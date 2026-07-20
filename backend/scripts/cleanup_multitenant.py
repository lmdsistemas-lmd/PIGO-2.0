from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal


GENERIC_TENANT_SQL = """
SELECT id, cnpj, razao_social, nome_fantasia
FROM tenants
WHERE lower(coalesce(razao_social, '') || ' ' || coalesce(nome_fantasia, '')) LIKE '%teste%'
   OR lower(coalesce(razao_social, '')) LIKE '%cliente licenca%'
   OR lower(coalesce(razao_social, '')) LIKE '%empresa license control%'
ORDER BY cnpj
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpeza segura de tenants genericos/de teste.")
    parser.add_argument("--apply", action="store_true", help="Aplica a remocao. Sem isto, roda em modo dry-run.")
    parser.add_argument(
        "--cnpj",
        action="append",
        default=[],
        help="Restringe a remocao a um CNPJ normalizado especifico. Pode repetir.",
    )
    args = parser.parse_args()

    allowed_cnpjs = {value for value in args.cnpj}

    with SessionLocal() as db:
        rows = db.execute(text(GENERIC_TENANT_SQL)).mappings().all()
        targets = [
            row
            for row in rows
            if not allowed_cnpjs or str(row["cnpj"]) in allowed_cnpjs
        ]

        if not targets:
            print("Nenhum tenant generico/de teste encontrado para os filtros informados.")
            return

        print("Tenants candidatos a remocao:")
        for row in targets:
            print(f"- id={row['id']} cnpj={row['cnpj']} razao_social={row['razao_social']} fantasia={row['nome_fantasia']}")

        if not args.apply:
            print("Dry-run: nada foi removido. Use --apply para aplicar.")
            return

        for row in targets:
            db.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": row["id"]})

        db.commit()
        print(f"Removidos {len(targets)} tenant(s).")


if __name__ == "__main__":
    main()
