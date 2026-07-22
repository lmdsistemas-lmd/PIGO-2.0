from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


Category = Literal["sales", "finance", "accounting", "other"]
ChartType = Literal["table", "cards", "bar", "line", "pie", "area"]


class ReportFilterValue(BaseModel):
    field: str
    operator: Literal["eq", "in", "between", "gte", "lte"] = "eq"
    value: Any


class ReportOrder(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"


class ReportTotal(BaseModel):
    field: str
    aggregation: Literal["sum", "avg", "min", "max", "count"]


class ReportDefinition(BaseModel):
    category: Category
    source: str
    fields: list[str] = Field(min_length=1, max_length=30)
    filters: list[ReportFilterValue] = []
    group_by: list[str] = []
    order_by: list[ReportOrder] = []
    totals: list[ReportTotal] = []
    chart: ChartType = "table"

    @model_validator(mode="after")
    def unique_fields(self):
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("Campos duplicados não são permitidos.")
        return self


class ReportTemplateInput(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1000)
    definition: ReportDefinition
    permissions: list[str] = ["all"]


class ReportPreviewInput(BaseModel):
    definition: ReportDefinition
    empresa_id: int = Field(gt=0)
    limit: int = Field(default=50, ge=1, le=50)


class ReportExportInput(ReportPreviewInput):
    format: Literal["pdf", "excel", "csv"]
    template_id: UUID | None = None


class BusinessValidationInput(BaseModel):
    objects: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)


class BusinessIntentInput(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
