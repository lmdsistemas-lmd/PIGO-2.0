from pathlib import Path

from sqlalchemy import text

from app.database.connection import engine


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def main() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with engine.begin() as connection:
        for migration_file in migration_files:
            sql = migration_file.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                if statement.strip():
                    connection.execute(text(statement))
            print(f"aplicada: {migration_file.name}")


if __name__ == "__main__":
    main()
