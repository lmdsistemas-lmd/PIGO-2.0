"""Read the physical cash contract from the supplied agent without guessing codes."""
from sqlalchemy import text


class CashRegisterService:
    def __init__(self, db, schema, tenant, company, closing):
        self.db, self.schema = db, schema
        self.params = {"tenant": str(tenant), "company": str(company), "closing": str(closing)}

    def has(self, table, columns):
        return {"tenant_id", *columns.split()} <= self.schema.get(table, set())

    def select(self, table, mapping, scope):
        expressions = [f'"{column}" AS "{key}"' if column in self.schema.get(table, set()) else f'NULL AS "{key}"' for key, column in mapping.items()]
        keys = {"TB_FECHAMENTO_CAIXA": "FCX_ID", "TB_FECHAMENTO_CAIXA_ITEM": "FCXI_SEQUENCIA",
                "TB_FECHAMENTO_CAIXA_VENDA": "FCXV_SEQUENCIA", "TB_MOVIMENTO_CAIXA": "MOV_ID",
                "TB_PEDIDO_VENDA": "PEV_ID"}
        order = f' ORDER BY "{keys[table]}"' if keys.get(table) in self.schema.get(table, set()) else ""
        return [dict(row) for row in self.db.execute(text(f'SELECT {", ".join(expressions)} FROM "{table}" WHERE tenant_id=:tenant AND {scope}{order} LIMIT 10001'), self.params).mappings()]

    def enrich(self, result):
        summary = {"vendas": "FCX_VALOR_VENDA", "total_registrado": "FCX_VALOR_TOTAL", "valor_caixa": "FCX_VALOR_CAIXA",
                   "diferenca": "FCX_VALOR_DIFERENCA", "sangrias": "FCX_VALOR_SANGRIA", "suprimentos": "FCX_VALOR_SUPRIMENTO",
                   "troco": "FCX_VALOR_TROCO", "recebimentos":"FCX_RECEBIMENTO", "pagamentos":"FCX_PAGAMENTO"}
        present = {key: column for key, column in summary.items() if column in self.schema.get("TB_FECHAMENTO_CAIXA", set())}
        if present:
            rows = self.select("TB_FECHAMENTO_CAIXA", present, '"FCX_EMPRESA"::text=:company AND "FCX_ID"::text=:closing')
            result["cash_summary"] = rows[0] if rows else {}
        if self.has("TB_FECHAMENTO_CAIXA_ITEM", "FCXI_EMPRESA FCXI_FECHAMENTO FCXI_SEQUENCIA"):
            payments = self.select("TB_FECHAMENTO_CAIXA_ITEM", {
                "nome": "FCXI_ESPECIE_MOEDA", "debito": "FCXI_VALOR_DEBITO", "credito": "FCXI_VALOR_CREDITO",
                "total": "FCXI_VALOR_TOTAL", "valor_caixa": "FCXI_VALOR_CAIXA", "diferenca": "FCXI_DIFERENCA",
            }, '"FCXI_EMPRESA"::text=:company AND "FCXI_FECHAMENTO"::text=:closing')
            names = {}
            if self.has("TB_ESPECIE_MOEDA", "ESP_ID ESP_DESCRICAO"):
                scope = ' AND "ESP_EMPRESA"::text=:company' if "ESP_EMPRESA" in self.schema["TB_ESPECIE_MOEDA"] else ""
                names = {str(row[0]): row[1] for row in self.db.execute(text('SELECT "ESP_ID", "ESP_DESCRICAO" FROM "TB_ESPECIE_MOEDA" WHERE tenant_id=:tenant' + scope), self.params)}
            for row in payments:
                row["nome"] = names.get(str(row["nome"])) or f'Forma {row["nome"]}'
            if not payments and result.get("cash_payments_available"):
                payments = None
            if payments is not None:
                result["cash_items_truncated"] = result.get("cash_items_truncated", False) or len(payments) > 10000
                result.update(cash_payments=payments[:10000], cash_payments_available=True,
                          cash_payment_columns=[{"key": key, "label": label, "type": "text" if key == "nome" else "currency"} for key, label in [
                              ("nome", "Forma de pagamento"), ("debito", "Débitos"), ("credito", "Créditos"),
                              ("total", "Total registrado"), ("valor_caixa", "Valor de caixa"), ("diferenca", "Diferença registrada")]])
        if self.has("TB_MOVIMENTO_CAIXA", "MOV_EMPRESA MOV_ID MOV_FECHAMENTO"):
            movements = self.select("TB_MOVIMENTO_CAIXA", {
                "codigo": "MOV_ID", "data": "MOV_DT_EMISSAO", "tipo": "MOV_TIPO", "origem": "MOV_ORIGEM",
                "descricao": "MOV_HISTORICO", "valor": "MOV_VALOR", "status": "MOV_STATUS", "usuario": "MOV_USUARIO",
            }, '"MOV_EMPRESA"::text=:company AND "MOV_FECHAMENTO"::text=:closing')
            result["cash_movements"] = movements[:10000]
            result["cash_movements_available"] = True
            result["cash_items_truncated"] = result.get("cash_items_truncated", False) or len(movements) > 10000
        if self.has("TB_FECHAMENTO_CAIXA_VENDA", "FCXV_EMPRESA FCXV_FECHAMENTO FCXV_SEQUENCIA"):
            sales_forms = self.select("TB_FECHAMENTO_CAIXA_VENDA", {
                "sequencia": "FCXV_SEQUENCIA", "forma": "FCXV_ESPECIE_MOEDA", "origem": "FCXV_ORIGEM",
                "valor": "FCXV_VALOR", "valor_caixa": "FCXV_VALOR_CAIXA", "diferenca": "FCXV_DIFERENCA",
            }, '"FCXV_EMPRESA"::text=:company AND "FCXV_FECHAMENTO"::text=:closing')
            result["cash_sales_forms"] = sales_forms[:10000]
            result["cash_items_truncated"] = result.get("cash_items_truncated", False) or len(sales_forms) > 10000
        self.add_orders(result)
        return result

    def add_orders(self, result):
        if not self.has("TB_PEDIDO_VENDA", "PEV_EMPRESA PEV_ID PEV_FECHAMENTO"):
            return
        orders = self.select("TB_PEDIDO_VENDA", {
            "pedido": "PEV_ID", "data": "PEV_DT_EMISSAO", "cliente": "PEV_CLIENTE",
            "status": "PEV_STATUS", "valor": "PEV_VALOR_TOTAL",
            "cancelamento": "PEV_DT_CANCELAMENTO", "motivo": "PEV_DESCRICAO_CANCELAMENTO",
        }, '"PEV_EMPRESA"::text=:company AND "PEV_FECHAMENTO"::text=:closing')
        result.update(cash_orders=orders[:10000], cash_orders_available=True,
                      cash_cancellations_available="PEV_DT_CANCELAMENTO" in self.schema["TB_PEDIDO_VENDA"])
        result["cash_items_truncated"] = result.get("cash_items_truncated", False) or len(orders) > 10000
        if result["cash_cancellations_available"]:
            cancelled = self.select("TB_PEDIDO_VENDA", {
                "pedido": "PEV_ID", "data": "PEV_DT_EMISSAO", "cliente": "PEV_CLIENTE", "status": "PEV_STATUS",
                "valor": "PEV_VALOR_TOTAL", "cancelamento": "PEV_DT_CANCELAMENTO", "motivo": "PEV_DESCRICAO_CANCELAMENTO",
            }, '"PEV_EMPRESA"::text=:company AND "PEV_FECHAMENTO"::text=:closing AND "PEV_DT_CANCELAMENTO" IS NOT NULL')
            result["cash_cancellations"] = cancelled[:10000]
            result["cash_items_truncated"] = result["cash_items_truncated"] or len(cancelled) > 10000
        if not self.has("TB_PEDIDO_VENDA_ITEM", "PEVI_EMPRESA PEVI_PEDIDO_VENDA PEVI_SEQUENCIA"):
            return
        mapping = {"pedido": "PEVI_PEDIDO_VENDA", "sequencia": "PEVI_SEQUENCIA", "produto": "PEVI_PRODUTO",
                   "descricao": "PEVI_DESCRICAO", "quantidade": "PEVI_QUANTIDADE", "valor": "PEVI_VALOR_TOTAL"}
        expressions = [f'I."{column}" AS "{key}"' if column in self.schema["TB_PEDIDO_VENDA_ITEM"] else f'NULL AS "{key}"' for key, column in mapping.items()]
        for key, column in {"status": "PEV_STATUS", "cancelamento": "PEV_DT_CANCELAMENTO"}.items():
            expressions.append(f'P."{column}" AS "{key}"' if column in self.schema["TB_PEDIDO_VENDA"] else f'NULL AS "{key}"')
        items = self.db.execute(text(f'''SELECT {", ".join(expressions)} FROM "TB_PEDIDO_VENDA_ITEM" I
            JOIN "TB_PEDIDO_VENDA" P ON P.tenant_id=I.tenant_id
            AND P."PEV_EMPRESA"::text=I."PEVI_EMPRESA"::text AND P."PEV_ID"::text=I."PEVI_PEDIDO_VENDA"::text
            WHERE P.tenant_id=:tenant AND P."PEV_EMPRESA"::text=:company AND P."PEV_FECHAMENTO"::text=:closing
            ORDER BY I."PEVI_PEDIDO_VENDA", I."PEVI_SEQUENCIA" LIMIT 10001'''), self.params).mappings().all()
        result.update(cash_order_products=[dict(item) for item in items[:10000]], cash_order_products_available=True)
        result["cash_items_truncated"] = result.get("cash_items_truncated", False) or len(items) > 10000
