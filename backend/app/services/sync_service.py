import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.saas import SyncJob, Tenant


logger = logging.getLogger(__name__)


class SyncService:
    TABLE_PK_MAP = {
        "TB_EMPRESA": ["EMP_ID"],
        "TB_PESSOA": ["PES_ID"],
        "TB_CLIENTE": ["CLI_PESSOA"],
        "TB_VENDEDOR": ["VDR_PESSOA"],
        "TB_CIDADE": ["CID_ID"],
        "TB_PEDIDO_VENDA": ["PEV_ID"],
        "TB_PEDIDO_VENDA_ITEM": ["PEVI_PEDIDO_VENDA", "PEVI_EMPRESA", "PEVI_PRODUTO"],
        "TB_PRODUTO": ["PRD_ID"],
        "TB_PRODUTO_ESTOQUE": ["PRDE_PRODUTO", "PRDE_EMPRESA"],
        "TB_RECEBIMENTO": ["REC_ID"],
        "TB_PAGAMENTO": ["PAG_ID"],
        "TB_AUDITORIA": ["AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA"],
        "TB_USUARIO": ["USU_ID"],
        "TB_COLABORADOR": ["COL_PESSOA"],
        "TB_PROD_GRUPO": ["PGRU_ID"],
        "TB_PROD_MARCA": ["PMAR_ID"],
        "TB_ESPECIE_MOEDA": ["ESP_ID"],
        "TB_PEDIDO_VENDA_FIN": ["PEVF_PEDIDO_VENDA", "PEVF_EMPRESA", "PEVF_ESPECIE_MOEDA"],
    }

    @staticmethod
    def process_sync_data(db: Session, tenant: Tenant, cnpj: str, data_type: str, content: Any) -> Dict:
        if not tenant:
            raise ValueError(f"Tenant nao encontrado para o CNPJ: {cnpj}")

        received = len(content) if isinstance(content, list) else 0
        job = SyncJob(
            tenant_id=tenant.id,
            status="RUNNING",
            table_name=data_type,
            records_synced=0,
            started_at=datetime.now(),
        )
        db.add(job)
        db.commit()

        try:
            if data_type in SyncService.TABLE_PK_MAP:
                stats = SyncService._sync_generic_table(db, str(tenant.id), data_type, content)
            elif data_type == "VENDAS" and isinstance(content, dict):
                vendas = content.get("vendas_diarias", [])
                stats = SyncService._sync_generic_table(
                    db,
                    str(tenant.id),
                    "sync_vendas_diarias",
                    vendas,
                    legacy_pk=["data_venda"],
                )
            elif data_type == "USUARIOS" and isinstance(content, list):
                stats = SyncService._sync_generic_table(db, str(tenant.id), "TB_USUARIO", content)
            else:
                logger.info("[SYNC] Tipo desconhecido tratado como tabela espelhada generica: %s", data_type)
                stats = SyncService._sync_generic_table(db, str(tenant.id), data_type, content)

            job.status = "COMPLETED"
            job.table_name = stats["destination_table"]
            job.records_synced = stats["inserted"] + stats["updated"]
            job.finished_at = datetime.now()
            db.commit()

            from app.services.report_engine import clear_report_cache

            clear_report_cache(str(tenant.id))

            logger.info(
                "[SYNC] completed tenant_id=%s tenant_cnpj=%s data_type=%s destination=%s "
                "received=%s inserted=%s updated=%s ignored=%s ignored_reasons=%s pk=%s",
                tenant.id,
                cnpj,
                data_type,
                stats["destination_table"],
                stats["received"],
                stats["inserted"],
                stats["updated"],
                stats["ignored"],
                stats["ignored_reasons"],
                stats["pk_columns"],
            )
            return stats

        except Exception as exc:
            db.rollback()
            logger.exception("[SYNC] Erro ao processar data_type=%s tenant_id=%s", data_type, tenant.id)
            job.status = "FAILED"
            job.error_message = str(exc)
            job.records_synced = 0
            job.finished_at = datetime.now()
            db.commit()
            return {
                "success": False,
                "data_type": data_type,
                "destination_table": data_type,
                "received": received,
                "inserted": 0,
                "updated": 0,
                "ignored": received,
                "ignored_reasons": {"exception": received or 1},
                "pk_columns": [],
                "error": str(exc),
            }

    @staticmethod
    def _sync_generic_table(
        db: Session,
        tenant_id: str,
        table_name: str,
        rows: List[Dict],
        legacy_pk: List[str] | None = None,
    ) -> Dict:
        stats = {
            "success": True,
            "destination_table": table_name,
            "received": len(rows) if isinstance(rows, list) else 0,
            "inserted": 0,
            "updated": 0,
            "ignored": 0,
            "ignored_reasons": {},
            "pk_columns": [],
        }

        if not isinstance(rows, list) or not rows:
            if stats["received"]:
                SyncService._increment_ignored(stats, "invalid_or_empty_content", stats["received"])
            return stats

        dict_rows = []
        columns = []
        for row in rows:
            if not isinstance(row, dict):
                SyncService._increment_ignored(stats, "row_not_object")
                continue
            dict_rows.append(row)
            for column in row.keys():
                if column not in columns:
                    columns.append(column)

        if not dict_rows:
            return stats

        if "tenant_id" not in columns:
            columns.append("tenant_id")

        sample_row = dict_rows[0]
        pks = SyncService._resolve_pk_columns(table_name, sample_row, legacy_pk)
        pks_with_tenant = ["tenant_id"] + pks
        stats["pk_columns"] = pks_with_tenant

        unique_rows = []
        seen_pks = set()
        for row in dict_rows:
            row["tenant_id"] = tenant_id
            pk_values = tuple(str(row.get(pk)) if pk == "tenant_id" else row.get(pk) for pk in pks_with_tenant)
            if any(value is None or str(value).strip() == "" for value in pk_values):
                SyncService._increment_ignored(stats, "incomplete_primary_key")
                logger.warning(
                    "[SYNC] ignored table=%s reason=incomplete_primary_key pk=%s row=%s",
                    table_name,
                    pks_with_tenant,
                    row,
                )
                continue
            if pk_values in seen_pks:
                SyncService._increment_ignored(stats, "duplicate_in_payload")
                continue
            seen_pks.add(pk_values)
            unique_rows.append(row)

        if not unique_rows:
            return stats

        SyncService._ensure_table_and_columns(db, table_name, columns, pks_with_tenant)
        existing_pk_values = SyncService._existing_pk_values(db, table_name, pks_with_tenant, unique_rows)
        stats["updated"] = len(existing_pk_values)
        stats["inserted"] = len(unique_rows) - stats["updated"]

        col_names = ", ".join([f'"{column}"' for column in columns])
        update_cols = [column for column in columns if column not in pks_with_tenant]
        set_clause = (
            ", ".join([f'"{column}" = EXCLUDED."{column}"' for column in update_cols])
            if update_cols
            else f'"{columns[0]}" = EXCLUDED."{columns[0]}"'
        )
        conflict_cols = ", ".join([f'"{column}"' for column in pks_with_tenant])

        chunk_size = 500
        for index in range(0, len(unique_rows), chunk_size):
            chunk = unique_rows[index : index + chunk_size]
            values_clauses = []
            flat_params = {}

            for row_index, row in enumerate(chunk):
                row_placeholders = []
                for column in columns:
                    param_key = f"{column}_{row_index}"
                    row_placeholders.append(f":{param_key}")
                    value = str(tenant_id) if column == "tenant_id" else row.get(column)
                    if isinstance(value, str) and value.strip() == "":
                        value = None
                    elif isinstance(value, float) and value.is_integer():
                        value = int(value)
                    flat_params[param_key] = value
                values_clauses.append(f"({', '.join(row_placeholders)})")

            bulk_sql = text(
                f"""
                INSERT INTO public."{table_name}" ({col_names})
                VALUES {", ".join(values_clauses)}
                ON CONFLICT ({conflict_cols})
                DO UPDATE SET {set_clause};
                """
            )
            db.execute(bulk_sql, flat_params)
            db.commit()

        return stats

    @staticmethod
    def _ensure_table_and_columns(db: Session, table_name: str, columns: List[str], pk_columns: List[str]) -> None:
        field_defs = [SyncService._column_definition(column) for column in columns]
        fields_sql = ",\n            ".join(field_defs)
        pk_cols = ", ".join([f'"{column}"' for column in pk_columns])

        db.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS public."{table_name}" (
                    {fields_sql},
                    PRIMARY KEY ({pk_cols})
                );
                """
            )
        )
        db.commit()

        existing_columns = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).fetchall()
        }
        for definition in field_defs:
            column_name = definition.split('"', 2)[1]
            if column_name not in existing_columns:
                db.execute(text(f'ALTER TABLE public."{table_name}" ADD COLUMN IF NOT EXISTS {definition}'))
        db.commit()

    @staticmethod
    def _column_definition(column: str) -> str:
        upper = column.upper()
        if column == "tenant_id":
            return f'"{column}" TEXT NOT NULL'
        if any(token in upper for token in ["VALOR", "TOTAL", "QUANTIDADE", "PRECO", "ESTOQUE", "CUSTO"]):
            return f'"{column}" NUMERIC(18,4)'
        if any(token in upper for token in ["_DT_", "DATA"]):
            return f'"{column}" TIMESTAMP'
        return f'"{column}" TEXT'

    @staticmethod
    def _existing_pk_values(db: Session, table_name: str, pk_columns: List[str], rows: List[Dict]) -> set:
        existing = set()
        for row in rows:
            where_sql = " AND ".join([f'"{column}" = :{column}' for column in pk_columns])
            params = {column: str(row.get(column)) if column == "tenant_id" else row.get(column) for column in pk_columns}
            found = db.execute(
                text(f'SELECT 1 FROM public."{table_name}" WHERE {where_sql} LIMIT 1'),
                params,
            ).scalar()
            if found:
                existing.add(tuple(params[column] for column in pk_columns))
        return existing

    @staticmethod
    def _increment_ignored(stats: Dict, reason: str, amount: int = 1) -> None:
        stats["ignored"] += amount
        stats["ignored_reasons"][reason] = stats["ignored_reasons"].get(reason, 0) + amount

    @staticmethod
    def _resolve_pk_columns(table_name: str, sample_row: Dict, legacy_pk: List[str] | None = None) -> List[str]:
        configured = legacy_pk or SyncService.TABLE_PK_MAP.get(table_name, ["ID"])
        available = set(sample_row.keys())
        resolved = [pk for pk in configured if pk in available]
        if resolved:
            return resolved

        id_columns = [column for column in sample_row.keys() if column.upper().endswith("_ID") or column.upper() == "ID"]
        if id_columns:
            logger.warning("[SYNC] PK configurada ausente para %s. Usando candidatas: %s", table_name, id_columns)
            return id_columns[:3]

        fallback = list(sample_row.keys())[:5]
        logger.warning("[SYNC] PK nao encontrada para %s. Usando fallback: %s", table_name, fallback)
        return fallback
