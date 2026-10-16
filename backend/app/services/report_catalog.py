from copy import deepcopy
import json
from sqlalchemy import text
from app.services.business_semantic_layer import BusinessSemanticLayer


def _field(label, expression, data_type="text", aggregations=None):
    return {
        "label": label,
        "expression": expression,
        "type": data_type,
        "aggregations": aggregations or (["count"] if data_type == "text" else ["sum", "avg", "min", "max", "count"]),
    }


CATALOG = {
    "sales": {
        "label": "Vendas",
        "sources": {
            "orders": {
                "label": "Pedidos",
                "description": "Pedidos, clientes, vendedores e valores de venda.",
                "table": "TB_PEDIDO_VENDA",
                "alias": "PV",
                "fields": {
                    "number": _field("Número", "PV.PEV_ID"),
                    "date": _field("Data", "PV.PEV_DT_EMISSAO", "date", ["min", "max", "count"]),
                    "customer_id": _field("Cliente", "PV.PEV_CLIENTE"),
                    "seller_id": _field("Vendedor", "PV.PEV_VENDEDOR"),
                    "status": _field("Status", "PV.PEV_STATUS"),
                    "total": _field("Valor", "COALESCE(PV.PEV_VALOR_TOTAL, 0)", "currency"),
                    "company": _field("Empresa", "PV.PEV_EMPRESA"),
                },
                "filters": {
                    "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
                    "period": {"label": "Período", "field": "date", "operators": ["between"]},
                    "status": {"label": "Status", "field": "status", "operators": ["eq", "in"]},
                    "customer_id": {"label": "Cliente", "field": "customer_id", "operators": ["eq", "in"]},
                    "seller_id": {"label": "Vendedor", "field": "seller_id", "operators": ["eq", "in"]},
                    "total": {"label": "Valor da venda", "field": "total", "operators": ["gte", "lte"]},
                },
                "groupings": ["date", "customer_id", "seller_id", "status", "company"],
            },
        },
        "planned_sources": ["Itens", "Clientes", "Produtos", "Vendedores", "Comissões", "Metas", "Cancelamentos"],
    },
    "finance": {
        "label": "Financeiro",
        "sources": {
            "receipts": {
                "label": "Recebimentos",
                "description": "Títulos emitidos, vencimentos, status e valores.",
                "table": "TB_RECEBIMENTO",
                "alias": "REC",
                "fields": {
                    "number": _field("Número", "REC.REC_ID"),
                    "issue_date": _field("Emissão", "REC.REC_DT_EMISSAO", "date", ["min", "max", "count"]),
                    "due_date": _field("Vencimento", "REC.REC_DT_VENCIMENTO", "date", ["min", "max", "count"]),
                    "customer_id": _field("Cliente", "REC.REC_PESSOA"),
                    "status": _field("Status", "REC.REC_STATUS"),
                    "open": _field("Em aberto", "REC.REC_ABERTO"),
                    "amount": _field("Valor", "COALESCE(REC.REC_VALOR, 0)", "currency"),
                    "company": _field("Empresa", "REC.REC_EMPRESA"),
                },
                "filters": {
                    "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
                    "period": {"label": "Período de emissão", "field": "issue_date", "operators": ["between"]},
                    "status": {"label": "Status", "field": "status", "operators": ["eq", "in"]},
                    "open": {"label": "Em aberto", "field": "open", "operators": ["eq"], "options": ["S", "N"]},
                    "customer_id": {"label": "Cliente", "field": "customer_id", "operators": ["eq", "in"]},
                },
                "groupings": ["issue_date", "due_date", "customer_id", "status", "open", "company"],
            },
        },
        "planned_sources": ["Pagamentos", "Fluxo de Caixa", "Carteiras", "Inadimplência", "Centro de Custos", "Movimentações"],
    },
    "accounting": {"label": "Contabilidade", "sources": {}, "planned_sources": ["Notas", "SPED", "CFOP", "NCM", "Impostos", "Entradas", "Saídas", "Livros", "Transportes"]},
    "other": {"label": "Outros", "sources": {}, "planned_sources": ["Funcionários", "Estoque", "Inventário", "Auditoria", "Logs", "Usuários", "Acessos", "Conferência"]},
}

CATALOG["sales"]["sources"].update({
    "items": {
        "label": "Itens vendidos", "description": "Produtos, quantidades, custos e valores por pedido.",
        "table": "TB_PEDIDO_VENDA_ITEM", "alias": "I",
        "joins": [
            "JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA AND PV.PEV_EMPRESA = I.PEVI_EMPRESA",
            "LEFT JOIN TB_PRODUTO P ON P.PRD_ID = I.PEVI_PRODUTO AND P.PRD_EMPRESA = I.PEVI_EMPRESA",
        ],
        "fields": {
            "order_number": _field("Pedido", "I.PEVI_PEDIDO_VENDA"),
            "date": _field("Data", "PV.PEV_DT_EMISSAO", "date", ["min", "max", "count"]),
            "product_id": _field("Código do produto", "I.PEVI_PRODUTO"),
            "product": _field("Produto", "P.PRD_DESCRICAO"),
            "group": _field("Grupo", "P.PRD_GRUPO"), "brand": _field("Marca", "P.PRD_MARCA"),
            "quantity": _field("Quantidade", "COALESCE(I.PEVI_QUANTIDADE, 0)", "number"),
            "unit_price": _field("Valor unitário", "COALESCE(I.PEVI_VALOR_UNITARIO, 0)", "currency"),
            "unit_cost": _field("Custo unitário", "COALESCE(I.PEVI_VALOR_CUSTO_UNITARIO, 0)", "currency"),
            "total": _field("Valor total", "COALESCE(I.PEVI_VALOR_TOTAL, 0)", "currency"),
            "company": _field("Empresa", "I.PEVI_EMPRESA"),
        },
        "filters": {
            "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
            "period": {"label": "Período", "field": "date", "operators": ["between"]},
            "product_id": {"label": "Produto", "field": "product_id", "operators": ["eq", "in"], "option_label": "product"},
            "group": {"label": "Grupo", "field": "group", "operators": ["eq", "in"]},
            "brand": {"label": "Marca", "field": "brand", "operators": ["eq", "in"]},
            "total": {"label": "Valor da venda", "field": "total", "operators": ["gte", "lte"]},
        },
        "groupings": ["date", "product_id", "product", "group", "brand", "company"],
    },
    "customers": {
        "label": "Clientes", "description": "Cadastro, localização e vendedor associado.",
        "table": "TB_CLIENTE", "alias": "C", "joins": ["JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA", "LEFT JOIN TB_CIDADE CI ON CI.CID_ID = P.PES_CIDADE"],
        "fields": {
            "customer_id": _field("Código", "C.CLI_PESSOA"), "name": _field("Nome", "P.PES_RSOCIAL_NOME"),
            "trade_name": _field("Fantasia", "P.PES_FANTASIA_APELIDO"), "city": _field("Cidade", "CI.CID_NOME"),
            "registered_at": _field("Cadastro", "P.PES_DT_CADASTRO", "date", ["min", "max", "count"]),
            "seller_id": _field("Vendedor", "P.PES_VENDEDOR"), "company": _field("Empresa", "C.CLI_EMPRESA"),
        },
        "filters": {
            "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
            "period": {"label": "Período de cadastro", "field": "registered_at", "operators": ["between"]},
            "city": {"label": "Cidade", "field": "city", "operators": ["eq", "in"]},
            "seller_id": {"label": "Vendedor", "field": "seller_id", "operators": ["eq", "in"]},
        }, "groupings": ["registered_at", "city", "seller_id", "company"],
    },
    "products": {
        "label": "Produtos", "description": "Catálogo de produtos, preços, custos, grupos e marcas.",
        "table": "TB_PRODUTO", "alias": "P", "joins": [],
        "fields": {
            "product_id": _field("Código", "P.PRD_ID"), "product": _field("Produto", "P.PRD_DESCRICAO"),
            "group": _field("Grupo", "P.PRD_GRUPO"), "brand": _field("Marca", "P.PRD_MARCA"),
            "status": _field("Status", "P.PRD_STATUS"),
            "minimum_stock": _field("Estoque mínimo", "COALESCE(P.PRD_ESTOQUE_MINIMO, 0)", "number"),
            "sale_price": _field("Preço de venda", "COALESCE(P.PRD_PRECO_VENDA, 0)", "currency"),
            "cost_price": _field("Preço de custo", "COALESCE(P.PRD_PRECO_CUSTO, 0)", "currency"),
            "company": _field("Empresa", "P.PRD_EMPRESA"),
        },
        "filters": {
            "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
            "group": {"label": "Grupo", "field": "group", "operators": ["eq", "in"]},
            "brand": {"label": "Marca", "field": "brand", "operators": ["eq", "in"]},
            "status": {"label": "Status", "field": "status", "operators": ["eq", "in"]},
        }, "groupings": ["group", "brand", "status", "company"],
    },
    "sellers": {
        "label": "Vendedores", "description": "Vendedores sincronizados e seus cadastros.",
        "table": "TB_VENDEDOR", "alias": "V", "distinct": True,
        "joins": ["JOIN TB_PESSOA P ON P.PES_ID = V.VDR_PESSOA", "LEFT JOIN TB_CIDADE CI ON CI.CID_ID = P.PES_CIDADE", "JOIN TB_PEDIDO_VENDA PV ON PV.PEV_VENDEDOR = V.VDR_PESSOA"],
        "fields": {"seller_id": _field("Código", "V.VDR_PESSOA"), "name": _field("Nome", "P.PES_RSOCIAL_NOME"), "city": _field("Cidade", "CI.CID_NOME"), "company": _field("Empresa", "PV.PEV_EMPRESA")},
        "filters": {"company": {"label": "Empresa", "field": "company", "operators": ["eq"]}, "city": {"label": "Cidade", "field": "city", "operators": ["eq", "in"]}},
        "groupings": ["city", "company"],
    },
})
CATALOG["sales"]["planned_sources"] = ["Comissões", "Metas", "Cancelamentos"]

_semantic_layer = BusinessSemanticLayer()
for _category_key, _category in CATALOG.items():
    for _source_key, _source in list(_category["sources"].items()):
        _category["sources"][_source_key] = _semantic_layer.enrich_source(_category_key, _source_key, _source)

READY_TEMPLATES = [
    {"key": "sales_by_product", "name": "Vendas por produto", "description": "Quantidade e valor vendido por produto.", "definition": {"category": "sales", "source": "items", "fields": ["product", "quantity", "total"], "filters": [], "group_by": ["product"], "order_by": [{"field": "total_sum", "direction": "desc"}], "totals": [{"field": "quantity", "aggregation": "sum"}, {"field": "total", "aggregation": "sum"}], "chart": "bar"}},
    {"key": "sales_by_group", "name": "Vendas por grupo", "description": "Faturamento agrupado por grupo de produtos.", "definition": {"category": "sales", "source": "items", "fields": ["group", "total"], "filters": [], "group_by": ["group"], "order_by": [{"field": "total_sum", "direction": "desc"}], "totals": [{"field": "total", "aggregation": "sum"}], "chart": "pie"}},
    {"key": "customer_directory", "name": "Cadastro de clientes", "description": "Clientes organizados por cidade.", "definition": {"category": "sales", "source": "customers", "fields": ["customer_id", "name", "city", "registered_at"], "filters": [], "group_by": [], "order_by": [{"field": "name", "direction": "asc"}], "totals": [], "chart": "table"}},
    {"key": "product_prices", "name": "Tabela de preços", "description": "Preço de venda e custo dos produtos.", "definition": {"category": "sales", "source": "products", "fields": ["product_id", "product", "group", "brand", "sale_price", "cost_price"], "filters": [], "group_by": [], "order_by": [{"field": "product", "direction": "asc"}], "totals": [], "chart": "table"}},
    {"key": "receipts_by_status", "name": "Recebimentos por status", "description": "Valores financeiros agrupados por status.", "definition": {"category": "finance", "source": "receipts", "fields": ["status", "amount"], "filters": [], "group_by": ["status"], "order_by": [{"field": "amount_sum", "direction": "desc"}], "totals": [{"field": "amount", "aggregation": "sum"}], "chart": "cards"}},
]

# Additional entry points use the same validated Builder and AI workspace.
READY_TEMPLATES.extend([
    {"key": "sales_by_brand", "name": "Vendas por marca", "description": "Compare a participação das marcas nas vendas.", "definition": {"category": "sales", "source": "items", "fields": ["brand", "total"], "filters": [], "group_by": ["brand"], "order_by": [{"field": "total_sum", "direction": "desc"}], "totals": [{"field": "total", "aggregation": "sum"}], "chart": "bar"}},
    {"key": "sales_by_seller", "name": "Vendas por vendedor", "description": "Faturamento e quantidade de pedidos por código de vendedor.", "definition": {"category": "sales", "source": "orders", "fields": ["seller_id", "number", "total"], "filters": [], "group_by": ["seller_id"], "order_by": [{"field": "total_sum", "direction": "desc"}], "totals": [{"field": "number", "aggregation": "count"}, {"field": "total", "aggregation": "sum"}], "chart": "bar"}},
    {"key": "daily_sales", "name": "Vendas diárias", "description": "Evolução das vendas por data de emissão.", "definition": {"category": "sales", "source": "orders", "fields": ["date", "total"], "filters": [], "group_by": ["date"], "order_by": [{"field": "date", "direction": "asc"}], "totals": [{"field": "total", "aggregation": "sum"}], "chart": "line"}},
    {"key": "customers_by_city", "name": "Clientes por cidade", "description": "Distribuição geográfica da carteira de clientes.", "definition": {"category": "sales", "source": "customers", "fields": ["city", "customer_id"], "filters": [], "group_by": ["city"], "order_by": [{"field": "customer_id_count", "direction": "desc"}], "totals": [{"field": "customer_id", "aggregation": "count"}], "chart": "bar"}},
    {"key": "receipts_by_due_date", "name": "Carteira por vencimento", "description": "Valores nominais em aberto por data de vencimento.", "definition": {"category": "finance", "source": "receipts", "fields": ["due_date", "amount"], "filters": [{"field": "open", "operator": "eq", "value": "S"}], "group_by": ["due_date"], "order_by": [{"field": "due_date", "direction": "asc"}], "totals": [{"field": "amount", "aggregation": "sum"}], "chart": "line"}},
    {"key": "receipts_by_customer", "name": "Títulos em aberto por cliente", "description": "Valor nominal dos títulos abertos por código de cliente; não desconta baixas parciais.", "definition": {"category": "finance", "source": "receipts", "fields": ["customer_id", "amount"], "filters": [{"field": "open", "operator": "eq", "value": "S"}], "group_by": ["customer_id"], "order_by": [{"field": "amount_sum", "direction": "desc"}], "totals": [{"field": "amount", "aggregation": "sum"}], "chart": "bar"}},
])


class ReportCatalog:
    def sync_metadata(self, db):
        """Mantém o catálogo relacional alinhado ao registro seguro do Engine."""
        db.execute(text("DELETE FROM report_filters"))
        db.execute(text("DELETE FROM report_fields"))
        db.execute(text("DELETE FROM report_sources"))
        for position, (category_key, category) in enumerate(CATALOG.items(), 1):
            db.execute(text("""INSERT INTO report_categories(key,name,position) VALUES (:key,:name,:position)
                ON CONFLICT (key) DO UPDATE SET name=EXCLUDED.name, position=EXCLUDED.position"""),
                {"key": category_key, "name": category["label"], "position": position})
            for source_key, source in category["sources"].items():
                db.execute(text("""INSERT INTO report_sources(category_key,key,name,provider,metadata)
                    VALUES (:category,:key,:name,'firebird',CAST(:metadata AS jsonb))
                    ON CONFLICT (key) DO UPDATE SET name=EXCLUDED.name, metadata=EXCLUDED.metadata"""),
                    {"category": category_key, "key": source_key, "name": source["label"], "metadata": '{}'})
                for field_position, (field_key, field) in enumerate(source["fields"].items(), 1):
                    semantic_metadata = {key: value for key, value in field.items() if key not in {"expression", "aggregations", "type", "label"}}
                    db.execute(text("""INSERT INTO report_fields(source_key,key,label,data_type,aggregations,position,semantic_metadata)
                        VALUES (:source,:key,:label,:type,CAST(:aggregations AS jsonb),:position,CAST(:semantic AS jsonb))
                        ON CONFLICT (source_key,key) DO UPDATE SET label=EXCLUDED.label,data_type=EXCLUDED.data_type,aggregations=EXCLUDED.aggregations,position=EXCLUDED.position,semantic_metadata=EXCLUDED.semantic_metadata"""),
                        {"source": source_key, "key": field_key, "label": field["label"], "type": field["type"], "aggregations": json.dumps(field["aggregations"]), "position": field_position, "semantic": json.dumps(semantic_metadata)})
                for filter_key, filter_meta in source["filters"].items():
                    db.execute(text("""INSERT INTO report_filters(source_key,key,label,data_type,operators,options)
                        VALUES (:source,:key,:label,'select',CAST(:operators AS jsonb),CAST(:options AS jsonb))
                        ON CONFLICT (source_key,key) DO UPDATE SET label=EXCLUDED.label,operators=EXCLUDED.operators,options=EXCLUDED.options"""),
                        {"source": source_key, "key": filter_key, "label": filter_meta["label"], "operators": json.dumps(filter_meta["operators"]), "options": json.dumps(filter_meta.get("options"))})
        db.commit()

    def public_catalog(self):
        result = deepcopy(CATALOG)
        for category in result.values():
            for source in category["sources"].values():
                source.pop("table", None)
                source.pop("alias", None)
                source.pop("joins", None)
                source.pop("company_field", None)
                source.pop("distinct", None)
                for field in source["fields"].values():
                    field.pop("expression", None)
        return result

    def source(self, category: str, source: str):
        category_meta = CATALOG.get(category)
        source_meta = category_meta and category_meta["sources"].get(source)
        if not source_meta:
            raise ValueError("Fonte de dados não disponível no catálogo.")
        return source_meta
