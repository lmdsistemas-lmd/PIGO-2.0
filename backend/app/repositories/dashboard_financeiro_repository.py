from __future__ import annotations

from typing import Any
import unicodedata
from datetime import date

from app.repositories.base_dashboard_repository import BaseDashboardRepository
from app.services.base_dashboard_service import DateRange


class DashboardFinanceiroRepository(BaseDashboardRepository):
    # =========================
    # Helpers
    # =========================

    def _normalize_city_name(self, value: str | None) -> str:
        if not value:
            return ""

        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.upper().strip()
        normalized = " ".join(normalized.split())
        return normalized

    def _get_city_position(self, city_name: str) -> dict[str, Any]:
        map_positions = {
            "SAO PAULO": {"x": 312, "y": 202, "cor": "#1d4ed8"},
            "RIO DE JANEIRO": {"x": 338, "y": 214, "cor": "#0f766e"},
            "BELO HORIZONTE": {"x": 318, "y": 182, "cor": "#2563eb"},
            "CURITIBA": {"x": 290, "y": 248, "cor": "#f59e0b"},
            "GOIANIA": {"x": 270, "y": 176, "cor": "#06b6d4"},
            "PORTO ALEGRE": {"x": 268, "y": 286, "cor": "#ef4444"},
            "SALVADOR": {"x": 350, "y": 185, "cor": "#7c3aed"},
            "BRASILIA": {"x": 284, "y": 170, "cor": "#0891b2"},
            "CAMPINAS": {"x": 304, "y": 198, "cor": "#2563eb"},
            "SANTOS": {"x": 316, "y": 216, "cor": "#0ea5e9"},
            "LEOPOLDINA": {"x": 345, "y": 188, "cor": "#1d4ed8"},
            "CATAGUASES": {"x": 337, "y": 183, "cor": "#0f766e"},
            "SAO JOAO NEPOMUCENO": {"x": 324, "y": 191, "cor": "#7c3aed"},
            "ALEM PARAIBA": {"x": 360, "y": 182, "cor": "#2563eb"},
            "MURIAE": {"x": 346, "y": 198, "cor": "#f59e0b"},
            "MAR DE ESPANHA": {"x": 318, "y": 196, "cor": "#06b6d4"},
            "RECREIO": {"x": 352, "y": 191, "cor": "#ef4444"},
            "ASTOLFO DUTRA": {"x": 333, "y": 189, "cor": "#0ea5e9"},
            "RIO NOVO": {"x": 316, "y": 187, "cor": "#0891b2"},
            "NAO INFORMADA": {"x": 250, "y": 160, "cor": "#64748b"},
        }

        return map_positions.get(
            self._normalize_city_name(city_name),
            {"x": 250, "y": 160, "cor": "#64748b"},
        )

    def _receber_valor_aberto_sql(self, alias: str, ref_date_sql: str = "CURRENT_DATE") -> str:
        return f"""
            CASE {alias}.REC_ABERTO
                WHEN 'S' THEN (
                    SELECT COALESCE(A.VALOR_ABERTO, 0)
                    FROM SP_RECEBIMENTO_ABERTO(
                        {alias}.REC_EMPRESA,
                        {alias}.REC_ID,
                        {ref_date_sql}
                    ) A
                )
                ELSE 0
            END
        """

    def _pagamento_valor_aberto_sql(self, alias: str, ref_date_sql: str = "CURRENT_DATE") -> str:
        return f"""
            CASE {alias}.PAG_ABERTO
                WHEN 'S' THEN (
                    SELECT COALESCE(A.VALOR_ABERTO, 0)
                    FROM SP_PAGAMENTO_ABERTO(
                        {alias}.PAG_EMPRESA,
                        {alias}.PAG_ID,
                        {ref_date_sql}
                    ) A
                )
                ELSE 0
            END
        """

    def _receber_metric_sql(self, alias: str, report_type: str) -> tuple[str, str, str]:
        valor_aberto_sql = self._receber_valor_aberto_sql(alias, "CURRENT_DATE")

        if report_type == "faturado":
            valor_sql = (
                f"(CAST(COALESCE({alias}.REC_VALOR, 0) AS NUMERIC(18,2)) - ({valor_aberto_sql}))"
            )
            filtro_sql = f"COALESCE({alias}.REC_STATUS, '') IN ('PB', 'BX')"
            data_sql = f"{alias}.REC_DT_EMISSAO BETWEEN :start_date AND :end_date"
        else:
            valor_sql = valor_aberto_sql
            filtro_sql = f"COALESCE({alias}.REC_STATUS, '') IN ('AB', 'PB')"
            data_sql = f"{alias}.REC_DT_EMISSAO BETWEEN :start_date AND :end_date"

        return valor_sql, filtro_sql, data_sql

    def _pagar_metric_sql(self, alias: str, report_type: str) -> tuple[str, str, str]:
        valor_aberto_sql = self._pagamento_valor_aberto_sql(alias, ":end_date")

        if report_type == "faturado":
            valor_sql = (
                f"(CAST(COALESCE({alias}.PAG_VALOR, 0) AS NUMERIC(18,2)) - ({valor_aberto_sql}))"
            )
            filtro_sql = f"COALESCE({alias}.PAG_STATUS, '') IN ('PB', 'BX')"
            data_sql = f"{alias}.PAG_DT_VENCIMENTO BETWEEN :start_date AND :end_date"
        else:
            valor_sql = valor_aberto_sql
            filtro_sql = f"COALESCE({alias}.PAG_STATUS, '') IN ('AB', 'PB')"
            data_sql = f"{alias}.PAG_DT_VENCIMENTO BETWEEN :start_date AND :end_date"

        return valor_sql, filtro_sql, data_sql

    # =========================
    # Totais
    # =========================

    def get_contas_receber_total(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> float:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_sql, filtro_sql, data_sql = self._receber_metric_sql("R", report_type)

        sql = f"""
            SELECT COALESCE(
                SUM(CAST({valor_sql} AS NUMERIC(18,2))),
                0
            ) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE {data_sql}
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._scalar(sql, params)

    def get_contas_pagar_total(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> float:
        empresa_sql, empresa_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)
        valor_sql, filtro_sql, data_sql = self._pagar_metric_sql("P", report_type)

        sql = f"""
            SELECT COALESCE(
                SUM(CAST({valor_sql} AS NUMERIC(18,2))),
                0
            ) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE {data_sql}
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._scalar(sql, params)

    def get_total_receber_vencido(
        self,
        empresa_id: int | None,
        report_type: str,
    ) -> float:
        if report_type == "faturado":
            return 0.0

        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_aberto_sql = self._receber_valor_aberto_sql("R", "CURRENT_DATE")

        sql = f"""
            SELECT COALESCE(
                SUM(CAST({valor_aberto_sql} AS NUMERIC(18,2))),
                0
            ) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE COALESCE(R.REC_STATUS, '') IN ('AB', 'PB')
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND R.REC_DT_VENCIMENTO < CURRENT_DATE
              AND CAST({valor_aberto_sql} AS NUMERIC(18,2)) > 0
              {empresa_sql}
        """

        return self._scalar(sql, empresa_params)

    def get_total_recebido_periodo(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> float:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_aberto_sql = self._receber_valor_aberto_sql("R", "CURRENT_DATE")

        sql = f"""
            SELECT COALESCE(
                SUM(
                    CAST(
                        (
                            CAST(COALESCE(R.REC_VALOR, 0) AS NUMERIC(18,2)) -
                            CAST({valor_aberto_sql} AS NUMERIC(18,2))
                        ) AS NUMERIC(18,2)
                    )
                ),
                0
            ) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE R.REC_DT_EMISSAO BETWEEN :start_date AND :end_date
              AND COALESCE(R.REC_STATUS, '') IN ('PB', 'BX')
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._scalar(sql, params)

    def get_total_pago_periodo(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> float:
        empresa_sql, empresa_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)
        valor_aberto_sql = self._pagamento_valor_aberto_sql("P", ":end_date")

        sql = f"""
            SELECT COALESCE(
                SUM(
                    CAST(
                        (
                            CAST(COALESCE(P.PAG_VALOR, 0) AS NUMERIC(18,2)) -
                            CAST({valor_aberto_sql} AS NUMERIC(18,2))
                        ) AS NUMERIC(18,2)
                    )
                ),
                0
            ) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE P.PAG_DT_VENCIMENTO BETWEEN :start_date AND :end_date
              AND COALESCE(P.PAG_STATUS, '') IN ('PB', 'BX')
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._scalar(sql, params)

    # =========================
    # Highlights / History
    # =========================

    def get_contas_pagar_highlight(
        self,
        empresa_id: int | None,
        report_type: str,
    ) -> str:
        empresa_sql, empresa_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)

        if report_type == "faturado":
            valor_aberto_sql = self._pagamento_valor_aberto_sql("P", "CURRENT_DATE")
            valor_sql = (
                f"(CAST(COALESCE(P.PAG_VALOR, 0) AS NUMERIC(18,2)) - ({valor_aberto_sql}))"
            )
            filtro_sql = "COALESCE(P.PAG_STATUS, '') IN ('PB', 'BX')"

            sql = f"""
                SELECT COUNT(*) AS TOTAL
                FROM TB_PAGAMENTO P
                WHERE COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
                  AND {filtro_sql}
                  AND CAST({valor_sql} AS NUMERIC(18,2)) > 0
                  {empresa_sql}
            """
            quantidade = self._safe_int(self._scalar(sql, empresa_params))
            return f"{quantidade} titulos com pagamento/baixa registrada"

        valor_aberto_sql = self._pagamento_valor_aberto_sql("P", "CURRENT_DATE")
        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE P.PAG_DT_VENCIMENTO BETWEEN CURRENT_DATE AND DATEADD(7 DAY TO CURRENT_DATE)
              AND COALESCE(P.PAG_STATUS, '') IN ('AB', 'PB')
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND CAST({valor_aberto_sql} AS NUMERIC(18,2)) > 0
              {empresa_sql}
        """

        quantidade = self._safe_int(self._scalar(sql, empresa_params))
        return f"{quantidade} titulos vencem nos proximos 7 dias"

    def get_contas_receber_highlight(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> str:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        _, filtro_sql, data_sql = self._receber_metric_sql("R", report_type)

        sql = f"""
            SELECT AVG(
                CASE
                    WHEN R.REC_DT_EMISSAO IS NOT NULL AND R.REC_DT_VENCIMENTO IS NOT NULL
                    THEN DATEDIFF(DAY FROM R.REC_DT_EMISSAO TO R.REC_DT_VENCIMENTO)
                    ELSE NULL
                END
            ) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE {data_sql}
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }

        prazo_medio = self._safe_int(round(self._scalar(sql, params) or 0))
        return f"Prazo medio de recebimento em {prazo_medio} dias"

    def get_contas_receber_history(
        self,
        empresa_id: int | None,
        report_type: str,
    ) -> list[int]:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_sql, filtro_sql, _ = self._receber_metric_sql("R", report_type)

        sql = f"""
            SELECT
                EXTRACT(YEAR FROM R.REC_DT_EMISSAO) AS ANO,
                EXTRACT(MONTH FROM R.REC_DT_EMISSAO) AS MES,
                COALESCE(
                    SUM(CAST({valor_sql} AS NUMERIC(18,2))),
                    0
                ) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE R.REC_DT_EMISSAO >= DATEADD(-11 MONTH TO CURRENT_DATE)
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
            GROUP BY 1, 2
            ORDER BY 1, 2
        """

        rows = self._fetch_all(sql, empresa_params)
        return [self._safe_int(row.get("TOTAL")) for row in rows][-12:]

    def get_contas_pagar_history(
        self,
        empresa_id: int | None,
        report_type: str,
    ) -> list[int]:
        empresa_sql, empresa_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)

        if report_type == "faturado":
            valor_aberto_sql = self._pagamento_valor_aberto_sql("P", "CURRENT_DATE")
            valor_sql = (
                f"(CAST(COALESCE(P.PAG_VALOR, 0) AS NUMERIC(18,2)) - ({valor_aberto_sql}))"
            )
            filtro_sql = "COALESCE(P.PAG_STATUS, '') IN ('PB', 'BX')"
        else:
            valor_sql = self._pagamento_valor_aberto_sql("P", "CURRENT_DATE")
            filtro_sql = "COALESCE(P.PAG_STATUS, '') IN ('AB', 'PB')"

        sql = f"""
            SELECT
                EXTRACT(YEAR FROM P.PAG_DT_VENCIMENTO) AS ANO,
                EXTRACT(MONTH FROM P.PAG_DT_VENCIMENTO) AS MES,
                COALESCE(
                    SUM(CAST({valor_sql} AS NUMERIC(18,2))),
                    0
                ) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE P.PAG_DT_VENCIMENTO >= DATEADD(-11 MONTH TO CURRENT_DATE)
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
            GROUP BY 1, 2
            ORDER BY 1, 2
        """

        rows = self._fetch_all(sql, empresa_params)
        return [self._safe_int(row.get("TOTAL")) for row in rows][-12:]

    # =========================
    # Receitas x Despesas
    # =========================

    def get_receitas_despesas(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> list[dict[str, Any]]:
        if report_type == "faturado":
            return self._get_receitas_despesas_faturado(date_range, empresa_id)
        return self._get_receitas_despesas_aberto(date_range, empresa_id)

    def _get_receitas_despesas_faturado(
        self,
        date_range: DateRange,
        empresa_id: int | None,
    ) -> list[dict[str, Any]]:
        empresa_rec_sql, empresa_rec_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        empresa_pag_sql, empresa_pag_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)

        rec_valor_sql, rec_filtro_sql, rec_data_sql = self._receber_metric_sql("R", "faturado")
        pag_valor_sql, pag_filtro_sql, pag_data_sql = self._pagar_metric_sql("P", "faturado")

        receitas_sql = f"""
            SELECT
                EXTRACT(YEAR FROM R.REC_DT_EMISSAO) AS ANO,
                EXTRACT(MONTH FROM R.REC_DT_EMISSAO) AS MES,
                COALESCE(SUM(CAST({rec_valor_sql} AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE {rec_data_sql}
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {rec_filtro_sql}
              {empresa_rec_sql}
            GROUP BY 1, 2
        """

        despesas_sql = f"""
            SELECT
                EXTRACT(YEAR FROM P.PAG_DT_VENCIMENTO) AS ANO,
                EXTRACT(MONTH FROM P.PAG_DT_VENCIMENTO) AS MES,
                COALESCE(SUM(CAST({pag_valor_sql} AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE {pag_data_sql}
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND {pag_filtro_sql}
              {empresa_pag_sql}
            GROUP BY 1, 2
        """

        params_rec = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_rec_params,
        }
        params_pag = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_pag_params,
        }

        receitas_rows = self._fetch_all(receitas_sql, params_rec)
        despesas_rows = self._fetch_all(despesas_sql, params_pag)

        receitas_map = {
            (self._safe_int(row.get("ANO")), self._safe_int(row.get("MES"))): self._safe_float(row.get("TOTAL"))
            for row in receitas_rows
        }
        despesas_map = {
            (self._safe_int(row.get("ANO")), self._safe_int(row.get("MES"))): self._safe_float(row.get("TOTAL"))
            for row in despesas_rows
        }

        all_keys = sorted(set(receitas_map.keys()) | set(despesas_map.keys()))

        return [
            {
                "label": self._month_label(month),
                "receitas": receitas_map.get((year, month), 0),
                "despesas": despesas_map.get((year, month), 0),
            }
            for year, month in all_keys
            if year and month
        ]

    def _get_receitas_despesas_aberto(
        self,
        date_range: DateRange,
        empresa_id: int | None,
    ) -> list[dict[str, Any]]:
        empresa_rec_sql, empresa_rec_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        empresa_pag_sql, empresa_pag_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)

        rec_valor_sql, rec_filtro_sql, rec_data_sql = self._receber_metric_sql("R", "aberto")
        pag_valor_sql, pag_filtro_sql, pag_data_sql = self._pagar_metric_sql("P", "aberto")

        receitas_sql = f"""
            SELECT
                EXTRACT(YEAR FROM R.REC_DT_EMISSAO) AS ANO,
                EXTRACT(MONTH FROM R.REC_DT_EMISSAO) AS MES,
                COALESCE(SUM(CAST({rec_valor_sql} AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_RECEBIMENTO R
            WHERE {rec_data_sql}
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {rec_filtro_sql}
              {empresa_rec_sql}
            GROUP BY 1, 2
        """

        despesas_sql = f"""
            SELECT
                EXTRACT(YEAR FROM P.PAG_DT_VENCIMENTO) AS ANO,
                EXTRACT(MONTH FROM P.PAG_DT_VENCIMENTO) AS MES,
                COALESCE(SUM(CAST({pag_valor_sql} AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_PAGAMENTO P
            WHERE {pag_data_sql}
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND {pag_filtro_sql}
              {empresa_pag_sql}
            GROUP BY 1, 2
        """

        params_rec = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_rec_params,
        }
        params_pag = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_pag_params,
        }

        receitas_rows = self._fetch_all(receitas_sql, params_rec)
        despesas_rows = self._fetch_all(despesas_sql, params_pag)

        receitas_map = {
            (self._safe_int(row.get("ANO")), self._safe_int(row.get("MES"))): self._safe_float(row.get("TOTAL"))
            for row in receitas_rows
        }
        despesas_map = {
            (self._safe_int(row.get("ANO")), self._safe_int(row.get("MES"))): self._safe_float(row.get("TOTAL"))
            for row in despesas_rows
        }

        all_keys = sorted(set(receitas_map.keys()) | set(despesas_map.keys()))

        return [
            {
                "label": self._month_label(month),
                "receitas": receitas_map.get((year, month), 0),
                "despesas": despesas_map.get((year, month), 0),
            }
            for year, month in all_keys
            if year and month
        ]

    # =========================
    # Aging
    # =========================

    def get_aging(
        self,
        empresa_id: int | None,
        report_type: str,
    ) -> list[dict[str, Any]]:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_sql, filtro_sql, _ = self._receber_metric_sql("R", report_type)

        sql = f"""
            SELECT
                R.REC_DT_VENCIMENTO,
                CAST({valor_sql} AS NUMERIC(18,2)) AS VALOR_BASE
            FROM TB_RECEBIMENTO R
            WHERE COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              AND CAST({valor_sql} AS NUMERIC(18,2)) > 0
              {empresa_sql}
        """

        rows = self._fetch_all(sql, empresa_params)
        today = date.today()

        result = {
            "1-7 dias": {"faixa": "1-7 dias", "valor": 0.0, "titulos": 0, "tone": "blue"},
            "1-21 dias": {"faixa": "1-21 dias", "valor": 0.0, "titulos": 0, "tone": "sky"},
            "1-30 dias": {"faixa": "1-30 dias", "valor": 0.0, "titulos": 0, "tone": "amber"},
            "31-60 dias": {"faixa": "31-60 dias", "valor": 0.0, "titulos": 0, "tone": "orange"},
            "61-90 dias": {"faixa": "61-90 dias", "valor": 0.0, "titulos": 0, "tone": "orange-strong"},
            "91-120 dias": {"faixa": "91-120 dias", "valor": 0.0, "titulos": 0, "tone": "red-soft"},
            "A vencer": {"faixa": "A vencer", "valor": 0.0, "titulos": 0, "tone": "teal"},
            "+120 dias": {"faixa": "+120 dias", "valor": 0.0, "titulos": 0, "tone": "red"},
        }

        for row in rows:
            vencimento = row.get("REC_DT_VENCIMENTO")
            valor = self._safe_float(row.get("VALOR_BASE"))

            if vencimento is None or valor <= 0:
                continue

            # Converte timestamp para date se necessário (PG retorna datetime, Firebird retorna date)
            if hasattr(vencimento, 'date'):
                vencimento = vencimento.date()

            atraso = (today - vencimento).days

            if atraso <= 0:
                result["A vencer"]["valor"] += valor
                result["A vencer"]["titulos"] += 1
            elif 1 <= atraso <= 7:
                result["1-7 dias"]["valor"] += valor
                result["1-7 dias"]["titulos"] += 1
            elif 8 <= atraso <= 21:
                result["1-21 dias"]["valor"] += valor
                result["1-21 dias"]["titulos"] += 1
            elif 22 <= atraso <= 30:
                result["1-30 dias"]["valor"] += valor
                result["1-30 dias"]["titulos"] += 1
            elif 31 <= atraso <= 60:
                result["31-60 dias"]["valor"] += valor
                result["31-60 dias"]["titulos"] += 1
            elif 61 <= atraso <= 90:
                result["61-90 dias"]["valor"] += valor
                result["61-90 dias"]["titulos"] += 1
            elif 91 <= atraso <= 120:
                result["91-120 dias"]["valor"] += valor
                result["91-120 dias"]["titulos"] += 1
            else:
                result["+120 dias"]["valor"] += valor
                result["+120 dias"]["titulos"] += 1

        ordered_keys = [
            "1-7 dias",
            "1-21 dias",
            "1-30 dias",
            "31-60 dias",
            "61-90 dias",
            "91-120 dias",
            "A vencer",
            "+120 dias",
        ]
        return [result[key] for key in ordered_keys]

    # =========================
    # Rankings
    # =========================

    def get_melhores_clientes(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        valor_sql, filtro_sql, data_sql = self._receber_metric_sql("R", report_type)

        sql = f"""
            SELECT
                R.REC_PESSOA AS CLIENTE_ID,
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME) AS CLIENTE_NOME,
                COALESCE(SUM(CAST({valor_sql} AS NUMERIC(18,2))), 0) AS VALOR_TOTAL,
                COUNT(*) AS TITULOS
            FROM TB_RECEBIMENTO R
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = R.REC_PESSOA
            WHERE {data_sql}
              AND R.REC_PESSOA IS NOT NULL
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
            GROUP BY
                R.REC_PESSOA,
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME)
            ORDER BY VALOR_TOTAL DESC
            ROWS 5
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }

        rows = self._fetch_all(sql, params)

        return [
            {
                "nome": row.get("CLIENTE_NOME") or f"Cliente {self._safe_int(row.get('CLIENTE_ID'))}",
                "valor": self._safe_float(row.get("VALOR_TOTAL")),
                "pedidos": self._safe_int(row.get("TITULOS")),
            }
            for row in rows
        ]

    def get_melhores_fornecedores(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("P.PAG_EMPRESA", empresa_id)
        valor_sql, filtro_sql, data_sql = self._pagar_metric_sql("P", report_type)

        sql = f"""
            SELECT
                P.PAG_PESSOA AS FORNECEDOR_ID,
                COALESCE(NULLIF(TRIM(PS.PES_FANTASIA_APELIDO), ''), PS.PES_RSOCIAL_NOME) AS FORNECEDOR_NOME,
                COUNT(*) AS QUANTIDADE,
                COALESCE(SUM(CAST({valor_sql} AS NUMERIC(18,2))), 0) AS VOLUME
            FROM TB_PAGAMENTO P
            INNER JOIN TB_PESSOA PS
                ON PS.PES_ID = P.PAG_PESSOA
            WHERE {data_sql}
              AND P.PAG_PESSOA IS NOT NULL
              AND COALESCE(P.PAG_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
            GROUP BY
                P.PAG_PESSOA,
                COALESCE(NULLIF(TRIM(PS.PES_FANTASIA_APELIDO), ''), PS.PES_RSOCIAL_NOME)
            ORDER BY VOLUME DESC
            ROWS 5
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }

        rows = self._fetch_all(sql, params)

        return [
            {
                "nome": row.get("FORNECEDOR_NOME") or f"Fornecedor {self._safe_int(row.get('FORNECEDOR_ID'))}",
                "quantidade": self._safe_int(row.get("QUANTIDADE")),
                "volume": self._safe_float(row.get("VOLUME")),
            }
            for row in rows
        ]

    # =========================
    # Estoque
    # =========================

    def get_estoque_critico(self, empresa_id: int | None) -> list[dict]:
        from app.repositories.stock_availability import stock_requires_consolidation
        self.stock_requires_rule = stock_requires_consolidation(self, empresa_id)
        if self.stock_requires_rule:
            return []
        resultado_com_minimo = self._get_estoque_critico_com_minimo(empresa_id)
        if resultado_com_minimo:
            return resultado_com_minimo
        return self._get_estoque_critico_sem_minimo(empresa_id)

    def _get_estoque_critico_com_minimo(self, empresa_id: int | None) -> list[dict]:
        empresa_prod_sql, empresa_prod_params = self._empresa_filter("P.PRD_EMPRESA", empresa_id)
        empresa_est_sql, empresa_est_params = self._empresa_filter("E.PRDE_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                P.PRD_ID AS PRODUTO_ID,
                P.PRD_DESCRICAO AS PRODUTO,
                CAST(COALESCE(E.PRDE_ESTOQUE, 0) AS NUMERIC(18,2)) AS ESTOQUE,
                CAST(COALESCE(P.PRD_ESTOQUE_MINIMO, 0) AS NUMERIC(18,2)) AS MINIMO,
                P.PRD_STATUS,
                P.PRD_CONTROLA_ESTOQUE
            FROM TB_PRODUTO P
            INNER JOIN TB_PRODUTO_ESTOQUE E
                ON E.PRDE_PRODUTO = P.PRD_ID
               AND E.PRDE_EMPRESA = P.PRD_EMPRESA
            WHERE COALESCE(P.PRD_ESTOQUE_MINIMO, 0) > 0
              AND COALESCE(E.PRDE_ESTOQUE, 0) <= COALESCE(P.PRD_ESTOQUE_MINIMO, 0)
              {empresa_prod_sql}
              {empresa_est_sql}
            ORDER BY P.PRD_DESCRICAO
            ROWS 30
        """

        params = {
            **empresa_prod_params,
            **empresa_est_params,
        }

        rows = self._fetch_all(sql, params)

        result = []
        for row in rows:
            product_status = str(row.get("PRD_STATUS") or "").strip().upper()
            controls_stock = str(row.get("PRD_CONTROLA_ESTOQUE") or "").strip().upper()

            if product_status in {"INATIVO", "I", "0"}:
                continue

            if controls_stock not in {"S", "SIM", "1", "T", "TRUE"}:
                continue

            estoque = self._safe_float(row.get("ESTOQUE"))
            minimo = self._safe_float(row.get("MINIMO"))

            if minimo <= 0:
                continue

            if estoque <= minimo * 0.5:
                status = "Critico"
            elif estoque <= minimo * 0.8:
                status = "Reposicao"
            else:
                status = "Atencao"

            result.append(
                {
                    "produto": row.get("PRODUTO"),
                    "estoque": self._safe_int(round(estoque)),
                    "minimo": self._safe_int(round(minimo)),
                    "status": status,
                }
            )

            if len(result) == 10:
                break

        return result

    def _get_estoque_critico_sem_minimo(self, empresa_id: int | None) -> list[dict]:
        empresa_prod_sql, empresa_prod_params = self._empresa_filter("P.PRD_EMPRESA", empresa_id)
        empresa_est_sql, empresa_est_params = self._empresa_filter("E.PRDE_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                P.PRD_ID AS PRODUTO_ID,
                P.PRD_DESCRICAO AS PRODUTO,
                CAST(COALESCE(E.PRDE_ESTOQUE, 0) AS NUMERIC(18,2)) AS ESTOQUE,
                P.PRD_STATUS,
                P.PRD_CONTROLA_ESTOQUE
            FROM TB_PRODUTO P
            INNER JOIN TB_PRODUTO_ESTOQUE E
                ON E.PRDE_PRODUTO = P.PRD_ID
               AND E.PRDE_EMPRESA = P.PRD_EMPRESA
            {f"WHERE 1=1 {empresa_prod_sql} {empresa_est_sql}"}
            ORDER BY E.PRDE_ESTOQUE ASC, P.PRD_DESCRICAO
            ROWS 30
        """

        params = {
            **empresa_prod_params,
            **empresa_est_params,
        }

        rows = self._fetch_all(sql, params)

        result = []
        for row in rows:
            product_status = str(row.get("PRD_STATUS") or "").strip().upper()
            controls_stock = str(row.get("PRD_CONTROLA_ESTOQUE") or "").strip().upper()

            if product_status in {"INATIVO", "I", "0"}:
                continue

            if controls_stock not in {"S", "SIM", "1", "T", "TRUE"}:
                continue

            estoque = self._safe_float(row.get("ESTOQUE"))

            status = "Atencao"
            if estoque <= 0:
                status = "Critico"
            elif estoque <= 3:
                status = "Reposicao"

            result.append(
                {
                    "produto": row.get("PRODUTO"),
                    "estoque": self._safe_int(round(estoque)),
                    "minimo": 0,
                    "status": status,
                }
            )

            if len(result) == 10:
                break

        return result

    # =========================
    # Clientes por cidade
    # =========================

    def get_clientes_por_cidade(
        self,
        date_range: DateRange,
        empresa_id: int | None,
        report_type: str,
    ) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("R.REC_EMPRESA", empresa_id)
        _, filtro_sql, data_sql = self._receber_metric_sql("R", report_type)

        city_columns = self.erp.table_columns('TB_CIDADE')
        ibge_select = 'CID.CID_CODIGO_MUNICIPIO' if 'CID_CODIGO_MUNICIPIO' in city_columns else 'NULL'
        ibge_group = ', CID.CID_CODIGO_MUNICIPIO' if 'CID_CODIGO_MUNICIPIO' in city_columns else ''

        sql = f"""
            SELECT
                CID.CID_ID AS CIDADE_ID,
                CID.CID_NOME AS CIDADE_NOME,
                {ibge_select} AS CODIGO_IBGE,
                COUNT(DISTINCT P.PES_ID) AS QUANTIDADE
            FROM TB_RECEBIMENTO R
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = R.REC_PESSOA
            LEFT JOIN TB_CIDADE CID
                ON CID.CID_ID = P.PES_CIDADE
            WHERE {data_sql}
              AND R.REC_PESSOA IS NOT NULL
              AND COALESCE(R.REC_STATUS, '') <> 'CANCELADO'
              AND {filtro_sql}
              {empresa_sql}
            GROUP BY CID.CID_ID, CID.CID_NOME{ibge_group}
            ORDER BY QUANTIDADE DESC
            ROWS 10
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }

        rows = self._fetch_all(sql, params)

        result = []
        for row in rows:
            city_name = row.get("CIDADE_NOME") or "Nao informada"

            result.append(
                {
                    "cidade": city_name,
                    "quantidade": self._safe_int(row.get("QUANTIDADE")),
                    "codigo_ibge": str(row['CODIGO_IBGE']).strip() if row.get('CODIGO_IBGE') else None,
                    "cor": ['#2563eb','#0d9488','#7c3aed','#d97706','#dc2626'][len(result) % 5],
                }
            )

        return result
