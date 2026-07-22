import re
import unicodedata
from copy import deepcopy


BUSINESS_OBJECTS = {
    "sale": {"name": "Venda", "description": "Operação comercial realizada com um cliente.", "sources": ["sales.orders", "sales.items"], "synonyms": ["venda", "vendas", "pedido", "pedidos", "faturamento"]},
    "customer": {"name": "Cliente", "description": "Pessoa ou empresa que compra produtos.", "sources": ["sales.customers"], "synonyms": ["cliente", "clientes", "consumidor", "comprador", "pessoa"]},
    "product": {"name": "Produto", "description": "Item comercializado pela empresa.", "sources": ["sales.products", "sales.items"], "synonyms": ["produto", "produtos", "item", "itens", "mercadoria"]},
    "receipt": {"name": "Recebimento", "description": "Título financeiro a receber de um cliente.", "sources": ["finance.receipts"], "synonyms": ["recebimento", "recebimentos", "conta a receber", "titulo a receber"]},
    "payment": {"name": "Pagamento", "description": "Compromisso financeiro a pagar.", "sources": [], "planned": True, "synonyms": ["pagamento", "pagamentos", "conta a pagar", "despesa"]},
    "seller": {"name": "Vendedor", "description": "Responsável comercial por uma venda ou cliente.", "sources": ["sales.sellers", "sales.orders"], "synonyms": ["vendedor", "vendedores", "representante", "consultor"]},
    "company": {"name": "Empresa", "description": "Empresa ERP proprietária dos dados.", "sources": [], "synonyms": ["empresa", "filial", "unidade"]},
    "city": {"name": "Cidade", "description": "Localidade associada a uma entidade de negócio.", "sources": ["sales.customers", "sales.sellers"], "synonyms": ["cidade", "municipio", "localidade"]},
    "group": {"name": "Grupo", "description": "Família comercial de produtos.", "sources": ["sales.products", "sales.items"], "synonyms": ["grupo", "grupo de produto", "familia"]},
    "brand": {"name": "Marca", "description": "Marca comercial de um produto.", "sources": ["sales.products", "sales.items"], "synonyms": ["marca", "fabricante"]},
}

BUSINESS_RELATIONS = [
    {"from": "sale", "to": "customer", "cardinality": "many_to_one"},
    {"from": "sale", "to": "product", "cardinality": "many_to_many", "through": "sales.items"},
    {"from": "sale", "to": "seller", "cardinality": "many_to_one"},
    {"from": "sale", "to": "company", "cardinality": "many_to_one"},
    {"from": "customer", "to": "city", "cardinality": "many_to_one"},
    {"from": "customer", "to": "seller", "cardinality": "many_to_one"},
    {"from": "seller", "to": "city", "cardinality": "many_to_one"},
    {"from": "product", "to": "group", "cardinality": "many_to_one"},
    {"from": "product", "to": "brand", "cardinality": "many_to_one"},
    {"from": "receipt", "to": "customer", "cardinality": "many_to_one"},
    {"from": "receipt", "to": "company", "cardinality": "many_to_one"},
]

BUSINESS_METRICS = {
    "revenue": {"name": "Faturamento", "object": "sale", "format": "currency", "definition": {"source": "sales.orders", "field": "total", "aggregation": "sum"}, "synonyms": ["faturamento", "receita", "valor vendido", "total vendido", "vendas"]},
    "average_ticket": {"name": "Ticket médio", "object": "sale", "format": "currency", "formula": "revenue / sale_count", "dependencies": ["revenue", "sale_count"], "synonyms": ["ticket medio", "valor medio da venda"]},
    "sale_count": {"name": "Quantidade de vendas", "object": "sale", "format": "integer", "definition": {"source": "sales.orders", "field": "number", "aggregation": "count"}, "synonyms": ["quantidade de vendas", "numero de vendas", "pedidos"]},
    "quantity": {"name": "Quantidade vendida", "object": "product", "format": "decimal", "definition": {"source": "sales.items", "field": "quantity", "aggregation": "sum"}, "synonyms": ["quantidade", "volume vendido", "itens vendidos"]},
    "customer_count": {"name": "Quantidade de clientes", "object": "customer", "format": "integer", "definition": {"source": "sales.customers", "field": "customer_id", "aggregation": "count"}, "synonyms": ["quantidade de clientes", "numero de clientes"]},
    "product_count": {"name": "Quantidade de produtos", "object": "product", "format": "integer", "definition": {"source": "sales.products", "field": "product_id", "aggregation": "count"}, "synonyms": ["quantidade de produtos", "numero de produtos"]},
    "gross_profit": {"name": "Lucro bruto", "object": "sale", "format": "currency", "formula": "revenue - cost_of_goods", "dependencies": ["revenue", "cost_of_goods"], "synonyms": ["lucro", "lucro bruto"]},
    "margin": {"name": "Margem", "object": "sale", "format": "percentage", "formula": "gross_profit / revenue * 100", "dependencies": ["gross_profit", "revenue"], "synonyms": ["margem", "margem de lucro", "lucratividade"]},
    "markup": {"name": "Markup", "object": "sale", "format": "percentage", "formula": "gross_profit / cost_of_goods * 100", "dependencies": ["gross_profit", "cost_of_goods"], "synonyms": ["markup"]},
    "cost_of_goods": {"name": "CMV", "object": "sale", "format": "currency", "definition": {"source": "sales.items", "field": "unit_cost", "aggregation": "sum_product_quantity"}, "synonyms": ["cmv", "custo", "custo da mercadoria vendida"]},
    "receivable": {"name": "A receber", "object": "receipt", "format": "currency", "definition": {"source": "finance.receipts", "field": "amount", "aggregation": "sum"}, "synonyms": ["a receber", "contas a receber", "recebiveis"]},
    "open_receivable": {"name": "Em aberto", "object": "receipt", "format": "currency", "definition": {"source": "finance.receipts", "field": "amount", "aggregation": "sum", "filters": [{"field": "open", "operator": "eq", "value": "S"}]}, "synonyms": ["em aberto", "saldo aberto", "nao recebido"]},
    "delinquency": {"name": "Inadimplência", "object": "receipt", "format": "currency", "planned": True, "dependencies": ["open_receivable"], "synonyms": ["inadimplencia", "vencido", "vencidos", "atrasado", "atrasados"]},
    "average_term": {"name": "Prazo médio", "object": "receipt", "format": "days", "planned": True, "synonyms": ["prazo medio", "tempo medio de recebimento"]},
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return re.sub(r"\s+", " ", "".join(char for char in value if not unicodedata.combining(char))).strip()


class BusinessKnowledgeLayer:
    def public_model(self) -> dict:
        return {
            "version": "1.0",
            "objects": deepcopy(BUSINESS_OBJECTS),
            "relations": deepcopy(BUSINESS_RELATIONS),
            "metrics": deepcopy(BUSINESS_METRICS),
        }

    def validate(self, *, objects=None, metrics=None, dimensions=None) -> dict:
        requested = {"objects": objects or [], "metrics": metrics or [], "dimensions": dimensions or []}
        errors, warnings, dependencies = [], [], set()
        for object_id in requested["objects"]:
            if object_id not in BUSINESS_OBJECTS:
                errors.append({"code": "UNKNOWN_OBJECT", "concept": object_id, "message": "Objeto de negócio não reconhecido."})
            elif BUSINESS_OBJECTS[object_id].get("planned"):
                errors.append({"code": "OBJECT_NOT_AVAILABLE", "concept": object_id, "message": "Objeto planejado, mas ainda sem fonte disponível."})
        for metric_id in requested["metrics"]:
            metric = BUSINESS_METRICS.get(metric_id)
            if not metric:
                errors.append({"code": "UNKNOWN_METRIC", "concept": metric_id, "message": "Métrica de negócio não reconhecida."})
                continue
            dependencies.update(metric.get("dependencies", []))
            dependencies.add(metric["object"])
            if metric.get("planned"):
                errors.append({"code": "METRIC_NOT_AVAILABLE", "concept": metric_id, "message": "Métrica conhecida, mas ainda não executável."})
        for dimension_id in requested["dimensions"]:
            if dimension_id not in BUSINESS_OBJECTS:
                errors.append({"code": "UNKNOWN_DIMENSION", "concept": dimension_id, "message": "Dimensão de negócio não reconhecida."})
                continue
            parents = sorted({relation["from"] for relation in BUSINESS_RELATIONS if relation["to"] == dimension_id})
            if len(parents) > 1 and not set(parents).intersection(requested["objects"]):
                warnings.append({"code": "AMBIGUOUS_DIMENSION", "concept": dimension_id, "options": parents, "message": "A dimensão pertence a mais de um objeto; informe o contexto desejado."})
        return {"valid": not errors and not warnings, "requested": requested, "dependencies": sorted(dependencies), "errors": errors, "warnings": warnings}

    def parse_intent(self, text: str) -> dict:
        normalized = _normalize(text)
        objects = self._match(normalized, BUSINESS_OBJECTS)
        metrics = self._match(normalized, BUSINESS_METRICS)
        dimensions = []
        if " por " in f" {normalized} ":
            tail = normalized.split(" por ", 1)[1]
            dimensions = self._match(tail, BUSINESS_OBJECTS)
        if not objects:
            objects = sorted({BUSINESS_METRICS[key]["object"] for key in metrics})
        validation = self.validate(objects=objects, metrics=metrics, dimensions=dimensions)
        return {"text": text, "intent": {"objects": objects, "metrics": metrics, "dimensions": dimensions, "filters": [], "period": self._period(normalized)}, "validation": validation, "requires_confirmation": not validation["valid"]}

    @staticmethod
    def _match(text: str, registry: dict) -> list[str]:
        matches = []
        for key, metadata in registry.items():
            terms = [_normalize(metadata["name"]), *[_normalize(item) for item in metadata.get("synonyms", [])]]
            if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) for term in terms):
                matches.append(key)
        return matches

    @staticmethod
    def _period(text: str):
        periods = {"ultimo trimestre": "last_quarter", "este mes": "current_month", "mes atual": "current_month", "mes anterior": "previous_month", "ultimo mes": "previous_month", "este ano": "current_year"}
        return next((value for term, value in periods.items() if term in text), None)
