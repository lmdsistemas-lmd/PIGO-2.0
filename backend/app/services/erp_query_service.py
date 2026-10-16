from __future__ import annotations
import re
import time
import hashlib
import json
import logging
import traceback
import threading
from typing import Any
from sqlalchemy import text
from app.database.erp_connection import get_erp_db, current_cnpj, current_tenant_id
from app.database.connection import SessionLocal
from app.models.saas import Tenant

logger = logging.getLogger(__name__)

# Cache de metadados para evitar round-trips ao Supabase
_tenant_id_cache: dict[str, str | None] = {}
_saas_mode_cache: dict[str, bool] = {}

# Cache de resultados de query (SQL + Params -> Resultado)
# Estrutura: { key: (timestamp, result) }
_query_result_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 30
_query_cache_lock = threading.RLock()
_query_cache_revision = 0


def clear_erp_query_cache():
    """Invalidate after a committed sync; in-flight old reads cannot refill it."""
    global _query_cache_revision
    with _query_cache_lock:
        _query_cache_revision += 1
        _query_result_cache.clear()
        _table_exists_cache.clear()

_table_exists_cache: dict[str, bool] = {}

class ERPQueryService:
    def table_columns(self, table_name: str) -> set[str]:
        """Read schema metadata without guessing optional synchronized fields."""
        if not re.fullmatch(r'TB_[A-Z0-9_]+', table_name):
            raise ValueError('Tabela ERP invalida.')
        if self._is_saas_mode():
            with SessionLocal() as db:
                return set(db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:table"), {'table': table_name}).scalars())
        db_gen = get_erp_db()
        db = next(db_gen)
        try:
            return {str(name).strip() for name in db.execute(text('SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME=:table'), {'table': table_name}).scalars()}
        finally:
            db_gen.close()

    def table_exists(self, table_name: str) -> bool:
        if not self._is_saas_mode():
            return True

        cache_key = table_name.upper()
        if _table_exists_cache.get(cache_key) is True:
            return True

        with SessionLocal() as db:
            exists = db.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                    )
                    """
                ),
                {"table_name": table_name.upper()},
            ).scalar()

        _table_exists_cache[cache_key] = bool(exists)
        return bool(exists)

    def _referenced_tables(self, sql: str) -> set[str]:
        quoted = {match.upper() for match in re.findall(r'"(TB_[A-Z0-9_]+)"', sql, flags=re.IGNORECASE)}
        unquoted = {match.upper() for match in re.findall(r'\b(TB_[A-Z0-9_]+)\b', sql, flags=re.IGNORECASE)}
        return quoted | unquoted

    def _has_missing_tables(self, sql: str, db: Any) -> list[str]:
        missing: list[str] = []
        for table_name in sorted(self._referenced_tables(sql)):
            exists = _table_exists_cache.get(table_name)
            if exists is not True:
                exists = bool(
                    db.execute(
                        text(
                            """
                            SELECT EXISTS (
                                SELECT 1
                                FROM information_schema.tables
                                WHERE table_schema = 'public'
                                  AND table_name = :table_name
                            )
                            """
                        ),
                        {"table_name": table_name},
                    ).scalar()
                )
                _table_exists_cache[table_name] = exists

            if not exists:
                missing.append(table_name)

        return missing

    def _is_schema_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        schema_markers = [
            "42p01",
            "42703",
            "relation",
            "rela",
            "coluna",
            "column",
            "does not exist",
            "nao existe",
            "não existe",
        ]
        return any(marker in message for marker in schema_markers)

    def _is_saas_mode(self) -> bool:
        """Verifica se o CNPJ atual está configurado como REMOTE (SaaS) - com cache"""
        cnpj = current_cnpj.get()
        if cnpj in _saas_mode_cache:
            return _saas_mode_cache[cnpj]
        try:
            from app.database.erp_connection import get_engine_for_cnpj
            result = get_engine_for_cnpj(cnpj) is None
        except:
            result = True
        _saas_mode_cache[cnpj] = result
        return result

    def _get_tenant_id(self, db: Any) -> str | None:
        """Retorna somente o tenant autenticado da sessao/JWT."""
        tenant_id_from_context = current_tenant_id.get()
        if tenant_id_from_context:
            return str(tenant_id_from_context)
        return None

    def _root_table_alias(self, sql: str) -> str | None:
        alias_match = re.search(
            r'FROM\s+("TB_[A-Z0-9_]+"|TB_[A-Z0-9_]+)(?:\s+(?:AS\s+)?([A-Z][A-Z0-9_]*))?',
            sql,
            flags=re.IGNORECASE,
        )
        if not alias_match:
            return None
        possible_alias = alias_match.group(2)
        if possible_alias and possible_alias.upper() not in {"WHERE", "INNER", "LEFT", "RIGHT", "JOIN", "ON", "ORDER", "GROUP", "LIMIT"}:
            return possible_alias
        return alias_match.group(1)

    def _join_aliases(self, sql: str) -> list[str]:
        aliases: list[str] = []
        for match in re.finditer(
            r'\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+("TB_[A-Z0-9_]+"|TB_[A-Z0-9_]+)(?:\s+(?:AS\s+)?([A-Z][A-Z0-9_]*))?',
            sql,
            flags=re.IGNORECASE,
        ):
            alias = match.group(2) or match.group(1)
            if alias.upper() not in {"ON", "WHERE", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "JOIN", "ORDER", "GROUP", "LIMIT"}:
                aliases.append(alias)
        return aliases

    def _inject_join_tenant_guards(self, sql: str, root_alias: str) -> str:
        if not root_alias:
            return sql

        for alias in self._join_aliases(sql):
            if alias == root_alias:
                continue
            guard = f'{alias}.tenant_id = {root_alias}.tenant_id'
            if guard.lower() in sql.lower():
                continue

            pattern = (
                rf'(\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+'
                rf'(?:"TB_[A-Z0-9_]+"|TB_[A-Z0-9_]+)(?:\s+(?:AS\s+)?{re.escape(alias)})?\s+ON\s+)'
                rf'(.*?)'
                rf'(?=(?:\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$))'
            )

            def add_guard(match):
                on_clause = match.group(2).strip()
                if guard.lower() in on_clause.lower():
                    return match.group(0)
                return f"{match.group(1)}{on_clause} AND {guard} "

            sql = re.sub(pattern, add_guard, sql, count=1, flags=re.IGNORECASE | re.DOTALL)

        return sql

    def _inject_root_tenant_filter(self, sql: str, tenant_id: str, params: dict[str, Any]) -> str:
        params["tenant_id_filter"] = tenant_id
        root_alias = self._root_table_alias(sql)
        if not root_alias:
            raise RuntimeError("Consulta SaaS sem tabela raiz TB_* para aplicar tenant_id.")

        tenant_col = f"{root_alias}.tenant_id"
        if ":tenant_id_filter" in sql and "tenant_id" in sql:
            return sql

        if "WHERE " in sql.upper():
            return re.sub(r'WHERE\s+', f'WHERE {tenant_col} = :tenant_id_filter AND ', sql, count=1, flags=re.IGNORECASE)
        if "GROUP BY" in sql.upper():
            return re.sub(r'GROUP BY', f'WHERE {tenant_col} = :tenant_id_filter GROUP BY', sql, count=1, flags=re.IGNORECASE)
        if "ORDER BY" in sql.upper():
            return re.sub(r'ORDER BY', f'WHERE {tenant_col} = :tenant_id_filter ORDER BY', sql, count=1, flags=re.IGNORECASE)
        if "LIMIT" in sql.upper():
            return re.sub(r'LIMIT', f'WHERE {tenant_col} = :tenant_id_filter LIMIT', sql, count=1, flags=re.IGNORECASE)
        return f"{sql} WHERE {tenant_col} = :tenant_id_filter"

    def _translate_sql(self, sql: str) -> str:
        """Traduz sintaxe Firebird para PostgreSQL (SaaS)"""
        # 1. SELECT FIRST n -> SELECT ... LIMIT n
        limit_match = re.search(r'SELECT\s+FIRST\s+(\d+)', sql, flags=re.IGNORECASE)
        if limit_match:
            limit_val = limit_match.group(1)
            sql = re.sub(r'SELECT\s+FIRST\s+\d+', 'SELECT', sql, flags=re.IGNORECASE)
            if "LIMIT" not in sql.upper():
                sql = sql.strip()
                if sql.endswith(';'):
                    sql = sql[:-1] + f" LIMIT {limit_val};"
                else:
                    sql += f" LIMIT {limit_val}"
        
        # 1.1. FIRST n (sem SELECT logo antes) -> LIMIT n
        match_first = re.search(r"FIRST\s+(\d+)", sql, re.IGNORECASE)
        if match_first:
            limit_val = match_first.group(1)
            sql = re.sub(r"FIRST\s+\d+", "", sql, flags=re.IGNORECASE)
            if "LIMIT" not in sql.upper():
                sql += f" LIMIT {limit_val}"

        # 2. ROWS n TO m -> LIMIT (m-n+1) OFFSET (n-1)
        match_rows_to = re.search(r"ROWS\s+(\d+)\s+TO\s+(\d+)", sql, re.IGNORECASE)
        if match_rows_to:
            start = int(match_rows_to.group(1))
            end = int(match_rows_to.group(2))
            limit = end - start + 1
            offset = start - 1
            sql = re.sub(r"ROWS\s+\d+\s+TO\s+\d+", "", sql, flags=re.IGNORECASE)
            sql += f" LIMIT {limit} OFFSET {offset}"
        
        # 2.1. ROWS n (sem TO) -> LIMIT n
        match_rows_only = re.search(r"\bROWS\s+(\d+)\b", sql, re.IGNORECASE)
        if match_rows_only and "LIMIT" not in sql.upper():
            limit_val = match_rows_only.group(1)
            sql = re.sub(r"\bROWS\s+\d+\b", "", sql, flags=re.IGNORECASE)
            sql += f" LIMIT {limit_val}"
        
        # 3. Ajustes de Aspas e Prefixos
        sql = re.sub(r'\b(TB_[A-Z0-9_]+)\b', r'"\1"', sql, flags=re.IGNORECASE)
        prefixes = "PEV|PEVI|REC|RECI|PAG|PAGI|PRD|PRDE|PES|EMP|CID|AUD|USU|CLI|VDR|PGRU|PMAR|ESP|COL|PEVF"
        
        def quote_and_upper(match):
            return f'"{match.group(1).upper()}"'
        sql = re.sub(rf'\b((?:{prefixes})_[A-Za-z0-9_]+)\b', quote_and_upper, sql, flags=re.IGNORECASE)

        # 4. Funções de Data
        sql = re.sub(r'DATEADD\s*\(\s*(-?\d+)\s+(DAY|MONTH|YEAR)S?\s+TO\s+CURRENT_DATE\s*\)',
                     r"CURRENT_DATE + INTERVAL '\1 \2'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'EXTRACT\(\s*WEEKDAY\s+FROM', 'EXTRACT(DOW FROM', sql, flags=re.IGNORECASE)
        sql = re.sub(r'DATEDIFF\s*\(\s*DAY\s+FROM\s+([^\s,]+)\s+TO\s+([^\s,\)]+)\s*\)',
                     r'(\2::date - \1::date)', sql, flags=re.IGNORECASE)

        # 5. SP Fallbacks (Firebird -> PostgreSQL)
        def _replace_rec_sp(m):
            alias = m.group(1)
            return f"""CASE {alias}."REC_ABERTO" WHEN 'S' THEN COALESCE({alias}."REC_VALOR", 0) ELSE 0 END"""
        sql = re.sub(r"""CASE\s+(\w+)\."REC_ABERTO"\s+WHEN\s+'S'\s+THEN\s+\(\s*SELECT\s+COALESCE\(A\.VALOR_ABERTO,\s*0\)\s+FROM\s+SP_RECEBIMENTO_ABERTO\([^)]+\)\s+A\s*\)\s+ELSE\s+0\s+END""",
                     _replace_rec_sp, sql, flags=re.IGNORECASE | re.DOTALL)

        def _replace_pag_sp(m):
            alias = m.group(1)
            return f"""CASE {alias}."PAG_ABERTO" WHEN 'S' THEN COALESCE({alias}."PAG_VALOR", 0) ELSE 0 END"""
        sql = re.sub(r"""CASE\s+(\w+)\."PAG_ABERTO"\s+WHEN\s+'S'\s+THEN\s+\(\s*SELECT\s+COALESCE\(A\.VALOR_ABERTO,\s*0\)\s+FROM\s+SP_PAGAMENTO_ABERTO\([^)]+\)\s+A\s*\)\s+ELSE\s+0\s+END""",
                     _replace_pag_sp, sql, flags=re.IGNORECASE | re.DOTALL)

        # 6. Tabelas e Colunas Inexistentes
        # 6.1. Remove TB_PRODUTO_PRECO (não sincronizada)
        if '"TB_PRODUTO_PRECO"' in sql or 'TB_PRODUTO_PRECO' in sql.upper():
            sql = re.sub(
                r'LEFT\s+JOIN\s+"?TB_PRODUTO_PRECO"?\s+\w+\s+ON\s+.*?(?=WHERE|GROUP|ORDER|LIMIT|$)',
                ' ',
                sql,
                flags=re.IGNORECASE | re.DOTALL
            )
            # Substitui campos que viriam dela pelos campos padrão da TB_PRODUTO
            sql = re.sub(r'\bPRDP\."PRDP_CUSTO_TOTAL"', 'P."PRD_PRECO_CUSTO"', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\bPRDP\."PRDP_PRECO_VENDA"', 'P."PRD_PRECO_VENDA"', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\bPRDP\."PRDP_PRECO_COMPRA"', 'P."PRD_PRECO_CUSTO"', sql, flags=re.IGNORECASE)
            sql = re.sub(r'COALESCE\s*\(\s*PRDP\.[^,]+,\s*', 'COALESCE(', sql, flags=re.IGNORECASE)

        # 6.2. Tabelas que retornam dummy
        missing_tables = ['"TB_PRODUTO_MOVIMENTO"', 'TB_produto_MOVIMENTO', '"TB_PEDIDO_VENDA_FIN"']
        if any(table in sql for table in missing_tables):
            return 'SELECT 0 AS QTD, 0 AS TOTAL FROM "TB_EMPRESA" WHERE 1=0'

        sql = re.sub(r'\b\w+\."PRD_CONTROLA_ESTOQUE"', "'S'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\b\w+\.PRD_CONTROLA_ESTOQUE\b', "'S'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'"PRD_CONTROLA_ESTOQUE"', "'S'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bPRD_CONTROLA_ESTOQUE\b', "'S'", sql, flags=re.IGNORECASE)

        # 7. Casts para compatibilidade de tipos (TEXT vs INT)
        sql = re.sub(r'ON\s+(\w+\."[^"]+")(\s*=\s*)(\w+\."[^"]+")',
                     lambda m: f'ON {m.group(1)}::text = {m.group(3)}::text', sql, flags=re.IGNORECASE)
        sql = re.sub(r'AND\s+(\w+\."[^"]+")\s*=\s*(\w+\."[^"]+")',
                     lambda m: f'AND {m.group(1)}::text = {m.group(2)}::text', sql, flags=re.IGNORECASE)

        return sql

    def scalar(self, sql: str, params: dict[str, Any] | None = None) -> float:
        res = self._execute_query(sql, params, mode="all")
        if res and isinstance(res, list) and len(res) > 0:
            val = list(res[0].values())[0]
            return float(val or 0)
        return 0.0

    def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute_query(sql, params, mode="all")

    def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def _execute_query(self, sql: str, params: dict[str, Any] | None = None, mode: str = "all") -> Any:
        params = params or {}
        is_saas = self._is_saas_mode()
        
        if is_saas:
            # --- TRADUÇÃO E PREPARAÇÃO ---
            sql = self._translate_sql(sql)
            tenant_id = self._get_tenant_id(None)
            if not tenant_id:
                raise RuntimeError("Tenant autenticado ausente na sessao; consulta SaaS bloqueada.")

            root_alias = self._root_table_alias(sql)
            sql = self._inject_join_tenant_guards(sql, root_alias)
            sql = self._inject_root_tenant_filter(sql, tenant_id, params)
            tenant_id = None
            if tenant_id:
                params["tenant_id_filter"] = tenant_id
                prefix = ""
                alias_match = re.search(
                    r'FROM\s+("TB_[A-Z0-9_]+"|TB_[A-Z0-9_]+)(?:\s+(AS\s+)?([A-Z0-9_]+))?',
                    sql,
                    flags=re.IGNORECASE,
                )
                if alias_match:
                    possible_alias = alias_match.group(3)
                    if possible_alias and possible_alias.upper() not in ["WHERE", "INNER", "LEFT", "RIGHT", "JOIN", "ON", "ORDER", "GROUP"]:
                        prefix = f"{possible_alias}."
                    else:
                        prefix = f"{alias_match.group(1)}."

                tenant_col = f"{prefix}tenant_id"
                if "WHERE " in sql.upper():
                    sql = re.sub(r'WHERE\s+', f'WHERE {tenant_col} = :tenant_id_filter AND ', sql, count=1, flags=re.IGNORECASE)
                else:
                    if "GROUP BY" in sql.upper():
                        sql = re.sub(r'GROUP BY', f'WHERE {tenant_col} = :tenant_id_filter GROUP BY', sql, count=1, flags=re.IGNORECASE)
                    elif "ORDER BY" in sql.upper():
                        sql = re.sub(r'ORDER BY', f'WHERE {tenant_col} = :tenant_id_filter ORDER BY', sql, count=1, flags=re.IGNORECASE)
                    else:
                        sql += f" WHERE {tenant_col} = :tenant_id_filter"
            
            # --- LÓGICA DE CACHE ---
            try:
                cache_key_str = f"{sql}_{json.dumps(params, sort_keys=True, default=str)}"
                cache_key = hashlib.md5(cache_key_str.encode()).hexdigest()
                now = time.time()
                with _query_cache_lock:
                    cache_revision = _query_cache_revision
                    cached = _query_result_cache.get(cache_key)
                    if cached and now - cached[0] < _CACHE_TTL:
                        return cached[1]
            except:
                cache_key = None

            # --- EXECUÇÃO NO POSTGRES ---
            db = SessionLocal()
            try:
                missing_tables = self._has_missing_tables(sql, db)
                if missing_tables:
                    logger.warning(
                        "Consulta ignorada por tabela nao sincronizada. tables=%s sql=%s params=%s",
                        missing_tables,
                        sql,
                        params,
                    )
                    return []

                started_at = time.perf_counter()
                logger.info("SQL SaaS executando: sql=%s params=%s", sql, params)
                query_result = db.execute(text(sql), params)
                rows = query_result.mappings().all()
                normalized_rows = []
                for row in rows:
                    normalized_row = {str(k).upper(): v for k, v in dict(row).items()}
                    normalized_rows.append(normalized_row)

                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    "SQL SaaS concluido: registros=%s duration_ms=%s",
                    len(normalized_rows),
                    duration_ms,
                )

                if cache_key:
                    with _query_cache_lock:
                        if cache_revision == _query_cache_revision:
                            _query_result_cache[cache_key] = (now, normalized_rows)
                return normalized_rows
            except Exception as e:
                db.rollback()
                if self._is_schema_error(e):
                    logger.warning(
                        "Consulta ignorada por incompatibilidade de schema. error=%s sql=%s params=%s",
                        e,
                        sql,
                        params,
                    )
                    return []

                logger.error(
                    "Erro em query SaaS: %s sql=%s params=%s\n%s",
                    e,
                    sql,
                    params,
                    traceback.format_exc(),
                )
                raise e
            finally:
                db.close()
        else:
            # MODO LOCAL (Firebird)
            db_gen = get_erp_db()
            db = next(db_gen)
            try:
                query_result = db.execute(text(sql), params)
                rows = query_result.mappings().all()
                normalized_rows = [{str(k).upper(): v for k, v in dict(row).items()} for row in rows]
                return normalized_rows
            except Exception as e:
                db.rollback()
                raise e

    def empresa_filter(self, field_name: str, empresa_id: int | None) -> tuple[str, dict[str, Any]]:
        if empresa_id is None:
            return "", {}
        empresa_val = str(empresa_id) if self._is_saas_mode() else empresa_id
        return f" AND {field_name} = :empresa_id ", {"empresa_id": empresa_val}
