from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.repositories.base_repository import BaseRepository


class BaseDashboardRepository(BaseRepository):
    MONTH_NAMES = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez",
    }

    def _month_label(self, month: int | None) -> str:
        if not month:
            return ""
        return self.MONTH_NAMES.get(int(month), str(month))

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _iso_date(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, (date, datetime)):
            return value.isoformat()

        return str(value)

    def _history_rows_to_series(
        self,
        rows: list[dict[str, Any]],
        value_key: str = "TOTAL",
        month_key: str = "MES",
        extra_keys: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        extra_keys = extra_keys or []
        result: list[dict[str, Any]] = []

        for row in rows:
            item = {
                "label": self._month_label(self._safe_int(row.get(month_key))),
                "valor": self._safe_float(row.get(value_key)),
            }

            for key in extra_keys:
                if key.upper() == "PEDIDOS":
                    item["pedidos"] = self._safe_int(row.get(key))
                else:
                    item[key.lower()] = row.get(key)

            result.append(item)

        return result[-12:]