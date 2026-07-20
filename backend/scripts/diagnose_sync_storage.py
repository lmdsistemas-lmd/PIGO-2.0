import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text

from app.database.connection import SessionLocal


TARGET_CNPJS = ["16609331000163", "47645430000124"]
EMPRESA_COLUMNS = [
    "EMP_ID",
    "PEV_EMPRESA",
    "PEVI_EMPRESA",
    "PRD_EMPRESA",
    "PRDE_EMPRESA",
    "REC_EMPRESA",
    "PAG_EMPRESA",
    "AUD_EMPRESA",
    "COL_EMPRESA",
    "CLI_EMPRESA",
]


def fetch_all(db, sql, params=None):
    return [dict(row) for row in db.execute(text(sql), params or {}).mappings().all()]


def tenant_tables(db):
    return fetch_all(
        db,
        """
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'tenant_id'
        ORDER BY table_name
        """,
    )


def table_columns(db, table_name):
    rows = fetch_all(
        db,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
        ORDER BY ordinal_position
        """,
        {"table_name": table_name},
    )
    return [row["column_name"] for row in rows]


def table_pk(db, table_name):
    rows = fetch_all(
        db,
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE tc.table_schema = 'public'
          AND tc.table_name = :table_name
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        {"table_name": table_name},
    )
    return [row["column_name"] for row in rows]


def count_by_tenant(db, table_name):
    return fetch_all(
        db,
        f"""
        SELECT t.cnpj, t.razao_social, x.tenant_id::text, COUNT(*) AS total
        FROM public."{table_name}" x
        LEFT JOIN tenants t ON t.id::text = x.tenant_id::text
        GROUP BY t.cnpj, t.razao_social, x.tenant_id
        ORDER BY total DESC, t.cnpj NULLS LAST
        """,
    )


def orphan_count(db, table_name):
    return fetch_all(
        db,
        f"""
        SELECT COUNT(*) AS total
        FROM public."{table_name}" x
        LEFT JOIN tenants t ON t.id::text = x.tenant_id::text
        WHERE x.tenant_id IS NULL OR t.id IS NULL
        """,
    )[0]["total"]


def target_counts(db, table_name):
    return fetch_all(
        db,
        f"""
        SELECT t.cnpj, x.tenant_id::text, COUNT(*) AS total
        FROM public."{table_name}" x
        JOIN tenants t ON t.id::text = x.tenant_id::text
        WHERE t.cnpj = ANY(:cnpjs)
        GROUP BY t.cnpj, x.tenant_id
        ORDER BY t.cnpj
        """,
        {"cnpjs": TARGET_CNPJS},
    )


def empresa_mix(db, table_name, columns):
    findings = []
    available = set(columns)
    for column in EMPRESA_COLUMNS:
        if column not in available:
            continue
        rows = fetch_all(
            db,
            f"""
            SELECT "{column}"::text AS empresa_id_origem,
                   COUNT(DISTINCT tenant_id) AS tenants,
                   ARRAY_AGG(DISTINCT tenant_id::text) AS tenant_ids,
                   COUNT(*) AS total
            FROM public."{table_name}"
            WHERE "{column}" IS NOT NULL
            GROUP BY "{column}"
            HAVING COUNT(DISTINCT tenant_id) > 1
            ORDER BY total DESC
            LIMIT 20
            """,
        )
        if rows:
            findings.append({"column": column, "rows": rows})
    return findings


def latest_sync_jobs(db):
    return fetch_all(
        db,
        """
        SELECT j.id::text,
               j.tenant_id::text,
               t.cnpj,
               t.razao_social,
               j.table_name,
               j.status,
               j.records_synced,
               j.error_message,
               j.started_at,
               j.finished_at
        FROM sync_jobs j
        LEFT JOIN tenants t ON t.id = j.tenant_id
        ORDER BY j.started_at DESC
        LIMIT 50
        """,
    )


def target_tenants(db):
    return fetch_all(
        db,
        """
        SELECT id::text,
               cnpj,
               razao_social,
               nome_fantasia,
               status,
               license_status,
               has_pigo_access,
               api_token_active,
               api_token_last_used_at
        FROM tenants
        WHERE cnpj = ANY(:cnpjs)
        ORDER BY cnpj
        """,
        {"cnpjs": TARGET_CNPJS},
    )


def main():
    db = SessionLocal()
    try:
        report = {
            "target_cnpjs": TARGET_CNPJS,
            "target_tenants": target_tenants(db),
            "latest_sync_jobs": latest_sync_jobs(db),
            "tables": {},
            "orphan_tables": [],
            "possible_empresa_id_mix": {},
            "updated_by_last_sync": [],
        }

        jobs = report["latest_sync_jobs"]
        report["updated_by_last_sync"] = [
            {
                "table_name": job["table_name"],
                "tenant_id": job["tenant_id"],
                "cnpj": job["cnpj"],
                "status": job["status"],
                "records_synced": job["records_synced"],
                "started_at": str(job["started_at"]) if job["started_at"] else None,
                "finished_at": str(job["finished_at"]) if job["finished_at"] else None,
            }
            for job in jobs[:10]
        ]

        for row in tenant_tables(db):
            table_name = row["table_name"]
            columns = table_columns(db, table_name)
            orphan_total = int(orphan_count(db, table_name))
            mix = empresa_mix(db, table_name, columns)
            report["tables"][table_name] = {
                "primary_key": table_pk(db, table_name),
                "empresa_columns": [column for column in EMPRESA_COLUMNS if column in columns],
                "count_by_tenant": count_by_tenant(db, table_name),
                "target_counts": target_counts(db, table_name),
                "orphan_count": orphan_total,
            }
            if orphan_total:
                report["orphan_tables"].append({"table_name": table_name, "orphan_count": orphan_total})
            if mix:
                report["possible_empresa_id_mix"][table_name] = mix

        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
