from __future__ import annotations

from datetime import date
from math import ceil

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def _number(value):
    return float(value or 0)


class CashRegisterService:
    def __init__(self, db: Session, tenant_id: str, company_id: str):
        if not tenant_id or not company_id:
            raise HTTPException(status_code=400, detail="Tenant e empresa são obrigatórios.")
        self.db = db
        self.tenant_id = str(tenant_id)
        self.company_id = str(company_id)
        self.has_accounts = inspect(db.bind).has_table("TB_CONTA", schema="public")

    @property
    def scope(self):
        return {"tenant_id": self.tenant_id, "company_id": self.company_id}

    def _account_name_sql(self, alias="F"):
        if not self.has_accounts:
            return f"NULL AS cash_name"
        return f'''(
            SELECT C."CNT_DESCRICAO" FROM public."TB_CONTA" C
             WHERE C.tenant_id = {alias}.tenant_id
               AND C."CNT_ID" = {alias}."FCX_CAIXA"
             LIMIT 1
        ) AS cash_name'''

    @staticmethod
    def _person(prefix, row):
        identifier = row.get(f"{prefix}_id")
        return {"id": identifier, "name": row.get(f"{prefix}_name") or (f"Usuário #{identifier}" if identifier else "Não informado")}

    def _closing_dto(self, row):
        data = dict(row)
        cash_id = data.get("cash_id")
        return {
            "id": data.get("id"), "status": data.get("status"),
            "openedAt": data.get("opened_at"), "closedAt": data.get("closed_at"),
            "cashAccount": {"id": cash_id, "name": data.get("cash_name") or (f"Caixa #{cash_id}" if cash_id else "Não informado")},
            "openedBy": self._person("opened_by", data), "closedBy": self._person("closed_by", data),
            "totals": {
                "total": _number(data.get("total")), "cash": _number(data.get("cash")),
                "difference": _number(data.get("difference")), "change": _number(data.get("change")),
                "withdrawals": _number(data.get("withdrawals")), "supplies": _number(data.get("supplies")),
                "sales": _number(data.get("sales")), "discounts": _number(data.get("discounts")),
                "receipts": _number(data.get("receipts")), "payments": _number(data.get("payments")),
                "forgivenChange": _number(data.get("forgiven_change")),
            },
        }

    def list_closings(self, *, start: date | None, end: date | None, status: str | None,
                      cash_account: str | None, user: str | None, difference: str | None,
                      search: str | None, page: int, page_size: int):
        filters = ['F.tenant_id=:tenant_id', 'F.erp_company_id=:company_id']
        params = {**self.scope, "limit": page_size, "offset": (page - 1) * page_size}
        if start: filters.append('COALESCE(F."FCX_DT_ABERTURA", F."FCX_DT_LANCAMENTO")::date >= :start'); params["start"] = start
        if end: filters.append('COALESCE(F."FCX_DT_ABERTURA", F."FCX_DT_LANCAMENTO")::date <= :end'); params["end"] = end
        if status: filters.append('F."FCX_STATUS"=:status'); params["status"] = status
        if cash_account: filters.append('F."FCX_CAIXA"=:cash_account'); params["cash_account"] = cash_account
        if user: filters.append('(F."FCX_USU_ABERTURA"=:user OR F."FCX_USU_FECHAMENTO"=:user)'); params["user"] = user
        if difference == "positive": filters.append('F."FCX_VALOR_DIFERENCA" > 0')
        elif difference == "zero": filters.append('COALESCE(F."FCX_VALOR_DIFERENCA", 0) = 0')
        elif difference == "negative": filters.append('F."FCX_VALOR_DIFERENCA" < 0')
        if search:
            filters.append('(F."FCX_ID" ILIKE :search OR F."FCX_OBSERVACAO" ILIKE :search)'); params["search"] = f"%{search}%"
        where = " AND ".join(filters)
        base = f'''FROM public."TB_FECHAMENTO_CAIXA" F
          LEFT JOIN public."TB_USUARIO" UA ON UA.tenant_id=F.tenant_id AND UA."USU_ID"=F."FCX_USU_ABERTURA"
          LEFT JOIN public."TB_USUARIO" UF ON UF.tenant_id=F.tenant_id AND UF."USU_ID"=F."FCX_USU_FECHAMENTO"
         WHERE {where}'''
        total = self.db.execute(text(f"SELECT COUNT(*) {base}"), params).scalar_one()
        summary = dict(self.db.execute(text(f'''SELECT COUNT(*) closings,
          COALESCE(SUM(F."FCX_VALOR_TOTAL"),0) total_amount,
          COALESCE(SUM(F."FCX_VALOR_DIFERENCA"),0) difference_amount,
          COUNT(DISTINCT F."FCX_CAIXA") cash_accounts {base}'''), params).mappings().one())
        rows = self.db.execute(text(f'''SELECT F."FCX_ID" id, F."FCX_STATUS" status,
          F."FCX_DT_ABERTURA" opened_at, F."FCX_DT_FECHAMENTO" closed_at,
          F."FCX_CAIXA" cash_id, {self._account_name_sql()},
          F."FCX_USU_ABERTURA" opened_by_id, UA."USU_NOME" opened_by_name,
          F."FCX_USU_FECHAMENTO" closed_by_id, UF."USU_NOME" closed_by_name,
          F."FCX_VALOR_TOTAL" total, F."FCX_VALOR_CAIXA" cash,
          F."FCX_VALOR_DIFERENCA" difference, F."FCX_VALOR_TROCO" change,
          F."FCX_VALOR_SANGRIA" withdrawals, F."FCX_VALOR_SUPRIMENTO" supplies,
          F."FCX_VALOR_VENDA" sales, F."FCX_VALOR_DESCONTO" discounts,
          F."FCX_RECEBIMENTO" receipts, F."FCX_PAGAMENTO" payments,
          F."FCX_TROCO_PERDOADO" forgiven_change {base}
          ORDER BY F."FCX_DT_ABERTURA" DESC NULLS LAST, F."FCX_ID" DESC
          LIMIT :limit OFFSET :offset'''), params).mappings().all()
        return {"items": [self._closing_dto(row) for row in rows], "summary": {
            "closings": summary["closings"], "totalAmount": _number(summary["total_amount"]),
            "differenceAmount": _number(summary["difference_amount"]), "cashAccounts": summary["cash_accounts"]},
            "pagination": {"page": page, "pageSize": page_size, "total": total, "pages": ceil(total/page_size) if total else 0}}

    def get_closing(self, closing_id: str):
        result = self.list_closings(start=None, end=None, status=None, cash_account=None, user=None,
                                    difference=None, search=closing_id, page=1, page_size=100)
        closing = next((item for item in result["items"] if str(item["id"]) == str(closing_id)), None)
        if not closing: raise HTTPException(status_code=404, detail="Fechamento não encontrado.")
        params = {**self.scope, "closing_id": str(closing_id)}
        species = '''COALESCE((SELECT E."ESP_DESCRICAO" FROM public."TB_ESPECIE_MOEDA" E
          WHERE E.tenant_id=X.tenant_id AND E."ESP_ID"=X.{field}
          AND (E."ESP_EMPRESA" IS NULL OR E."ESP_EMPRESA"=:company_id) LIMIT 1), X.{field})'''
        payments = self.db.execute(text(f'''SELECT X."FCXI_SEQUENCIA" sequence,
          X."FCXI_ESPECIE_MOEDA" species_id, {species.format(field='"FCXI_ESPECIE_MOEDA"')} species,
          X."FCXI_VALOR_DEBITO" debit, X."FCXI_VALOR_CREDITO" credit,
          X."FCXI_VALOR_TOTAL" total, X."FCXI_VALOR_CAIXA" cash, X."FCXI_DIFERENCA" difference
          FROM public."TB_FECHAMENTO_CAIXA_ITEM" X WHERE X.tenant_id=:tenant_id
          AND X.erp_company_id=:company_id AND X."FCXI_FECHAMENTO"=:closing_id
          ORDER BY X."FCXI_SEQUENCIA"'''), params).mappings().all()
        sales = self.db.execute(text(f'''SELECT X."FCXV_SEQUENCIA" sequence,
          X."FCXV_ESPECIE_MOEDA" species_id, {species.format(field='"FCXV_ESPECIE_MOEDA"')} species,
          X."FCXV_ORIGEM" origin, X."FCXV_VALOR" value,
          X."FCXV_VALOR_CAIXA" cash, X."FCXV_DIFERENCA" difference
          FROM public."TB_FECHAMENTO_CAIXA_VENDA" X WHERE X.tenant_id=:tenant_id
          AND X.erp_company_id=:company_id AND X."FCXV_FECHAMENTO"=:closing_id
          ORDER BY X."FCXV_SEQUENCIA"'''), params).mappings().all()
        closing["paymentMethods"] = [{k: (_number(v) if k in {"debit","credit","total","cash","difference"} else v) for k,v in dict(row).items()} for row in payments]
        closing["sales"] = [{k: (_number(v) if k in {"value","cash","difference"} else v) for k,v in dict(row).items()} for row in sales]
        closing["timeline"] = ([{"at": closing["openedAt"], "type": "opening", "label": "Caixa aberto", "user": closing["openedBy"]}] if closing["openedAt"] else []) + ([{"at": closing["closedAt"], "type": "closing", "label": "Caixa fechado", "user": closing["closedBy"]}] if closing["closedAt"] else [])
        return closing

    def movements(self, closing_id: str, page: int, page_size: int):
        params = {**self.scope, "closing_id": str(closing_id), "limit": page_size, "offset": (page-1)*page_size}
        where = '''M.tenant_id=:tenant_id AND M.erp_company_id=:company_id AND M."MOV_FECHAMENTO"=:closing_id'''
        total = self.db.execute(text(f'SELECT COUNT(*) FROM public."TB_MOVIMENTO_CAIXA" M WHERE {where}'), params).scalar_one()
        rows = self.db.execute(text(f'''SELECT M."MOV_ID" id, M."MOV_DT_LANCAMENTO" occurred_at,
          M."MOV_TIPO" type, M."MOV_HISTORICO" history, M."MOV_VALOR" value,
          M."MOV_USUARIO" user_id, COALESCE(U."USU_NOME", M."MOV_USUARIO") user_name,
          M."MOV_ORIGEM" origin, M."MOV_ESPECIE_MOEDA" species_id,
          COALESCE((SELECT E."ESP_DESCRICAO" FROM public."TB_ESPECIE_MOEDA" E WHERE E.tenant_id=M.tenant_id
          AND E."ESP_ID"=M."MOV_ESPECIE_MOEDA" AND (E."ESP_EMPRESA" IS NULL OR E."ESP_EMPRESA"=:company_id) LIMIT 1), M."MOV_ESPECIE_MOEDA") species
          FROM public."TB_MOVIMENTO_CAIXA" M LEFT JOIN public."TB_USUARIO" U
          ON U.tenant_id=M.tenant_id AND U."USU_ID"=M."MOV_USUARIO" WHERE {where}
          ORDER BY M."MOV_DT_LANCAMENTO" DESC NULLS LAST, M."MOV_ID" DESC LIMIT :limit OFFSET :offset'''), params).mappings().all()
        return {"items": [{**dict(row), "value": _number(row["value"])} for row in rows],
                "pagination": {"page":page,"pageSize":page_size,"total":total,"pages":ceil(total/page_size) if total else 0}}

    def _require_closing(self, closing_id: str):
        row = self.db.execute(text('''SELECT "FCX_ID" id, "FCX_EMPRESA" company,
          "FCX_DT_ABERTURA" opened_at, "FCX_DT_FECHAMENTO" closed_at,
          "FCX_QTDE_VENDA" sales_quantity, "FCX_QTDE_CANCELADOS" cancelled_quantity,
          "FCX_QTDE_SANGRIA" withdrawal_quantity, "FCX_QTDE_SUPRIMENTO" supply_quantity
          FROM public."TB_FECHAMENTO_CAIXA" WHERE tenant_id=:tenant_id
          AND erp_company_id=:company_id AND "FCX_ID"=:closing_id'''),
          {**self.scope, "closing_id": str(closing_id)}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Fechamento nÃ£o encontrado.")
        return dict(row)

    def _sales_query(self, closing_id: str, page: int, page_size: int, *, cancelled: bool):
        closing = self._require_closing(closing_id)
        params = {**self.scope, "closing_id": str(closing_id), "limit": page_size,
                  "offset": (page - 1) * page_size}
        status_filter = '''AND P."PEV_STATUS"='C' ''' if cancelled else '''AND P."PEV_STATUS"<>'C' '''
        base = f'''FROM public."TB_PEDIDO_VENDA" P
          LEFT JOIN public."TB_PESSOA" C ON C.tenant_id=P.tenant_id AND C."PES_ID"=P."PEV_CLIENTE"
          LEFT JOIN public."TB_PESSOA" V ON V.tenant_id=P.tenant_id AND V."PES_ID"=P."PEV_VENDEDOR"
          WHERE P.tenant_id=:tenant_id AND P."PEV_EMPRESA"=:company_id {status_filter}
          AND EXISTS (SELECT 1 FROM public."TB_PEDIDO_VENDA_FIN" PF
            WHERE PF.tenant_id=P.tenant_id AND PF."PEVF_EMPRESA"=P."PEV_EMPRESA"
              AND PF."PEVF_PEDIDO_VENDA"=P."PEV_ID"
              AND PF."PEVF_FECHAMENTO"=:closing_id)'''
        summary = self.db.execute(text(f'''SELECT COUNT(*) quantity,
          COALESCE(SUM(P."PEV_VALOR_TOTAL"),0) total {base}'''), params).mappings().one()
        rows = self.db.execute(text(f'''SELECT P."PEV_ID" id,
          COALESCE(P."PEV_DT_FATURAMENTO",P."PEV_DT_EMISSAO",P."PEV_DT_LANCAMENTO") occurred_at,
          P."PEV_CLIENTE" customer_id,
          COALESCE(C."PES_FANTASIA_APELIDO",C."PES_RSOCIAL_NOME",'Cliente #' || P."PEV_CLIENTE") customer,
          P."PEV_VENDEDOR" seller_id,
          COALESCE(V."PES_FANTASIA_APELIDO",V."PES_RSOCIAL_NOME",'Vendedor #' || P."PEV_VENDEDOR") seller,
          P."PEV_VALOR_TOTAL" total, P."PEV_STATUS" status,
          (SELECT STRING_AGG(DISTINCT COALESCE(E."ESP_DESCRICAO",PF."PEVF_ESPECIE_MOEDA"), ', ')
             FROM public."TB_PEDIDO_VENDA_FIN" PF
             LEFT JOIN public."TB_ESPECIE_MOEDA" E ON E.tenant_id=PF.tenant_id
              AND E."ESP_ID"=PF."PEVF_ESPECIE_MOEDA"
              AND (E."ESP_EMPRESA" IS NULL OR E."ESP_EMPRESA"=:company_id)
            WHERE PF.tenant_id=P.tenant_id AND PF."PEVF_EMPRESA"=P."PEV_EMPRESA"
              AND PF."PEVF_PEDIDO_VENDA"=P."PEV_ID"
              AND PF."PEVF_FECHAMENTO"=:closing_id) payment_method
          {base}
          ORDER BY occurred_at DESC NULLS LAST, P."PEV_ID" DESC LIMIT :limit OFFSET :offset'''), params).mappings().all()
        quantity = int(summary["quantity"] or 0)
        total = _number(summary["total"])
        expected = _number(closing["cancelled_quantity"] if cancelled else closing["sales_quantity"])
        if not quantity and expected > 0:
            return {"available": False, "items": [], "summary": {},
                    "code": "SALE_LINKS_NOT_SYNCED_FOR_CLOSING",
                    "message": "As vendas individuais deste fechamento ainda nÃ£o estÃ£o disponÃ­veis no espelho.",
                    "missing": ["Registros de TB_PEDIDO_VENDA_FIN com PEVF_FECHAMENTO para este FCX_ID"]}
        return {"available": True,
                "source": "TB_PEDIDO_VENDA + TB_PEDIDO_VENDA_FIN.PEVF_FECHAMENTO",
                "items": [{**dict(row), "total": _number(row["total"])} for row in rows],
                "summary": {"quantity": quantity, "total": total,
                            "averageTicket": total / quantity if quantity else 0},
                "pagination": {"page": page, "pageSize": page_size, "total": quantity,
                               "pages": ceil(quantity/page_size) if quantity else 0}}

    def sales(self, closing_id: str, page: int, page_size: int):
        return self._sales_query(closing_id, page, page_size, cancelled=False)

    def cancelled_sales(self, closing_id: str, page: int, page_size: int):
        result = self._sales_query(closing_id, page, page_size, cancelled=True)
        result["statusRule"] = "PEV_STATUS='C' e vÃ­nculo explÃ­cito PEVF_FECHAMENTO"
        return result

    def products(self, closing_id: str, page: int, page_size: int):
        closing = self._require_closing(closing_id)
        params = {**self.scope, "closing_id": str(closing_id), "limit": page_size,
                  "offset": (page - 1) * page_size}
        base = '''FROM public."TB_PEDIDO_VENDA_ITEM" I
          JOIN public."TB_PEDIDO_VENDA" P ON P.tenant_id=I.tenant_id
            AND P."PEV_EMPRESA"=I."PEVI_EMPRESA" AND P."PEV_ID"=I."PEVI_PEDIDO_VENDA"
          LEFT JOIN public."TB_PRODUTO" PR ON PR.tenant_id=I.tenant_id
            AND PR."PRD_EMPRESA"=I."PEVI_EMPRESA" AND PR."PRD_ID"=I."PEVI_PRODUTO"
          WHERE I.tenant_id=:tenant_id AND I."PEVI_EMPRESA"=:company_id
            AND P."PEV_STATUS"<>'C'
            AND EXISTS (SELECT 1 FROM public."TB_PEDIDO_VENDA_FIN" PF
              WHERE PF.tenant_id=I.tenant_id AND PF."PEVF_EMPRESA"=I."PEVI_EMPRESA"
                AND PF."PEVF_PEDIDO_VENDA"=I."PEVI_PEDIDO_VENDA"
                AND PF."PEVF_FECHAMENTO"=:closing_id)'''
        grouped = f'''SELECT I."PEVI_PRODUTO" product_id,
          COALESCE(PR."PRD_DESCRICAO",'Produto #' || I."PEVI_PRODUTO") product,
          MAX(I."PEVI_UN_VENDA") unit, COUNT(*) item_lines,
          COUNT(DISTINCT I."PEVI_PEDIDO_VENDA") sales,
          COALESCE(SUM(I."PEVI_QUANTIDADE"),0) quantity,
          COALESCE(SUM(I."PEVI_VALOR_DESCONTO"),0) discount,
          COALESCE(SUM(I."PEVI_VALOR_TOTAL"),0) total {base}
          GROUP BY I."PEVI_PRODUTO", PR."PRD_DESCRICAO"'''
        summary = self.db.execute(text(f'''SELECT COUNT(*) products,
          COALESCE(SUM(item_lines),0) items, COALESCE(SUM(quantity),0) quantity,
          COALESCE(SUM(total),0) total FROM ({grouped}) G'''), params).mappings().one()
        rows = self.db.execute(text(f'''{grouped} ORDER BY total DESC, product
          LIMIT :limit OFFSET :offset'''), params).mappings().all()
        total_products = int(summary["products"] or 0)
        if not total_products and _number(closing["sales_quantity"]) > 0:
            return {"available": False, "items": [], "summary": {},
                    "code": "PRODUCT_LINKS_NOT_SYNCED_FOR_CLOSING",
                    "message": "Os produtos individuais deste fechamento ainda nÃ£o estÃ£o disponÃ­veis no espelho.",
                    "missing": ["PEVF_FECHAMENTO e itens de TB_PEDIDO_VENDA_ITEM para este FCX_ID"]}
        return {"available": True,
                "source": "TB_PEDIDO_VENDA_FIN -> TB_PEDIDO_VENDA_ITEM -> TB_PRODUTO",
                "items": [{**dict(row), "quantity": _number(row["quantity"]),
                           "discount": _number(row["discount"]), "total": _number(row["total"])} for row in rows],
                "summary": {"items": int(summary["items"] or 0), "products": total_products,
                            "quantity": _number(summary["quantity"]), "total": _number(summary["total"])},
                "pagination": {"page": page, "pageSize": page_size, "total": total_products,
                               "pages": ceil(total_products/page_size) if total_products else 0}}

    def unavailable_documents(self, closing_id: str, kind: str):
        self._require_closing(closing_id)
        if kind == "receipts":
            return {"available": False, "items": [], "summary": {},
                    "code": "RECEIPT_CLOSING_LINK_UNAVAILABLE",
                    "message": "Os dados de recebimentos individuais ainda nÃ£o estÃ£o disponÃ­veis neste espelho.",
                    "missing": ["VÃ­nculo de TB_RECEBIMENTO com FCX_ID ou tabelas de borderÃ´ de recebimento"]}
        return {"available": False, "items": [], "summary": {},
                "code": "PAYMENT_SOURCE_UNAVAILABLE",
                "message": "Os dados de pagamentos individuais ainda nÃ£o estÃ£o disponÃ­veis neste espelho.",
                "missing": ["TB_PAGAMENTO e vÃ­nculo comprovado com FCX_ID"]}

    def movements_by_kind(self, closing_id: str, kind: str, page: int, page_size: int):
        closing = self._require_closing(closing_id)
        rules = {"withdrawals": ("D", "SANGRIA"), "supplies": ("C", "SUPRIMENTO")}
        movement_type, origin = rules[kind]
        params = {**self.scope, "closing_id": str(closing_id), "movement_type": movement_type,
                  "origin": origin, "limit": page_size, "offset": (page - 1) * page_size}
        where = '''M.tenant_id=:tenant_id AND M.erp_company_id=:company_id
          AND M."MOV_FECHAMENTO"=:closing_id AND M."MOV_TIPO"=:movement_type
          AND M."MOV_ORIGEM"=:origin'''
        summary = self.db.execute(text(f'''SELECT COUNT(*) quantity, COALESCE(SUM(M."MOV_VALOR"),0) total
          FROM public."TB_MOVIMENTO_CAIXA" M WHERE {where}'''), params).mappings().one()
        rows = self.db.execute(text(f'''SELECT M."MOV_ID" id, M."MOV_DT_LANCAMENTO" occurred_at,
          M."MOV_HISTORICO" history, M."MOV_VALOR" value, M."MOV_USUARIO" user_id,
          COALESCE(U."USU_NOME",M."MOV_USUARIO") user_name, M."MOV_TIPO" type,
          M."MOV_ORIGEM" origin, M."MOV_ESPECIE_MOEDA" species_id,
          COALESCE(E."ESP_DESCRICAO",M."MOV_ESPECIE_MOEDA") species
          FROM public."TB_MOVIMENTO_CAIXA" M
          LEFT JOIN public."TB_USUARIO" U ON U.tenant_id=M.tenant_id AND U."USU_ID"=M."MOV_USUARIO"
          LEFT JOIN public."TB_ESPECIE_MOEDA" E ON E.tenant_id=M.tenant_id
            AND E."ESP_ID"=M."MOV_ESPECIE_MOEDA"
            AND (E."ESP_EMPRESA" IS NULL OR E."ESP_EMPRESA"=:company_id)
          WHERE {where} ORDER BY M."MOV_DT_LANCAMENTO" DESC NULLS LAST, M."MOV_ID" DESC
          LIMIT :limit OFFSET :offset'''), params).mappings().all()
        total = int(summary["quantity"] or 0)
        expected_key = "withdrawal_quantity" if kind == "withdrawals" else "supply_quantity"
        if not total and _number(closing[expected_key]) > 0:
            return {"available": False, "items": [], "summary": {},
                    "code": "MOVEMENTS_NOT_SYNCED_FOR_CLOSING",
                    "message": "Os movimentos individuais deste tipo ainda nÃ£o estÃ£o disponÃ­veis no espelho.",
                    "missing": [f"TB_MOVIMENTO_CAIXA com MOV_FECHAMENTO e MOV_ORIGEM={origin}"]}
        return {"available": True, "source": "TB_MOVIMENTO_CAIXA",
                "filter": {"MOV_TIPO": movement_type, "MOV_ORIGEM": origin},
                "items": [{**dict(row), "value": _number(row["value"])} for row in rows],
                "summary": {"quantity": total, "total": _number(summary["total"])},
                "pagination": {"page": page, "pageSize": page_size, "total": total,
                               "pages": ceil(total/page_size) if total else 0}}
