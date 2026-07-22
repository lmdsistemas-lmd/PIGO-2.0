from copy import deepcopy
import json
from sqlalchemy import text


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
                    "quantity": _field("Quantidade", "COALESCE(PV.PEV_QT_ITENS, 0)", "number"),
                    "total": _field("Valor", "COALESCE(PV.PEV_VALOR_TOTAL, 0)", "currency"),
                    "discount": _field("Desconto", "COALESCE(PV.PEV_DESCONTO, 0)", "currency"),
                    "company": _field("Empresa", "PV.PEV_EMPRESA"),
                },
                "filters": {
                    "company": {"label": "Empresa", "field": "company", "operators": ["eq"]},
                    "period": {"label": "Período", "field": "date", "operators": ["between"]},
                    "status": {"label": "Status", "field": "status", "operators": ["eq", "in"]},
                    "customer_id": {"label": "Cliente", "field": "customer_id", "operators": ["eq", "in"]},
                    "seller_id": {"label": "Vendedor", "field": "seller_id", "operators": ["eq", "in"]},
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


class ReportCatalog:
    def sync_metadata(self, db):
        """Mantém o catálogo relacional alinhado ao registro seguro do Engine."""
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
                    db.execute(text("""INSERT INTO report_fields(source_key,key,label,data_type,aggregations,position)
                        VALUES (:source,:key,:label,:type,CAST(:aggregations AS jsonb),:position)
                        ON CONFLICT (source_key,key) DO UPDATE SET label=EXCLUDED.label,data_type=EXCLUDED.data_type,aggregations=EXCLUDED.aggregations,position=EXCLUDED.position"""),
                        {"source": source_key, "key": field_key, "label": field["label"], "type": field["type"], "aggregations": json.dumps(field["aggregations"]), "position": field_position})
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
                for field in source["fields"].values():
                    field.pop("expression", None)
        return result

    def source(self, category: str, source: str):
        category_meta = CATALOG.get(category)
        source_meta = category_meta and category_meta["sources"].get(source)
        if not source_meta:
            raise ValueError("Fonte de dados não disponível no catálogo.")
        return source_meta
