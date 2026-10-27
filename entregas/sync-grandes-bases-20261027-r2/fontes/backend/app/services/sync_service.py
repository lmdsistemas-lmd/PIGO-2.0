import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.saas import SyncJob, Tenant
from app.services.sync_batch import validate_batch, begin_batch, save_receipt


logger = logging.getLogger(__name__)


class SyncService:
    STRICT_PK_TABLES = {
        "TB_PEDIDO_VENDA_ITEM",
        "TB_PEDIDO_VENDA_FIN",
        "TB_FECHAMENTO_CAIXA",
        "TB_FECHAMENTO_CAIXA_ITEM",
        "TB_FECHAMENTO_CAIXA_VENDA",
        "TB_MOVIMENTO_CAIXA",
    }
    ERP_COMPANY_ALIAS_TABLES = {
        "TB_FECHAMENTO_CAIXA",
        "TB_FECHAMENTO_CAIXA_ITEM",
        "TB_FECHAMENTO_CAIXA_VENDA",
        "TB_MOVIMENTO_CAIXA",
    }

    TABLE_PK_MAP = {
        "TB_EMPRESA": ["EMP_ID"],
        "TB_PESSOA": ["PES_ID"],
        "TB_CLIENTE": ["CLI_PESSOA"],
        "TB_VENDEDOR": ["VDR_PESSOA"],
        "TB_CIDADE": ["CID_ID"],
        "TB_PEDIDO_VENDA": ["PEV_ID"],
        "TB_PEDIDO_VENDA_ITEM": ["PEVI_EMPRESA", "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA"],
        "TB_PRODUTO": ["PRD_ID"],
        "TB_PRODUTO_ESTOQUE": ["PRDE_PRODUTO", "PRDE_EMPRESA"],
        "TB_PROD_CODIGO_BARRAS": ["PRDC_PRODUTO", "PRDC_COD_BARRAS"],
        "TB_PRODUTO_PRECO": ["PRDP_PRODUTO", "PRDP_EMPRESA"],
        "TB_RECEBIMENTO": ["REC_ID"],
        "TB_PAGAMENTO": ["PAG_ID"],
        "TB_AUDITORIA": ["AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA"],
        "TB_USUARIO": ["USU_ID"],
        "TB_COLABORADOR": ["COL_PESSOA"],
        "TB_PROD_GRUPO": ["PGRU_ID"],
        "TB_PROD_MARCA": ["PMAR_ID"],
        "TB_FORNECEDOR": ["FOR_PESSOA", "FOR_EMPRESA"],
        "TB_PROD_DEPARTAMENTO": ["PDEP_ID"],
        "TB_PROD_SUBGRUPO": ["PSGR_ID"],
        "TB_PLANO_CONTA": ["PLC_ID"],
        "TB_FECHAMENTO_CAIXA_FORMA": ["FCF_ID", "FCF_EMPRESA"],
        "TB_PIGO_CAIXA_MOVIMENTO": ["FCI_ID", "FCI_EMPRESA"],
        "TB_CAIXA_SANGRIA": ["SAN_ID", "SAN_EMPRESA"],
        "TB_CHEQUE_EMITIDO": ["CHQ_ID", "CHQ_EMPRESA"],
        "TB_ESPECIE_MOEDA": ["ESP_ID"],
        "TB_PEDIDO_VENDA_FIN": ["PEVF_EMPRESA", "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA"],
        "TB_FECHAMENTO_CAIXA": ["erp_company_id", "FCX_ID"],
        "TB_FECHAMENTO_CAIXA_ITEM": ["erp_company_id", "FCXI_FECHAMENTO", "FCXI_SEQUENCIA"],
        "TB_FECHAMENTO_CAIXA_VENDA": ["erp_company_id", "FCXV_FECHAMENTO", "FCXV_SEQUENCIA"],
        "TB_MOVIMENTO_CAIXA": ["erp_company_id", "MOV_ID"],
    }
    TABLE_KEY_VARIANTS = {'TB_PEDIDO_VENDA': [['PEV_EMPRESA', 'PEV_ID'], ['PEV_ID']],
     'TB_RECEBIMENTO': [['REC_EMPRESA', 'REC_ID'], ['REC_ID']],
     'TB_PAGAMENTO': [['PAG_EMPRESA', 'PAG_ID'], ['PAG_ID']],
     'TB_PRODUTO_ESTOQUE': [['PRDE_PRODUTO', 'PRDE_EMPRESA', 'PRDE_LOCAL', 'PRDE_VARIACAO'],
                            ['PRDE_PRODUTO', 'PRDE_EMPRESA']],
     'TB_PEDIDO_VENDA_ITEM': [['PEVI_EMPRESA', 'PEVI_PEDIDO_VENDA', 'PEVI_SEQUENCIA'],
                              ['PEVI_PEDIDO_VENDA', 'PEVI_EMPRESA', 'PEVI_PRODUTO']],
     'TB_PEDIDO_VENDA_FIN': [['PEVF_EMPRESA', 'PEVF_PEDIDO_VENDA', 'PEVF_SEQUENCIA'],
                             ['PEVF_PEDIDO_VENDA', 'PEVF_EMPRESA', 'PEVF_ESPECIE_MOEDA']],
     'TB_FECHAMENTO_CAIXA_ITEM': [['FCXI_EMPRESA', 'FCXI_FECHAMENTO', 'FCXI_SEQUENCIA'],
                                  ['FCI_ID', 'FCI_EMPRESA']]}

    @staticmethod
    def process_sync_data(db: Session, tenant: Tenant, cnpj: str, data_type: str, content: Any, batch=None, installation_id=None) -> Dict:
        if not tenant:
            raise ValueError(f"Tenant nao encontrado para o CNPJ: {cnpj}")

        if batch is not None:
            return SyncService._process_batch(db, tenant, cnpj, data_type, content, batch, installation_id)

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

            # A invalidação ocorre somente após a persistência e o job terem commitado.
            from app.services.erp_query_service import clear_erp_query_cache
            from app.services.dashboard_financeiro_service import clear_dashboard_financeiro_cache
            from app.services.report_engine import clear_report_cache

            clear_erp_query_cache(str(tenant.id))
            clear_dashboard_financeiro_cache(str(tenant.id))
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
    def _process_batch(db, tenant, cnpj, data_type, content, batch, installation_id):
        received = len(content) if isinstance(content, list) else 0
        try:
            if data_type not in SyncService.TABLE_PK_MAP:
                raise ValueError("SYNC_TABLE_NOT_SUPPORTED")
            batch_id, digest, keys = validate_batch(data_type, content, batch)
            tenant_id = str(tenant.id)
            installation = str(installation_id or "legacy")
            previous = begin_batch(db, tenant_id, installation, batch_id, digest)
            if previous is not None:
                db.commit()
                return previous
            stats = SyncService._sync_generic_table(db, tenant_id, data_type, content,
                                                   atomic=True, strict=True, key_columns=keys)
            stats.update(protocol_version=2, batch_id=batch_id, payload_sha256=digest,
                         persisted=stats["inserted"] + stats["updated"], replayed=False)
            if stats["ignored"] or stats["persisted"] != received:
                raise ValueError("SYNC_BATCH_INCOMPLETE")
            job = SyncJob(tenant_id=tenant.id, status="COMPLETED", table_name=data_type,
                          records_synced=stats["persisted"], started_at=datetime.now(), finished_at=datetime.now())
            db.add(job)
            save_receipt(db, tenant_id, installation, batch_id, digest, stats)
            db.commit()  # Business rows, job, audit and receipt commit together.
        except Exception as exc:
            db.rollback()
            code = str(exc) if isinstance(exc, ValueError) else "SYNC_BATCH_PERSISTENCE_FAILED"
            if not code.startswith(("SYNC_", "MIRROR_KEY_MIGRATION_REQUIRED")):
                code = "SYNC_BATCH_PERSISTENCE_FAILED"
            logger.error("[SYNC_LOTE] falha table=%s tenant=%s exception=%s sqlstate=%s code=%s",
                         data_type, tenant.id, type(exc).__name__, getattr(getattr(exc,"orig",None),"sqlstate",None), code)
            return {"success": False, "received": received, "inserted": 0, "updated": 0,
                    "ignored": received, "error": code}
        # Cache invalidation is after commit and cannot turn a committed batch into a failure.
        try:
            from app.services.erp_query_service import clear_erp_query_cache
            from app.services.dashboard_financeiro_service import clear_dashboard_financeiro_cache
            from app.services.report_engine import clear_report_cache
            clear_erp_query_cache(tenant_id)
            clear_dashboard_financeiro_cache(tenant_id)
            clear_report_cache(tenant_id)
        except Exception as exc:
            logger.warning("[SYNC_LOTE] cache_invalidacao exception=%s", type(exc).__name__)
        return stats

    @staticmethod
    def _sync_generic_table(
        db: Session,
        tenant_id: str,
        table_name: str,
        rows: List[Dict],
        legacy_pk: List[str] | None = None,
        atomic: bool = False, strict: bool = False, key_columns=None,
    ) -> Dict:
        if not isinstance(table_name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", table_name):
            raise ValueError("Nome de tabela de sincronização inválido.")
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
            row = SyncService._normalize_row_contract(table_name, row)
            dict_rows.append(row)
            for column in row.keys():
                if not isinstance(column, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", column):
                    raise ValueError("Nome de campo de sincronização inválido.")
                if column not in columns:
                    columns.append(column)

        if not dict_rows:
            return stats

        if "tenant_id" not in columns:
            columns.append("tenant_id")

        # Resolve from the complete payload shape. An incomplete first row must
        # not force a legacy key that collapses later physical positions.
        sample_row = dict.fromkeys(column for column in columns if column != "tenant_id")
        pks = SyncService._resolve_pk_columns(table_name, sample_row, legacy_pk)
        if key_columns is not None:
            required_keys = SyncService.TABLE_PK_MAP.get(table_name, pks)
            if not set(required_keys) <= set(key_columns) or not set(key_columns) <= set(sample_row) or "tenant_id" in key_columns:
                raise ValueError("SYNC_PHYSICAL_KEY_MISMATCH")
            pks = list(key_columns)
        if key_columns is None:
            stored = [row[0] for row in db.execute(text('''SELECT k.column_name
                FROM information_schema.table_constraints t
                JOIN information_schema.key_column_usage k
                ON t.constraint_name=k.constraint_name AND t.table_schema=k.table_schema AND t.table_name=k.table_name
                WHERE t.table_schema='public' AND t.table_name=:table AND t.constraint_type='PRIMARY KEY'
                ORDER BY k.ordinal_position'''), {"table": table_name}).all() if row[0] != "tenant_id"]
            if stored and set(pks) < set(stored):
                if not set(stored) <= set(sample_row):
                    raise ValueError("MIRROR_KEY_MIGRATION_REQUIRED: " + table_name + " requer os campos da chave fisica existente.")
                pks = stored
                strict = True
        pks_with_tenant = ["tenant_id"] + pks
        stats["pk_columns"] = pks_with_tenant

        unique_rows = []
        seen_pks = set()
        for row in dict_rows:
            row["tenant_id"] = tenant_id
            pk_values = tuple(str(row.get(pk)) if pk == "tenant_id" else row.get(pk) for pk in pks_with_tenant)
            if any(value is None or str(value).strip() == "" for value in pk_values):
                SyncService._increment_ignored(stats, "incomplete_primary_key")
                logger.warning("[SYNC] ignored table=%s reason=incomplete_primary_key pk=%s", table_name, pks_with_tenant)
                continue
            if pk_values in seen_pks:
                SyncService._increment_ignored(stats, "duplicate_in_payload")
                continue
            seen_pks.add(pk_values)
            unique_rows.append(row)

        if strict and stats["ignored"]:
            raise ValueError("SYNC_BATCH_INVALID_ROWS")
        if not unique_rows:
            return stats

        SyncService._ensure_table_and_columns(db, table_name, columns, pks_with_tenant, commit=not atomic)
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
            if atomic:
                returning = text(bulk_sql.text.rstrip().rstrip(";") + " RETURNING 1")
                persisted = db.execute(returning, flat_params).fetchall()
                if len(persisted) != len(chunk):
                    raise ValueError("SYNC_BATCH_INCOMPLETE")
            else:
                db.execute(bulk_sql, flat_params)
                db.commit()

        return stats

    @staticmethod
    def _ensure_table_and_columns(db: Session, table_name: str, columns: List[str], pk_columns: List[str], commit: bool = True) -> None:
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
        if commit:
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
        constraints = db.execute(text('''SELECT tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema AND tc.table_name=kcu.table_name
            WHERE tc.table_schema='public' AND tc.table_name=:table AND tc.constraint_type='PRIMARY KEY'
            ORDER BY kcu.ordinal_position'''), {"table": table_name}).all()
        existing_keys = [row[1] for row in constraints]
        if constraints and set(existing_keys) != set(pk_columns):
            if not set(existing_keys) <= set(pk_columns):
                raise ValueError("MIRROR_KEY_MIGRATION_REQUIRED: " + table_name + " nao permite reduzir ou substituir a chave existente durante o envio.")
            # Re-key only when the physical key is present on every stored row.
            # Never invent line sequences, discard old rows or silently merge items.
            missing = " OR ".join(f'"{column}" IS NULL' for column in pk_columns)
            if db.execute(text(f'SELECT 1 FROM public."{table_name}" WHERE {missing} LIMIT 1')).first():
                db.rollback()
                raise ValueError(f"MIRROR_KEY_MIGRATION_REQUIRED: {table_name} contém registros sem a chave física recebida. Preserve o espelho e homologue a carga com as sequências do ERP antes de migrar.")
            constraint = constraints[0][0].replace('"', '""')
            db.execute(text(f'ALTER TABLE public."{table_name}" DROP CONSTRAINT "{constraint}"'))
            for _, column in constraints:
                if column not in pk_columns:
                    db.execute(text(f'ALTER TABLE public."{table_name}" ALTER COLUMN "{column}" DROP NOT NULL'))
            db.execute(text(f'ALTER TABLE public."{table_name}" ADD PRIMARY KEY ({pk_cols})'))
        if commit:
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
        # One indexed lookup per bounded group, rather than one round trip per record.
        for start in range(0, len(rows), 500):
            group = rows[start:start + 500]
            params, predicates = {}, []
            for index, row in enumerate(group):
                placeholders = []
                for key_index, column in enumerate(pk_columns):
                    parameter = f"pk_{index}_{key_index}"
                    value = row.get(column)
                    params[parameter] = str(value) if value is not None else None
                    placeholders.append(":" + parameter)
                predicates.append("(" + ",".join(placeholders) + ")")
            columns = ",".join('"' + column + '"' for column in pk_columns)
            found = db.execute(text(f'SELECT {columns} FROM public."{table_name}" WHERE ({columns}) IN (' +
                                         ",".join(predicates) + ")"), params).fetchall()
            existing.update(tuple(str(value) for value in row) for row in found)
        return existing

    @staticmethod
    def _increment_ignored(stats: Dict, reason: str, amount: int = 1) -> None:
        stats["ignored"] += amount
        stats["ignored_reasons"][reason] = stats["ignored_reasons"].get(reason, 0) + amount

    @staticmethod
    def _resolve_pk_columns(table_name: str, sample_row: Dict, legacy_pk: List[str] | None = None) -> List[str]:
        if not legacy_pk and table_name in SyncService.ERP_COMPANY_ALIAS_TABLES and "erp_company_id" in sample_row:
            return list(SyncService.TABLE_PK_MAP[table_name])
        if not legacy_pk and table_name == "TB_PRODUTO_ESTOQUE" and {"PRDE_LOCAL", "PRDE_VARIACAO"} & set(sample_row):
            physical = SyncService.TABLE_KEY_VARIANTS[table_name][0]
            if not set(physical) <= set(sample_row):
                raise ValueError("Chave física incompleta para TB_PRODUTO_ESTOQUE: informe local e variação.")
        if not legacy_pk and table_name in SyncService.TABLE_KEY_VARIANTS:
            for candidate in SyncService.TABLE_KEY_VARIANTS[table_name]:
                if set(candidate) <= set(sample_row):
                    return candidate
            raise ValueError(f"Chave física incompleta para {table_name}.")
        configured = legacy_pk or SyncService.TABLE_PK_MAP.get(table_name, ["ID"])
        # A tabela de itens não possui um identificador artificial. A chave
        # física completa deve ser preservada mesmo quando o payload vier
        # incompleto, para que a linha seja rejeitada em vez de sofrer upsert
        # por uma chave parcial.
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

    @staticmethod
    def _normalize_row_contract(table_name: str, row: Dict) -> Dict:
        normalized = dict(row)
        if table_name not in SyncService.ERP_COMPANY_ALIAS_TABLES:
            return normalized

        upper_value = normalized.pop("ERP_COMPANY_ID", None)
        lower_value = normalized.get("erp_company_id")
        if lower_value is not None and upper_value is not None and str(lower_value) != str(upper_value):
            raise ValueError(
                f"{table_name}: ERP_COMPANY_ID diverge de erp_company_id"
            )
        company_column = {"TB_FECHAMENTO_CAIXA": "FCX_EMPRESA", "TB_FECHAMENTO_CAIXA_ITEM": "FCXI_EMPRESA", "TB_FECHAMENTO_CAIXA_VENDA": "FCXV_EMPRESA", "TB_MOVIMENTO_CAIXA": "MOV_EMPRESA"}[table_name]
        values = [value for value in (lower_value, upper_value, normalized.get(company_column)) if value is not None]
        if values and any(str(value) != str(values[0]) for value in values):
            raise ValueError(f"{table_name}: empresa fisica diverge de erp_company_id")
        if values:
            normalized["erp_company_id"] = values[0]
            normalized[company_column] = values[0]
        return normalized
