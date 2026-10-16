"""Read-only operational workspaces over the tenant's synchronized ERP data.

Missing fields remain unknown: balances and cash conferences are never replaced
with nominal document values or synthesized from sales totals.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from app.services.cash_closing_details_service import CashClosingDetailsService


def field(key, label, column, kind="text"):
    return {"key": key, "label": label, "source": column, "type": kind}


def source(title, group, table, pk, company, fields, date_field=None, joins=()):
    return {"title": title, "group": group, "table": table, "pk": pk,
            "company": company, "fields": fields, "date": date_field, "joins": joins}


PERSON = [("P", "TB_PESSOA", "PES_ID", "T.CLI_PESSOA", None)]
SOURCES = {
    "clientes": source("Clientes", "Pessoas", "TB_CLIENTE", "CLI_PESSOA", "CLI_EMPRESA", [
        field("codigo", "Código", "T.CLI_PESSOA"), field("nome", "Nome / razão social", "P.PES_RSOCIAL_NOME"),
        field("fantasia", "Nome fantasia", "P.PES_FANTASIA_APELIDO"), field("documento", "CPF/CNPJ", "P.PES_CNPJ_CPF"),
        field("email", "E-mail", "P.PES_EMAIL"), field("telefone", "Telefone", "P.PES_TELEFONE"),
        field("status", "Status", "P.PES_STATUS"), field("cadastro", "Cadastro", "P.PES_DT_CADASTRO", "date")], joins=PERSON),
    "fornecedores": source("Fornecedores", "Pessoas", "TB_FORNECEDOR", "FOR_PESSOA", "FOR_EMPRESA", [
        field("codigo", "Código", "T.FOR_PESSOA"), field("nome", "Nome / razão social", "P.PES_RSOCIAL_NOME"),
        field("fantasia", "Nome fantasia", "P.PES_FANTASIA_APELIDO"), field("email", "E-mail", "P.PES_EMAIL"),
        field("telefone", "Telefone", "P.PES_TELEFONE"), field("status", "Status", "P.PES_STATUS")],
        joins=[("P", "TB_PESSOA", "PES_ID", "T.FOR_PESSOA", None)]),
    "produtos": source("Produtos", "Produtos", "TB_PRODUTO", "PRD_ID", "PRD_EMPRESA", [
        field("codigo", "Código", "T.PRD_ID"), field("nome", "Produto", "T.PRD_DESCRICAO"),
        field("barras", "Código de barras", "T.PRD_CODIGO_BARRAS"), field("referencia", "Referência", "T.PRD_REFERENCIA"),
        field("codigos_barras", "Códigos de barras cadastrados", "B.CODIGOS"),
        field("departamento", "Departamento", "T.PRD_DEPARTAMENTO"), field("grupo", "Grupo", "T.PRD_GRUPO"),
        field("subgrupo", "Subgrupo", "T.PRD_SUBGRUPO"), field("marca", "Marca", "T.PRD_MARCA"),
        field("venda", "Preço de venda", "T.PRD_PRECO_VENDA", "currency"), field("custo", "Custo", "T.PRD_PRECO_CUSTO", "currency"),
        field("estoque", "Quantidade na posição única", "E.PRDE_ESTOQUE", "number"),
        field("posicoes", "Posições de estoque", "E.PRDE_POSICOES", "number"), field("minimo", "Estoque mínimo", "T.PRD_ESTOQUE_MINIMO", "number"),
        field("status", "Status", "T.PRD_STATUS")]),
    "grupos": source("Grupos de produtos", "Produtos", "TB_PROD_GRUPO", "PGRU_ID", "PGRU_EMPRESA", [
        field("codigo", "Código", "T.PGRU_ID"), field("nome", "Grupo", "T.PGRU_DESCRICAO"), field("status", "Status", "T.PGRU_STATUS")]),
    "marcas": source("Marcas", "Produtos", "TB_PROD_MARCA", "PMAR_ID", "PMAR_EMPRESA", [
        field("codigo", "Código", "T.PMAR_ID"), field("nome", "Marca", "T.PMAR_DESCRICAO"), field("status", "Status", "T.PMAR_STATUS")]),
    "departamentos": source("Departamentos de produtos", "Produtos", "TB_PROD_DEPARTAMENTO", "PDEP_ID", None, [
        field("codigo", "Código", "T.PDEP_ID"), field("nome", "Departamento", "T.PDEP_DESCRICAO"), field("status", "Status", "T.PDEP_STATUS")]),
    "subgrupos": source("Subgrupos de produtos", "Produtos", "TB_PROD_SUBGRUPO", "PSGR_ID", "PSGR_EMPRESA", [
        field("codigo", "Código", "T.PSGR_ID"), field("nome", "Subgrupo", "T.PSGR_DESCRICAO"),
        field("grupo", "Grupo", "T.PSGR_GRUPO"), field("status", "Status", "T.PSGR_STATUS")]),
    "plano-contas": source("Plano de Contas", "Diversos", "TB_PLANO_CONTA", "PLC_ID", "PLC_EMPRESA", [
        field("codigo", "Código", "T.PLC_ID"), field("nome", "Conta", "T.PLC_DESCRICAO"),
        field("pai", "Conta superior", "T.PLC_CONTA_PAI"), field("tipo", "Tipo", "T.PLC_TIPO"), field("dre", "Considera na DRE", "T.PLC_DRE")]),
    "fechamentos": source("Fechamentos de Caixa", "Financeiro", "TB_FECHAMENTO_CAIXA", "FCX_ID", "FCX_EMPRESA", [
        field("codigo", "ID", "T.FCX_ID"), field("caixa", "Caixa", "T.FCX_CAIXA"),
        field("operador", "Operador", "T.FCX_OPERADOR"), field("abertura", "Abertura", "T.FCX_DT_ABERTURA", "datetime"),
        field("fechamento", "Fechamento", "T.FCX_DT_FECHAMENTO", "datetime"), field("status", "Status", "T.FCX_STATUS")], "T.FCX_DT_ABERTURA"),
    "cheques": source("Cheques Emitidos", "Financeiro", "TB_CHEQUE_EMITIDO", "CHQ_ID", "CHQ_EMPRESA", [
        field("codigo", "ID", "T.CHQ_ID"), field("numero", "Cheque", "T.CHQ_NUMERO"), field("fornecedor", "Fornecedor", "T.CHQ_FORNECEDOR"),
        field("pessoa", "Pessoa (código)", "T.CHQ_PESSOA"), field("nominal", "Nominal", "T.CHQ_NOMINAL"),
        field("conta", "Conta bancária", "T.CHQ_CONTA"), field("emissao", "Emissão", "T.CHQ_DT_EMISSAO", "date"),
        field("vencimento", "Vencimento", "T.CHQ_DT_VENCIMENTO", "date"), field("valor", "Valor", "T.CHQ_VALOR", "currency"), field("status", "Status", "T.CHQ_STATUS")], "T.CHQ_DT_EMISSAO"),
    "sangrias": source("Sangrias", "Financeiro", "TB_CAIXA_SANGRIA", "SAN_ID", "SAN_EMPRESA", [
        field("codigo", "ID", "T.SAN_ID"), field("data", "Data", "T.SAN_DT_MOVIMENTO", "datetime"),
        field("caixa", "Caixa", "T.SAN_CAIXA"), field("operador", "Operador", "T.SAN_OPERADOR"),
        field("descricao", "Descrição", "T.SAN_DESCRICAO"), field("valor", "Valor", "T.SAN_VALOR", "currency"), field("status", "Status", "T.SAN_STATUS")], "T.SAN_DT_MOVIMENTO"),
}

for key, prefix, table, person in [("receber", "REC", "TB_RECEBIMENTO", "Cliente"), ("pagar", "PAG", "TB_PAGAMENTO", "Fornecedor")]:
    SOURCES[key] = source(f"Contas a {'Receber' if key == 'receber' else 'Pagar'}", "Financeiro", table, f"{prefix}_ID", f"{prefix}_EMPRESA", [
        field("codigo", "ID", f"T.{prefix}_ID"), field("pessoa", person, "P.PES_RSOCIAL_NOME"),
        field("documento", "Documento", f"T.{prefix}_DOCUMENTO"),
        field("especie", "Espécie (código)", f"T.{prefix}_ESPECIE_MOEDA"),
        field("centro_custo", "Centro de custo (código)", f"T.{prefix}_CENTRO_CUSTO"),
        field("plano_contas", "Plano de contas (código)", f"T.{prefix}_PLANO_CONTAS"),
        field("status", "Status", f"T.{prefix}_STATUS"), field("emissao", "Emissão", f"T.{prefix}_DT_EMISSAO", "date"),
        field("vencimento", "Vencimento", f"T.{prefix}_DT_VENCIMENTO", "date"),
        field("original", "Valor original", f"T.{prefix}_VALOR", "currency"),
        field("baixado", "Valor recebido" if key == "receber" else "Valor pago", f"T.{prefix}_VALOR_BAIXADO", "currency"),
        field("saldo", "Saldo atual", f"T.{prefix}_VALOR_ABERTO", "currency"),
        field("pagamento", "Data da última baixa", f"T.{prefix}_DT_PAGAMENTO", "date"), field("aberto", "Em aberto", f"T.{prefix}_ABERTO")],
        f"T.{prefix}_DT_VENCIMENTO", [("P", "TB_PESSOA", "PES_ID", f"T.{prefix}_PESSOA", None)])


def quote(name):
    if not name.replace("_", "").isalnum():
        raise ValueError("Identificador de catálogo inválido.")
    return '"' + name + '"'


class OperationsService:
    def __init__(self, db, tenant_id):
        self.db = db
        self.tenant = str(tenant_id)
        self.schema = {}
        for table, column in db.execute(text("""SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name LIKE 'TB_%'""")):
            self.schema.setdefault(table, set()).add(column)

    def prepare(self, resource, company):
        if resource not in SOURCES:
            raise LookupError("Consulta não encontrada.")
        spec = SOURCES[resource]
        required = {"tenant_id", spec["pk"]} | ({spec["company"]} if spec["company"] else set())
        if not required <= self.schema.get(spec["table"], set()):
            return spec, None
        aliases = {"T": self.schema[spec["table"]]}
        expression = lambda value: ".".join(quote(part) for part in value.split("."))
        available = lambda value: value.split(".")[1] in aliases.get(value.split(".")[0], set())
        joins = []
        if resource == "produtos":
            # Aggregate each relation before joining: local/variation and barcode
            # multiplicity must never duplicate products or imply an ERP total.
            if {"tenant_id", "PRDE_EMPRESA", "PRDE_PRODUTO", "PRDE_ESTOQUE"} <= self.schema.get("TB_PRODUTO_ESTOQUE", set()):
                joins.append('''LEFT JOIN (SELECT tenant_id, "PRDE_EMPRESA", "PRDE_PRODUTO",
                    COUNT(*) AS "PRDE_POSICOES",
                    CASE WHEN COUNT(*)=1 THEN MIN("PRDE_ESTOQUE") END AS "PRDE_ESTOQUE"
                    FROM "TB_PRODUTO_ESTOQUE" WHERE tenant_id=:tenant AND "PRDE_EMPRESA"::text=:company
                    GROUP BY tenant_id, "PRDE_EMPRESA", "PRDE_PRODUTO") "E"
                    ON "E".tenant_id="T".tenant_id AND "E"."PRDE_EMPRESA"::text="T"."PRD_EMPRESA"::text
                    AND "E"."PRDE_PRODUTO"::text="T"."PRD_ID"::text''')
                aliases["E"] = {"PRDE_ESTOQUE", "PRDE_POSICOES"}
            if {"tenant_id", "PRDC_EMPRESA", "PRDC_PRODUTO", "PRDC_COD_BARRAS"} <= self.schema.get("TB_PROD_CODIGO_BARRAS", set()):
                joins.append('''LEFT JOIN (SELECT tenant_id, "PRDC_EMPRESA", "PRDC_PRODUTO",
                    STRING_AGG(DISTINCT "PRDC_COD_BARRAS"::text, ', ' ORDER BY "PRDC_COD_BARRAS"::text) AS "CODIGOS"
                    FROM "TB_PROD_CODIGO_BARRAS" WHERE tenant_id=:tenant AND "PRDC_EMPRESA"::text=:company
                    GROUP BY tenant_id, "PRDC_EMPRESA", "PRDC_PRODUTO") "B"
                    ON "B".tenant_id="T".tenant_id AND "B"."PRDC_EMPRESA"::text="T"."PRD_EMPRESA"::text
                    AND "B"."PRDC_PRODUTO"::text="T"."PRD_ID"::text''')
                aliases["B"] = {"CODIGOS"}
        for alias, table, column, root, companies in spec["joins"]:
            columns = self.schema.get(table, set())
            if {column, "tenant_id"} <= columns and available(root) and (not companies or companies[0] in columns and companies[1] in aliases["T"]):
                aliases[alias] = columns
                condition = f'{quote(alias)}.{quote(column)}::text={expression(root)}::text AND {quote(alias)}.tenant_id="T".tenant_id'
                if companies:
                    condition += f' AND {quote(alias)}.{quote(companies[0])}::text="T".{quote(companies[1])}::text'
                joins.append(f'LEFT JOIN {quote(table)} {quote(alias)} ON {condition}')
        fields = []
        for item in spec["fields"]:
            item = dict(item)
            if resource == "clientes" and item["key"] in {"status", "cadastro"}:
                native = "T.CLI_STATUS" if item["key"] == "status" else "T.CLI_DT_CADASTRO"
                if available(native):
                    item["source"] = native
            if resource == "fechamentos" and item["key"] == "operador" and not available(item["source"]) and "FCX_USU_ABERTURA" in aliases["T"]:
                item["source"] = "T.FCX_USU_ABERTURA"
            fields.append({**item, "available": available(item["source"])})
        from_sql = f'{quote(spec["table"])} "T" ' + " ".join(joins)
        where = ['"T".tenant_id=:tenant']
        params = {"tenant": self.tenant}
        if spec["company"]:
            where.append(f'"T".{quote(spec["company"])}::text=:company')
            params["company"] = str(company)
        return spec, {"fields": fields, "from": from_sql, "where": where, "params": params, "expr": expression, "available": available}

    def list(self, resource, company, search="", status="", start=None, end=None, page=1, page_size=25, sort=None, direction="asc", export=False):
        spec, query = self.prepare(resource, company)
        public = [{key: item[key] for key in ("key", "label", "type")} for item in spec["fields"]]
        if query is None:
            return {"title": spec["title"], "group": spec["group"], "available": False,
                    "message": "Os dados desta consulta ainda não foram sincronizados do ERP.",
                    "columns": public, "rows": [], "total": 0, "summary": {}, "missing_fields": [], "statuses": [], "has_period": bool(spec["date"])}
        fields, params, where = query["fields"], query["params"], query["where"]
        expr = query["expr"]
        if search.strip():
            checks = [f'CAST({expr(item["source"])} AS TEXT) ILIKE :search' for item in fields if item["available"]]
            where.append("(" + " OR ".join(checks) + ")")
            params["search"] = "%" + search.strip() + "%"
        status_field = next((f for f in fields if f["key"] == "status" and f["available"]), None)
        if status and status_field:
            where.append(f'CAST({expr(status_field["source"])} AS TEXT)=:status')
            params["status"] = status
        if spec["date"] and (start or end):
            if not query["available"](spec["date"]):
                raise ValueError("A data necessária para filtrar esta consulta ainda não foi sincronizada.")
            if not start or not end:
                raise ValueError("Informe o início e o fim do período.")
            if date.fromisoformat(str(start)) > date.fromisoformat(str(end)):
                raise ValueError("A data inicial deve ser anterior à final.")
            where.append(f'CAST({expr(spec["date"])} AS DATE) BETWEEN :start AND :end')
            params.update(start=start, end=end)
        where_sql = " AND ".join(where)
        base = f'FROM {query["from"]} WHERE {where_sql}'
        total = self.db.execute(text("SELECT COUNT(*) " + base), params).scalar()
        selected = [f'{expr(item["source"])} AS {quote(item["key"])}' if item["available"] else f'NULL AS {quote(item["key"])}' for item in fields]
        selected.append(f'CAST("T".{quote(spec["pk"])} AS TEXT) AS "_id"')
        sort_field = next((item for item in fields if item["key"] == sort and item["available"]), None)
        if sort and sort_field is None:
            raise ValueError("Ordenação indisponível para esta coluna.")
        order = expr(sort_field["source"]) if sort_field else f'"T".{quote(spec["pk"])}'
        limit = 10001 if export else page_size
        rows = self.db.execute(text(f'SELECT {", ".join(selected)} {base} ORDER BY {order} {"DESC" if direction == "desc" else "ASC"} NULLS LAST LIMIT :limit OFFSET :offset'),
                               {**params, "limit": limit, "offset": 0 if export else (page - 1) * page_size}).mappings().all()
        summary = {}
        for item in fields:
            if spec["group"] == "Financeiro" and item["type"] == "currency" and item["available"]:
                column = expr(item["source"])
                summary[item["key"]] = self.db.execute(text(f'SELECT CASE WHEN COUNT({column})=COUNT(*) THEN SUM(CAST({column} AS NUMERIC)) END {base}'), params).scalar()
        statuses = []
        if status_field:
            # Only statuses belonging to this tenant/company are offered.
            _, unfiltered = self.prepare(resource, company)
            statuses = list(self.db.execute(text(f'SELECT DISTINCT CAST({expr(status_field["source"])} AS TEXT) FROM {unfiltered["from"]} WHERE {" AND ".join(unfiltered["where"])} ORDER BY 1 LIMIT 30'), unfiltered["params"]).scalars())
        return {"title": spec["title"], "group": spec["group"], "available": True,
                "columns": [{**item, "available": f["available"]} for item, f in zip(public, fields)],
                "rows": [dict(row) for row in rows], "total": total, "summary": summary,
                "missing_fields": [item["label"] for item in fields if not item["available"]],
                "statuses": [s for s in statuses if s is not None], "has_period": bool(spec["date"])}

    def detail(self, resource, company, record_id):
        spec, query = self.prepare(resource, company)
        if query is None:
            raise LookupError("Registro não sincronizado.")
        fields = query["fields"]
        selected = [f'{query["expr"](f["source"])} AS {quote(f["key"])}' if f["available"] else f'NULL AS {quote(f["key"])}' for f in fields]
        row = self.db.execute(text(f'SELECT {", ".join(selected)} FROM {query["from"]} WHERE {" AND ".join(query["where"])} AND CAST("T".{quote(spec["pk"])} AS TEXT)=:id'), {**query["params"], "id": str(record_id)}).mappings().first()
        if not row:
            raise LookupError("Registro não encontrado.")
        result = {"record": dict(row), "cash_payments": [], "cash_payments_available": False,
                  "cash_items": {}, "cash_items_available": False}
        stock_columns = {"tenant_id", "PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_LOCAL", "PRDE_VARIACAO", "PRDE_ESTOQUE"}
        if resource == "produtos" and stock_columns <= self.schema.get("TB_PRODUTO_ESTOQUE", set()):
            positions = self.db.execute(text('''SELECT "PRDE_LOCAL" AS local, "PRDE_VARIACAO" AS variacao,
                "PRDE_ESTOQUE" AS quantidade FROM "TB_PRODUTO_ESTOQUE" WHERE tenant_id=:tenant
                AND "PRDE_EMPRESA"::text=:company AND "PRDE_PRODUTO"::text=:id
                ORDER BY "PRDE_LOCAL", "PRDE_VARIACAO" LIMIT 10001'''),
                {"tenant": self.tenant, "company": str(company), "id": str(record_id)}).mappings().all()
            result.update(stock_positions=[dict(position) for position in positions[:10000]],
                          stock_positions_truncated=len(positions) > 10000)
        columns = self.schema.get("TB_FECHAMENTO_CAIXA_FORMA", set())
        required = {"tenant_id", "FCF_FECHAMENTO", "FCF_EMPRESA", "FCF_NOME", "FCF_ENTRADAS", "FCF_SAIDAS", "FCF_CONFERENCIA"}
        if resource == "fechamentos" and required <= columns:
            items = self.db.execute(text('''SELECT "FCF_NOME" AS nome, "FCF_ENTRADAS" AS entradas,
                "FCF_SAIDAS" AS saidas, "FCF_CONFERENCIA" AS conferencia
                FROM "TB_FECHAMENTO_CAIXA_FORMA" WHERE tenant_id=:tenant
                AND "FCF_EMPRESA"::text=:company AND "FCF_FECHAMENTO"::text=:id ORDER BY 1'''),
                {"tenant": self.tenant, "company": str(company), "id": str(record_id)}).mappings().all()
            result["cash_payments_available"] = True
            for item in items:
                incoming = Decimal(str(item["entradas"])) if item["entradas"] is not None else None
                outgoing = Decimal(str(item["saidas"])) if item["saidas"] is not None else None
                counted = Decimal(str(item["conferencia"])) if item["conferencia"] is not None else None
                total = incoming - outgoing if incoming is not None and outgoing is not None else None
                result["cash_payments"].append({**dict(item), "total": total,
                                                "diferenca": counted - total if counted is not None and total is not None else None})
        movement_table = "TB_PIGO_CAIXA_MOVIMENTO" if "TB_PIGO_CAIXA_MOVIMENTO" in self.schema else "TB_FECHAMENTO_CAIXA_ITEM"
        if resource == "fechamentos" and {"tenant_id", "FCI_ID", "FCI_FECHAMENTO", "FCI_EMPRESA", "FCI_TIPO", "FCI_DATA", "FCI_DESCRICAO", "FCI_QUANTIDADE", "FCI_VALOR", "FCI_DOCUMENTO", "FCI_USUARIO"} <= self.schema.get(movement_table, set()):
            items = self.db.execute(text(f'''SELECT "FCI_TIPO" AS tipo, "FCI_DATA" AS data,
                "FCI_DESCRICAO" AS descricao,"FCI_QUANTIDADE" AS quantidade,"FCI_VALOR" AS valor,
                "FCI_DOCUMENTO" AS documento,"FCI_USUARIO" AS usuario FROM "{movement_table}"
                WHERE tenant_id=:tenant AND "FCI_EMPRESA"::text=:company AND "FCI_FECHAMENTO"::text=:id
                ORDER BY "FCI_DATA", "FCI_ID" LIMIT 10001'''),
                {"tenant": self.tenant, "company": str(company), "id": str(record_id)}).mappings().all()
            result["cash_items_available"] = True
            result["cash_items_truncated"] = len(items) > 10000
            for item in items[:10000]:
                result["cash_items"].setdefault(item["tipo"], []).append(dict(item))
        if resource == "fechamentos":
            result = CashClosingDetailsService(self.db, self.schema, self.tenant, company, record_id).enrich(result)
        return result

    def forecast(self, company, start, end):
        if (end - start).days < 0 or (end - start).days > 366:
            raise ValueError("Selecione um intervalo de até 366 dias.")
        daily = {}
        unavailable = []
        for key, prefix, side in [("receber", "REC", "entradas"), ("pagar", "PAG", "saidas")]:
            spec, query = self.prepare(key, company)
            required = {f"{prefix}_VALOR_ABERTO", f"{prefix}_DT_VENCIMENTO", f"{prefix}_ABERTO"}
            if query is None or not required <= self.schema.get(spec["table"], set()):
                unavailable.append(spec["title"])
                continue
            status_filter = f' AND COALESCE(UPPER(TRIM("T"."{prefix}_STATUS")),\'\') NOT IN (\'C\',\'CANCELADO\',\'CANCELADA\')' if f"{prefix}_STATUS" in self.schema[spec["table"]] else ""
            rows = self.db.execute(text(f'''SELECT CAST("T"."{prefix}_DT_VENCIMENTO" AS DATE) AS dia,
                "T"."{prefix}_VALOR_ABERTO" AS saldo FROM {query["from"]}
                WHERE {" AND ".join(query["where"])} AND "T"."{prefix}_ABERTO"='S' {status_filter}
                AND CAST("T"."{prefix}_DT_VENCIMENTO" AS DATE) BETWEEN :start AND :end'''),
                {**query["params"], "start": start, "end": end}).mappings().all()
            if any(row["saldo"] is None for row in rows):
                unavailable.append(spec["title"])
                continue
            for row in rows:
                day = row["dia"].isoformat()
                daily.setdefault(day, {"entradas": Decimal(0), "saidas": Decimal(0)})[side] += Decimal(str(row["saldo"]))
        if unavailable:
            return {"available": False, "missing": unavailable, "rows": [], "summary": {}}
        accumulated = Decimal(0)
        rows = []
        cursor = start
        while cursor <= end:
            item = daily.get(cursor.isoformat(), {"entradas": Decimal(0), "saidas": Decimal(0)})
            net = item["entradas"] - item["saidas"]
            accumulated += net
            rows.append({"dia": cursor, **item, "resultado": net, "acumulado": accumulated})
            cursor += timedelta(days=1)
        return {"available": True, "rows": rows, "summary": {
            "entradas": sum((r["entradas"] for r in rows), Decimal(0)),
            "saidas": sum((r["saidas"] for r in rows), Decimal(0)), "resultado": accumulated}}
