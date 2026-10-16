import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database.connection import SessionLocal


SQL = """
SELECT
    id::text,
    cnpj,
    razao_social,
    nome_fantasia,
    email,
    has_pigo_access,
    license_status,
    license_expires_at AS expires_at,
    api_token_active,
    updated_at
FROM tenants
ORDER BY updated_at DESC;
"""


def main():
    with SessionLocal() as db:
        rows = db.execute(text(SQL)).mappings().all()
        print(json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
