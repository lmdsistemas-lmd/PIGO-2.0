from datetime import date, timedelta

from app.schemas.report_assistant import ReportIntent
from app.schemas.reporting import ReportDefinition, ReportFilterValue, ReportOrder, ReportTotal
from app.services.report_catalog import ReportCatalog
from app.services.report_query_builder import ReportQueryBuilder


SOURCE_CANDIDATES = {
    "revenue": ["sales.orders", "sales.items"], "sale_count": ["sales.orders"],
    "quantity": ["sales.items"], "customer_count": ["sales.customers"],
    "product_count": ["sales.products"], "receivable": ["finance.receipts"],
    "open_receivable": ["finance.receipts"],
}

METRIC_FIELDS = {
    ("revenue", "orders"): ("total", "sum"), ("revenue", "items"): ("total", "sum"),
    ("sale_count", "orders"): ("number", "count"), ("quantity", "items"): ("quantity", "sum"),
    ("customer_count", "customers"): ("customer_id", "count"),
    ("product_count", "products"): ("product_id", "count"),
    ("receivable", "receipts"): ("amount", "sum"),
    ("open_receivable", "receipts"): ("amount", "sum"),
}

DIMENSION_FIELDS = {
    ("seller", "orders"): "seller_id", ("customer", "orders"): "customer_id",
    ("product", "items"): "product", ("group", "items"): "group", ("brand", "items"): "brand",
    ("customer", "receipts"): "customer_id", ("city", "customers"): "city",
    ("seller", "customers"): "seller_id", ("group", "products"): "group",
    ("brand", "products"): "brand", ("city", "sellers"): "city",
}

FILTER_FIELDS = {
    "seller": "seller_id", "customer": "customer_id", "city": "city", "group": "group",
    "brand": "brand", "amount": "total",
}


class ReportIntentToDefinitionService:
    def __init__(self, catalog=None):
        self.catalog = catalog or ReportCatalog()
        self.builder = ReportQueryBuilder(self.catalog)

    def convert(self, intent: ReportIntent, empresa_id: int) -> ReportDefinition:
        category, source_key = self._select_source(intent)
        source = self.catalog.source(category, source_key)
        dimensions = [DIMENSION_FIELDS[(item, source_key)] for item in intent.dimensions]
        totals = []
        for metric in intent.metrics:
            field, aggregation = METRIC_FIELDS[(metric, source_key)]
            totals.append(ReportTotal(field=field, aggregation=aggregation))

        filters = self._filters(intent, source_key, source)
        if intent.period:
            if "period" not in source["filters"]:
                raise ValueError("A fonte escolhida não suporta filtro de período.")
            filters.append(ReportFilterValue(field="period", operator="between", value=list(self._period_range(intent.period["type"]))))
        if "open_receivable" in intent.metrics:
            filters.append(ReportFilterValue(field="open", operator="eq", value="S"))

        fields = list(dict.fromkeys(dimensions + [item.field for item in totals]))
        if not fields:
            raise ValueError("A intenção não possui campos executáveis.")
        order_by = []
        if totals:
            first = totals[0]
            order_by = [ReportOrder(field=f"{first.field}_{first.aggregation}", direction="desc")]
        definition = ReportDefinition(
            category=category, source=source_key, fields=fields, filters=filters,
            group_by=dimensions, totals=totals, order_by=order_by,
            chart=intent.visualization,
        )
        self.builder.validate(definition)
        return definition

    def _select_source(self, intent: ReportIntent) -> tuple[str, str]:
        candidates = None
        for metric in intent.metrics:
            metric_sources = SOURCE_CANDIDATES.get(metric, [])
            candidates = list(metric_sources) if candidates is None else [item for item in candidates if item in metric_sources]
        if candidates is None:
            candidates = list(dict.fromkeys(source for obj in intent.objects for source in self._object_sources(obj)))
        for candidate in candidates:
            category, source = candidate.split(".", 1)
            if all((dimension, source) in DIMENSION_FIELDS for dimension in intent.dimensions):
                return category, source
        raise ValueError("Nenhuma fonte disponível combina os conceitos solicitados.")

    @staticmethod
    def _object_sources(object_id: str) -> list[str]:
        defaults = {"customer": ["sales.customers"], "product": ["sales.products"], "seller": ["sales.sellers"]}
        return defaults.get(object_id, [])

    @staticmethod
    def _filters(intent, source_key, source):
        result = []
        for item in intent.filters:
            field = FILTER_FIELDS.get(item.concept)
            if not field or field not in source["filters"]:
                raise ValueError(f"Filtro de {item.concept} não é suportado pela fonte escolhida.")
            result.append(ReportFilterValue(field=field, operator=item.operator, value=item.value))
        return result

    @staticmethod
    def _period_range(period: str) -> tuple[str, str]:
        today = date.today()
        if period == "today": start = end = today
        elif period == "yesterday": start = end = today - timedelta(days=1)
        elif period == "current_week": start, end = today - timedelta(days=today.weekday()), today
        elif period == "last_week": end = today - timedelta(days=today.weekday() + 1); start = end - timedelta(days=6)
        elif period == "current_month": start, end = today.replace(day=1), today
        elif period == "previous_month": end = today.replace(day=1) - timedelta(days=1); start = end.replace(day=1)
        elif period in {"current_quarter", "last_quarter"}:
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            current_start = date(today.year, quarter_start_month, 1)
            if period == "current_quarter": start, end = current_start, today
            else: end = current_start - timedelta(days=1); start = date(end.year, ((end.month - 1) // 3) * 3 + 1, 1)
        elif period == "current_year": start, end = date(today.year, 1, 1), today
        elif period == "previous_year": start, end = date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        elif period.startswith("last_") and period.endswith("_days"):
            days = int(period.split("_")[1]); start, end = today - timedelta(days=days - 1), today
        else: raise ValueError("Período não suportado.")
        return start.isoformat(), end.isoformat()
