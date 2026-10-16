from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LicenseControlTenant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = Field(min_length=1, max_length=100)
    company_id: str = Field(min_length=1, max_length=100)
    empresa: str = Field(min_length=1, max_length=255)
    nome_fantasia: str | None = Field(default=None, max_length=255)
    cnpj: str = Field(min_length=1, max_length=30)
    produto: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=30)
    validade: datetime | None = None
    ativo: bool
    updated_at: datetime

    @field_validator("tenant_id", "company_id", "empresa", "produto", "status")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("campo nao pode ser vazio")
        return value

    @field_validator("nome_fantasia")
    @classmethod
    def empty_trade_name_as_none(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class LicenseControlSyncEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenants: list[dict[str, Any]]


class LicenseControlSyncResponse(BaseModel):
    success: bool
    received: int
    created: int
    updated: int
    disabled: int
    ignored: int
    errors: list[dict[str, Any]]
    processing_time: int
    action: str | None = None
