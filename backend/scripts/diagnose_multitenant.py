from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal


def fetch_all(db, sql: str, params: dict | None = None):
    return [dict(row) for row in db.execute(text(sql), params or {}).mappings().all()]


def main() -> None:
    with SessionLocal() as db:
        synced_tables = fetch_all(
            db,
            """
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name = 'tenant_id'
            ORDER BY table_name
            """,
        )

        missing_or_null_tenant = []
        tenant_empresa_collisions = []
        for item in synced_tables:
            table_name = item["table_name"]
            null_count = db.execute(
                text(f'SELECT COUNT(*) FROM public."{table_name}" WHERE tenant_id IS NULL'),
            ).scalar()
            if null_count:
                missing_or_null_tenant.append({"table": table_name, "null_tenant_id": int(null_count)})

            empresa_columns = fetch_all(
                db,
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND upper(column_name) IN (
                    'EMP_ID', 'EMPRESA_ID', 'EMPRESA', 'PEV_EMPRESA', 'REC_EMPRESA',
                    'PAG_EMPRESA', 'PRDE_EMPRESA', 'COL_EMPRESA', 'AUD_EMPRESA'
                  )
                """,
                {"table_name": table_name},
            )
            for col in empresa_columns:
                column_name = col["column_name"]
                collisions = fetch_all(
                    db,
                    f"""
                    SELECT "{column_name}" AS empresa_id, COUNT(DISTINCT tenant_id) AS tenants
                    FROM public."{table_name}"
                    WHERE "{column_name}" IS NOT NULL
                    GROUP BY "{column_name}"
                    HAVING COUNT(DISTINCT tenant_id) > 1
                    LIMIT 20
                    """,
                )
                if collisions:
                    tenant_empresa_collisions.append(
                        {
                            "table": table_name,
                            "column": column_name,
                            "samples": collisions,
                        }
                    )

        report = {
            "duplicate_tokens": fetch_all(
                db,
                """
                SELECT api_token::text AS api_token, COUNT(*) AS total
                FROM tenants
                WHERE api_token IS NOT NULL
                GROUP BY api_token
                HAVING COUNT(*) > 1
                """,
            ),
            "duplicate_cnpj": fetch_all(
                db,
                """
                SELECT regexp_replace(cnpj, '\\D', '', 'g') AS cnpj, COUNT(*) AS total
                FROM tenants
                GROUP BY regexp_replace(cnpj, '\\D', '', 'g')
                HAVING COUNT(*) > 1
                """,
            ),
            "tokens_without_active_access": fetch_all(
                db,
                """
                SELECT id::text, cnpj, razao_social, api_token::text, api_token_active, has_pigo_access
                FROM tenants
                WHERE api_token IS NOT NULL
                  AND (api_token_active IS NOT TRUE OR has_pigo_access IS NOT TRUE)
                ORDER BY cnpj
                """,
            ),
            "generic_or_test_tenants": fetch_all(
                db,
                """
                SELECT id::text, cnpj, razao_social, nome_fantasia, license_control_id
                FROM tenants
                WHERE lower(coalesce(razao_social, '') || ' ' || coalesce(nome_fantasia, '')) LIKE '%teste%'
                   OR lower(coalesce(razao_social, '')) LIKE '%cliente licenca%'
                   OR lower(coalesce(razao_social, '')) LIKE '%empresa license control%'
                ORDER BY cnpj
                """,
            ),
            "tables_with_null_tenant_id": missing_or_null_tenant,
            "same_empresa_id_across_tenants": tenant_empresa_collisions,
        }

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
