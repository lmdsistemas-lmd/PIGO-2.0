import re

from app.ai.schemas.intent import ReportIntent, ReportIntentFilter
from app.services.business_knowledge_layer import BUSINESS_METRICS, BUSINESS_OBJECTS, BusinessKnowledgeLayer, _normalize


PERIODS = [
    ("ultimos 90 dias", "last_90_days"), ("ultimos 30 dias", "last_30_days"),
    ("ultimos 7 dias", "last_7_days"), ("semana passada", "last_week"),
    ("ultimo trimestre", "last_quarter"), ("este trimestre", "current_quarter"),
    ("mes passado", "previous_month"), ("ultimo mes", "previous_month"),
    ("este mes", "current_month"), ("ano passado", "previous_year"),
    ("este ano", "current_year"), ("esta semana", "current_week"),
    ("ontem", "yesterday"), ("hoje", "today"),
]

UNSAFE_PATTERNS = (
    r"\bselect\b", r"\bjoin\b", r"\bwhere\b", r"\binsert\b", r"\bupdate\b",
    r"\bdelete\b", r"\bdrop\b", r"\btb_[a-z0-9_]+\b", r"\bpev_[a-z0-9_]+\b",
    r"ignore (as |todas as )?(regras|permissoes)", r"banco (de dados|diretamente)",
)


class UnsafeReportRequest(ValueError):
    pass


class DeterministicIntentParser:
    def __init__(self):
        self.knowledge = BusinessKnowledgeLayer()

    def parse(self, prompt: str, answers: dict[str, str] | None = None) -> tuple[ReportIntent, float]:
        text = _normalize(prompt)
        if not text:
            raise ValueError("Informe o relatório que deseja criar.")
        if any(re.search(pattern, text) for pattern in UNSAFE_PATTERNS):
            raise UnsafeReportRequest("A solicitação contém instruções técnicas ou tentativa de ignorar regras.")

        objects = self.knowledge._match(text, BUSINESS_OBJECTS)
        metrics = self.knowledge._match(text, BUSINESS_METRICS)
        dimensions = self._dimensions(text)
        period = next(({"type": value} for phrase, value in PERIODS if phrase in text), None)

        if "payment" in objects and "payment" not in metrics:
            metrics.append("payment")
        if not metrics:
            if "customer" in objects:
                metrics.append("customer_count")
            elif "product" in objects:
                metrics.append("product_count")
        objects = sorted(set(objects) | {BUSINESS_METRICS[key]["object"] for key in metrics if key in BUSINESS_METRICS})

        answers = answers or {}
        if "city" in dimensions and answers.get("city_context"):
            city_owner = answers["city_context"].removesuffix("_city")
            objects = sorted(set(objects) | {city_owner})

        filters = self._filters(text)
        confidence = 0.35 + (0.3 if metrics else 0) + (0.15 if dimensions else 0) + (0.1 if period else 0) + (0.1 if objects else 0)
        category = "finance" if any(item in {"receipt", "payment"} for item in objects) else "sales"
        return ReportIntent(
            category=category,
            objects=objects,
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            period=period,
            sort=[{"field": metrics[0], "direction": "desc"}] if metrics else [],
            visualization=self._visualization(metrics, dimensions),
        ), min(confidence, 0.99)

    def _dimensions(self, text: str) -> list[str]:
        if " por " not in f" {text} ":
            return []
        tail = text.split(" por ", 1)[1]
        for phrase, _ in PERIODS:
            tail = tail.split(phrase, 1)[0]
        return self.knowledge._match(tail, BUSINESS_OBJECTS)

    @staticmethod
    def _filters(text: str) -> list[ReportIntentFilter]:
        filters = []
        patterns = [
            (r"(?:do|pelo) vendedor ([\w\s.-]+?)(?=\s+(?:deste|este|no|na|nos|ultimos|ultimo|acima|abaixo)\b|$)", "seller"),
            (r"clientes? de ([\w\s.-]+?)(?=\s+(?:deste|este|no|na|nos|ultimos|ultimo)\b|$)", "city"),
            (r"produtos? do grupo ([\w\s.-]+?)(?=\s+(?:deste|este|no|na|nos|ultimos|ultimo)\b|$)", "group"),
        ]
        for pattern, concept in patterns:
            match = re.search(pattern, text)
            if match:
                filters.append(ReportIntentFilter(concept=concept, value=match.group(1).strip(), requires_resolution=concept == "seller"))
        amount = re.search(r"acima de r?\$?\s*([\d.]+(?:,\d+)?)", text)
        if amount:
            value = float(amount.group(1).replace(".", "").replace(",", "."))
            filters.append(ReportIntentFilter(concept="amount", operator="gte", value=value))
        return filters

    @staticmethod
    def _visualization(metrics: list[str], dimensions: list[str]) -> str:
        if metrics and dimensions:
            return "bar"
        if metrics:
            return "cards"
        return "table"
