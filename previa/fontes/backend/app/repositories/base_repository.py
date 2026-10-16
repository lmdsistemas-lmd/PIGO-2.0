from __future__ import annotations

from typing import Any

from app.services.erp_query_service import ERPQueryService


class BaseRepository:
    def __init__(self) -> None:
        self.erp = ERPQueryService()

    def _scalar(self, sql: str, params: dict[str, Any]) -> float:
        return self.erp.scalar(sql, params)

    def _fetch_all(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self.erp.fetch_all(sql, params)

    def _fetch_one(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        return self.erp.fetch_one(sql, params)

    def _empresa_filter(
        self,
        field_name: str,
        empresa_id: int | None,
    ) -> tuple[str, dict[str, Any]]:
        return self.erp.empresa_filter(field_name, empresa_id)