from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import text

from app.database.connection import SessionLocal
from app.services.municipality_coordinate_resolver import (
    MunicipalityCoordinateResolver,
    normalize_ibge_code,
)


DEFAULT_CATALOG = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "municipality_geocodes_ibge_2022.csv"
)


def load_catalog(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as catalog:
        for line_number, row in enumerate(csv.DictReader(catalog), start=2):
            code = normalize_ibge_code(row.get("ibge_code"))
            if not code:
                raise ValueError(f"Código IBGE inválido na linha {line_number}.")
            if code in seen:
                raise ValueError(f"Código IBGE duplicado: {code}.")
            seen.add(code)
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError(f"Coordenada inválida para {code}.")
            rows.append(
                {
                    "ibge_code": code,
                    "name": row["name"].strip(),
                    "state_code": row["state_code"].strip().upper(),
                    "latitude": latitude,
                    "longitude": longitude,
                    "coordinate_type": row.get("coordinate_type")
                    or "MUNICIPAL_SEAT",
                    "source": row.get("source") or "IBGE",
                    "source_version": row.get("source_version")
                    or "Localidades do Brasil 2022",
                }
            )
    return rows


def import_catalog(path: Path, dry_run: bool = False) -> int:
    rows = load_catalog(path)
    if dry_run:
        return len(rows)

    statement = text(
        """
        INSERT INTO municipality_geocodes (
            ibge_code, name, state_code, latitude, longitude,
            coordinate_type, source, source_version, updated_at
        ) VALUES (
            :ibge_code, :name, :state_code, :latitude, :longitude,
            :coordinate_type, :source, :source_version, now()
        )
        ON CONFLICT (ibge_code) DO UPDATE SET
            name = EXCLUDED.name,
            state_code = EXCLUDED.state_code,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            coordinate_type = EXCLUDED.coordinate_type,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
            updated_at = now()
        """
    )
    with SessionLocal.begin() as db:
        for start in range(0, len(rows), 500):
            db.execute(statement, rows[start : start + 500])
    MunicipalityCoordinateResolver.clear_cache()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa o catálogo municipal local sem chamadas externas."
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = import_catalog(args.file, dry_run=args.dry_run)
    print(f"municipality_geocodes rows={count} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
