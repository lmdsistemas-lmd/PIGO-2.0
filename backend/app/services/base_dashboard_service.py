from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass
class DateRange:
    start: date
    end: date


class BaseDashboardService:
    def _resolve_period(
        self,
        period: str,
        start: str | None,
        end: str | None,
    ) -> DateRange:
        today = date.today()

        if period == "today":
            return DateRange(start=today, end=today)

        if period == "yesterday":
            previous_day = today - timedelta(days=1)
            return DateRange(start=previous_day, end=previous_day)

        if period == "week":
            week_start = today - timedelta(days=today.weekday())
            return DateRange(start=week_start, end=today)

        if period == "month":
            month_start = today.replace(day=1)
            return DateRange(start=month_start, end=today)

        if period == "previousMonth":
            first_day_current_month = today.replace(day=1)
            last_day_previous_month = first_day_current_month - timedelta(days=1)
            first_day_previous_month = last_day_previous_month.replace(day=1)
            return DateRange(start=first_day_previous_month, end=last_day_previous_month)

        if period == "year":
            year_start = today.replace(month=1, day=1)
            return DateRange(start=year_start, end=today)

        if period == "custom" and start and end:
            return DateRange(
                start=datetime.strptime(start, "%Y-%m-%d").date(),
                end=datetime.strptime(end, "%Y-%m-%d").date(),
            )

        month_start = today.replace(day=1)
        return DateRange(start=month_start, end=today)

    def _previous_period(self, date_range: DateRange) -> DateRange:
        total_days = (date_range.end - date_range.start).days + 1
        previous_end = date_range.start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=total_days - 1)
        return DateRange(start=previous_start, end=previous_end)

    def _format_variation(self, current_value: float, previous_value: float) -> str:
        if previous_value <= 0:
            return "Sem base anterior"

        variation = ((current_value - previous_value) / previous_value) * 100
        prefix = "+" if variation >= 0 else ""
        value = f"{variation:.1f}".replace(".", ",")
        return f"{prefix}{value}% frente ao periodo anterior"

    def _load_sync_data(self) -> dict | None:
        from app.database.erp_connection import current_cnpj
        import os
        import json
        
        import re
        cnpj = re.sub(r"\D", "", str(current_cnpj.get()))
        sync_dir = "sync_data"
        
        print(f"[DEBUG SYNC] Carregando dados para CNPJ: {cnpj}")
        
        data = {}
        found = False
        
        if os.path.exists(sync_dir):
            for filename in os.listdir(sync_dir):
                if filename.startswith(cnpj) and filename.endswith(".json"):
                    print(f"[DEBUG SYNC] Arquivo encontrado: {filename}")
                    try:
                        with open(os.path.join(sync_dir, filename), "r", encoding="utf-8") as f:
                            file_data = json.load(f)
                            data[file_data["type"]] = file_data["content"]
                            found = True
                    except Exception as e:
                        print(f"[DEBUG SYNC] Erro ao ler arquivo {filename}: {e}")
                        continue
        else:
            print(f"[DEBUG SYNC] Diretorio {sync_dir} nao encontrado.")
        
        return data if found else None

    def _apply_sync_data(self, sync_data: dict, report_type: str) -> dict:
        # Este método deve ser sobrescrito pelos serviços específicos
        return {}