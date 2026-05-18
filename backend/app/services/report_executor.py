from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.services.report_parameter_extractor import extract_params_from_queries
from app.services.report_parameter_resolver import ParameterResolver, ReportParameter


class ReportExecutorService:
    """
    Serviço responsável por:
    - descobrir parâmetros usados pelo relatório
    - gerar binds automáticos
    - executar preview
    """

    def __init__(self, db_session):
        self.db = db_session

    def _extract_sql_from_query(self, query: Any) -> str:
        if isinstance(query, dict):
            sql = query.get("sql") or query.get("sql_text") or ""
        else:
            sql = getattr(query, "sql", None) or getattr(query, "sql_text", None) or ""

        return self._clean_sql(str(sql))

    def _clean_sql(self, sql: str) -> str:
        sql = (sql or "").strip()

        while sql.endswith(";"):
            sql = sql[:-1].strip()

        return sql

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}

        for key, value in row.items():
            if isinstance(value, Decimal):
                normalized[key] = float(value)
            elif isinstance(value, datetime):
                normalized[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, date):
                normalized[key] = value.strftime("%Y-%m-%d")
            else:
                normalized[key] = value

        return normalized

    def _apply_limit_firebird(self, sql: str, limit: Optional[int]) -> str:
        """
        Aplica FIRST no Firebird sem encapsular a query em subquery,
        evitando erro com CTE (WITH ...) e várias queries complexas.
        """
        sql = self._clean_sql(sql)

        if not limit or int(limit) <= 0:
            return sql

        limit = int(limit)
        sql_lower = sql.strip().lower()

        # Já possui FIRST
        if re.search(r"^\s*select\s+first\s+\d+", sql, flags=re.IGNORECASE):
            return sql

        # Query simples: SELECT ...
        if sql_lower.startswith("select"):
            return re.sub(
                r"^\s*select\s+",
                f"SELECT FIRST {limit} ",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )

        # Query com CTE: WITH ... SELECT ...
        if sql_lower.startswith("with"):
            match = re.search(r"\bselect\b", sql, flags=re.IGNORECASE)
            if match:
                start = match.start()
                before = sql[:start]
                after = sql[start:]
                after = re.sub(
                    r"^\s*select\s+",
                    f"SELECT FIRST {limit} ",
                    after,
                    count=1,
                    flags=re.IGNORECASE,
                )
                return before + after

        return sql

    def get_sql_list(self, parsed_report: Dict[str, Any]) -> List[str]:
        sql_list: List[str] = []

        for q in parsed_report.get("queries", []):
            sql = self._extract_sql_from_query(q)
            if sql:
                sql_list.append(sql)

        return sql_list

    def get_main_sql(self, parsed_report: Dict[str, Any]) -> str:
        queries = parsed_report.get("queries", []) or []

        if not queries:
            raise ValueError("Nenhuma query encontrada no relatório.")

        for query in queries:
            sql = self._extract_sql_from_query(query)
            if not sql:
                continue

            sql_lower = sql.lower()

            if (
                sql_lower.startswith("select")
                or sql_lower.startswith("with")
                or sql_lower.startswith("/*")
            ):
                return sql

        sql_list = self.get_sql_list(parsed_report)
        if not sql_list:
            raise ValueError("Nenhuma query encontrada no relatório.")

        return sql_list[0]

    def describe_parameters(
        self,
        parsed_report: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[ReportParameter]:
        sql_list = self.get_sql_list(parsed_report)
        param_names = extract_params_from_queries(sql_list)

        resolver = ParameterResolver(user_context=user_context)
        return resolver.describe(param_names)

    def build_parameter_bundle(
        self,
        parsed_report: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        report_params = self.describe_parameters(parsed_report, user_context=user_context)

        return {
            "param_names": [p.original_name for p in report_params],
            "parameters": [
                {
                    "original_name": p.original_name,
                    "normalized_name": p.normalized_name,
                    "semantic_key": p.semantic_key,
                    "inferred_type": p.inferred_type,
                    "required": p.required,
                    "default_value": p.default_value,
                    "aliases": p.aliases,
                }
                for p in report_params
            ],
        }

    def execute_preview(
        self,
        parsed_report: Dict[str, Any],
        payload: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        resolver = ParameterResolver(user_context=user_context)
        report_params = self.describe_parameters(parsed_report, user_context=user_context)
        bind_params = resolver.resolve(report_params, incoming_payload=payload)

        main_sql = self.get_main_sql(parsed_report)
        sql_execucao = self._apply_limit_firebird(main_sql, limit)

        result = self.db.execute(text(sql_execucao), bind_params)
        rows = result.mappings().all()

        linhas = [self._normalize_row(dict(row)) for row in rows]
        columns = list(linhas[0].keys()) if linhas else []

        return {
            "colunas": columns,
            "linhas": linhas,
            "total_registros": len(linhas),
            "parametros_usados": bind_params,
            "parametros_detectados": [
                {
                    "original_name": p.original_name,
                    "normalized_name": p.normalized_name,
                    "semantic_key": p.semantic_key,
                    "inferred_type": p.inferred_type,
                    "required": p.required,
                    "default_value": p.default_value,
                    "aliases": p.aliases,
                }
                for p in report_params
            ],
        }