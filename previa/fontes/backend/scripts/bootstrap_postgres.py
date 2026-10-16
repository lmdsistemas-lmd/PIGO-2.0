import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
MIGRATION_FILE = BACKEND_DIR / "migrations" / "001_init_postgresql.sql"

sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import DATABASE_URL  # noqa: E402


def _psql_base_args(database_url: str, database: str | None = None):
    parsed = urlparse(database_url.replace("postgresql+pg8000://", "postgresql://"))
    dbname = database or parsed.path.lstrip("/") or "postgres"
    args = ["psql", "-v", "ON_ERROR_STOP=1", "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432)]
    if parsed.username:
        args.extend(["-U", parsed.username])
    args.extend(["-d", dbname])
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    return args, env, dbname


def run_psql(database: str, sql: str) -> None:
    args, env, _ = _psql_base_args(DATABASE_URL, database)
    subprocess.run(args + ["-c", sql], check=True, cwd=PROJECT_DIR, env=env)


def query_psql(database: str, sql: str) -> str:
    args, env, _ = _psql_base_args(DATABASE_URL, database)
    result = subprocess.run(
        args + ["-tAc", sql],
        check=True,
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_database_if_missing(database_url: str, target_db: str) -> None:
    exists = query_psql("postgres", f"SELECT 1 FROM pg_database WHERE datname = '{target_db}'")
    if exists == "1":
        return

    parsed = urlparse(database_url.replace("postgresql+pg8000://", "postgresql://"))
    args = ["createdb", "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432)]
    if parsed.username:
        args.extend(["-U", parsed.username])
    args.append(target_db)

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    subprocess.run(args, check=True, cwd=PROJECT_DIR, env=env)


def run_psql_file(database: str, file_path: Path) -> None:
    args, env, _ = _psql_base_args(DATABASE_URL, database)
    subprocess.run(args + ["-f", str(file_path)], check=True, cwd=PROJECT_DIR, env=env)


def main() -> None:
    _, _, target_db = _psql_base_args(DATABASE_URL)
    create_database_if_missing(DATABASE_URL, target_db)
    run_psql_file(target_db, MIGRATION_FILE)

    from scripts.seed_initial import seed
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

    print(f"Banco '{target_db}' pronto com migration e seed inicial.")


if __name__ == "__main__":
    main()
