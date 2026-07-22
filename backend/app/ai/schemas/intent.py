"""Contratos públicos e independentes de fornecedor para o assistente."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.reporting import ReportDefinition


class ReportAssistantInterpretInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    company_id: int = Field(gt=0)
    answers: dict[str, str] = Field(default_factory=dict)


class ReportIntentFilter(BaseModel):
    concept: str
    operator: Literal["eq", "gte", "lte", "in"] = "eq"
    value: Any
    requires_resolution: bool = False


class ReportIntent(BaseModel):
    intent_version: int = 1
    category: str
    source: str | None = None
    objects: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[ReportIntentFilter] = Field(default_factory=list)
    period: dict[str, str] | None = None
    sort: list[dict[str, str]] = Field(default_factory=list)
    visualization: str = "table"


class ReportAssistantResult(BaseModel):
    success: bool
    code: str
    intent: ReportIntent | None = None
    report_definition: ReportDefinition | None = None
    confidence: float = 0
    warnings: list[dict | str] = Field(default_factory=list)
    questions: list[dict] = Field(default_factory=list)
    unavailable_concepts: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    message: str | None = None
    request_id: str = ""
