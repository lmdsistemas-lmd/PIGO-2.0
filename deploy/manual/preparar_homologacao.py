"""Back up the current PIGO and restore a new, isolated database. No app startup."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


class PreparationError(Exception):
    """A safe diagnostic that never includes connection strings or SQL data."""


def settings_from(path):
    settings = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip().strip('"').strip("'")
    return settings


def private_directory(parent):
    directory = parent / ("homologacao_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    if os.name == "nt":
        # Restrict the empty directory before placing any customer data in it.
        result = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"],
                                capture_output=True, text=True, check=True)
        row = next(csv.reader(result.stdout.strip().splitlines()))
        sid = row[-1].strip()
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise PreparationError("Nao foi possivel identificar a conta Windows; nenhum backup iniciado.")
        acl = subprocess.run(["icacls.exe", str(directory), "/inheritance:r", "/grant:r",
                              f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
                             capture_output=True, text=True)
        if acl.returncode:
            raise PreparationError("Nao foi possivel restringir a pasta privada; nenhum backup iniciado.")
    else:
        directory.chmod(0o700)
    return directory


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value):
    return "'" + value.replace("'", "''") + "'"


def database_metadata(connection):
    from sqlalchemy import text
    row = connection.execute(text("""
        SELECT current_database() AS name,
               current_setting('server_version_num')::integer AS version_number,
               current_setting('server_version') AS version,
               pg_encoding_to_char(d.encoding) AS encoding,
               d.datcollate AS collate, d.datctype AS ctype,
               d.datlocprovider AS provider,
               COALESCE(to_jsonb(d)->>'datlocale', to_jsonb(d)->>'daticulocale') AS locale
        FROM pg_database d WHERE d.datname = current_database()
    """)).mappings().one()
    return dict(row)


def database_inventory(connection):
    from sqlalchemy import text
    tables = list(connection.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name
    """)).scalars())
    # Exact counts are taken from the very snapshot used by pg_dump.
    selected = {"agent_installations", "municipality_geocodes", "TB_EMPRESA", "TB_USUARIO",
                "TB_FECHAMENTO_CAIXA", "TB_FECHAMENTO_CAIXA_ITEM"}
    counts = {}
    for table in tables:
        if table in selected:
            counts[table] = connection.execute(text("SELECT count(*) FROM public." + quote_identifier(table))).scalar_one()
    return {"tables": tables, "counts": counts}


def create_database_sql(name, metadata):
    if not re.fullmatch(r"pigo_homolog_[0-9]{8}_[0-9a-f]{12}", name):
        raise PreparationError("Nome de destino fora do padrao de homologacao.")
    providers = {"c": "libc", "i": "icu", "b": "builtin"}
    provider = providers.get(metadata["provider"])
    if not provider:
        raise PreparationError("Provedor de locale nao reconhecido; backup preservado, sem criar banco.")
    options = ["TEMPLATE template0", "ENCODING " + quote_literal(metadata["encoding"]),
               "LOCALE_PROVIDER " + provider,
               "LC_COLLATE " + quote_literal(metadata["collate"]),
               "LC_CTYPE " + quote_literal(metadata["ctype"])]
    if provider in {"icu", "builtin"}:
        if not metadata["locale"]:
            raise PreparationError("Locale de origem indisponivel; backup preservado, sem criar banco.")
        options.append(("ICU_LOCALE " if provider == "icu" else "BUILTIN_LOCALE ") + quote_literal(metadata["locale"]))
    return "CREATE DATABASE " + quote_identifier(name) + " WITH " + " ".join(options)


def run_tool(arguments, environment, log, stdout_file=None):
    with log.open("wb") as errors:
        result = subprocess.run(arguments, env=environment, stdout=stdout_file or subprocess.DEVNULL,
                                stderr=errors, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise PreparationError(f"{Path(arguments[0]).stem} falhou (codigo {result.returncode}). Diagnostico privado: {log.name}")


def prepare(current_root, pg_bin, backup_root, report, expected_database="pigo-dashboard"):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    environment_file = current_root / "backend" / ".env"
    settings = settings_from(environment_file)
    # Exactly the file inspected in the previous step, not an inherited DATABASE_URL.
    value = settings.get("DATABASE_URL")
    if not value:
        raise PreparationError("DATABASE_URL ausente no .env atual; nenhuma operacao realizada.")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise PreparationError("Esperado PostgreSQL local; nenhuma operacao realizada.")
    if url.database != expected_database or not url.username:
        raise PreparationError("Nome do banco ou usuario diverge do ambiente conferido; nenhuma operacao realizada.")
    source_hash = digest(environment_file)
    executable = ".exe" if os.name == "nt" else ""
    pg_dump, pg_restore = [pg_bin / (name + executable) for name in ["pg_dump", "pg_restore"]]
    for tool in [pg_dump, pg_restore]:
        if not tool.is_file():
            raise PreparationError("Ferramenta PostgreSQL nao encontrada: " + tool.name)
    environment = {key: val for key, val in os.environ.items() if not key.upper().startswith("PG")}
    environment.update(PGCONNECT_TIMEOUT="10", PGAPPNAME="pigo-backup-homologacao")
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
    connection_args = ["--host", url.host, "--port", str(url.port or 5432), "--username", url.username, "--no-password"]
    source = create_engine(url, connect_args={"timeout": 10})
    admin = clone = None
    directory = None
    try:
        with source.connect() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            metadata = database_metadata(connection)
            if metadata["name"] != expected_database:
                raise PreparationError("Conexao nao corresponde ao banco conferido.")
            major = metadata["version_number"] // 10000
            for tool in [pg_dump, pg_restore]:
                version = subprocess.run([str(tool), "--version"], capture_output=True, text=True,
                                         env=environment, timeout=10, check=True)
                match = re.search(r"\(PostgreSQL\)\s+(\d+)", version.stdout)
                if not match or int(match[1]) != major:
                    raise PreparationError("Use pg_dump e pg_restore da mesma versao principal do servidor.")
            report.update(banco_origem=expected_database, versao_servidor=metadata["version"])
            directory = private_directory(backup_root)
            report["pasta_privada"] = str(directory)
            snapshot = connection.execute(text("SELECT pg_export_snapshot()")).scalar_one()
            inventory = database_inventory(connection)
            partial = directory / "pigo-producao.dump.partial"
            backup = directory / "pigo-producao.dump"
            print("Criando backup consistente do banco atual...", flush=True)
            run_tool([str(pg_dump), *connection_args, "--dbname", url.database, "--format=custom",
                      "--snapshot", snapshot, "--file", str(partial)], environment, directory / "pg_dump-erros.log")
            if not partial.is_file() or partial.stat().st_size < 5:
                raise PreparationError("Backup nao foi gerado corretamente.")
            with partial.open("rb") as stream:
                if stream.read(5) != b"PGDMP":
                    raise PreparationError("Formato do backup inesperado.")
            partial.rename(backup)
            report["backup"] = {"arquivo": str(backup), "bytes": backup.stat().st_size,
                                "sha256": digest(backup), "formato": "PostgreSQL custom"}
            with (directory / "backup-conteudo.txt").open("wb") as listing:
                run_tool([str(pg_restore), "--list", str(backup)], environment, directory / "pg_restore-lista-erros.log", listing)
            connection.rollback()
        # Backup is complete before any new database can be created.
        admin = create_engine(url.set(database="postgres"), connect_args={"timeout": 10}, isolation_level="AUTOCOMMIT")
        destination = "pigo_homolog_" + datetime.now(timezone.utc).strftime("%Y%m%d_") + uuid.uuid4().hex[:12]
        if destination == url.database:
            raise PreparationError("Destino nao pode ser o banco atual.")
        with admin.connect() as connection:
            permitted = connection.execute(text("SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user")).scalar_one()
            if not permitted:
                raise PreparationError("Backup concluido, mas a conta atual nao pode criar bancos. Necessaria criacao por um administrador PostgreSQL.")
            if connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": destination}).first():
                raise PreparationError("Banco de destino ja existe; nenhum banco foi substituido.")
            print("Criando banco separado para homologacao...", flush=True)
            connection.exec_driver_sql(create_database_sql(destination, metadata))
        report["banco_homologacao"] = destination
        report["banco_homologacao_criado"] = True
        print("Restaurando o backup na copia...", flush=True)
        run_tool([str(pg_restore), *connection_args, "--dbname", destination, "--no-owner", "--no-privileges",
                  "--exit-on-error", "--single-transaction", str(backup)], environment, directory / "pg_restore-erros.log")
        clone = create_engine(url.set(database=destination), connect_args={"timeout": 10})
        with clone.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            restored_metadata = database_metadata(connection)
            restored = database_inventory(connection)
            for key in ["encoding", "collate", "ctype", "provider", "locale"]:
                if metadata[key] != restored_metadata[key]:
                    raise PreparationError("Locale da copia diverge da origem: " + key)
            if restored != inventory:
                raise PreparationError("Conferencia da restauracao divergiu. Backup preservado; copia nao liberada para uso.")
            connection.rollback()
        if digest(environment_file) != source_hash:
            raise PreparationError("O .env atual mudou durante a operacao; revise a configuracao antes de continuar.")
        report.update(status="BACKUP_E_RESTAURACAO_CONFERIDOS",
                      verificacao={"tabelas_publicas": len(inventory["tables"]),
                                   "contagens_conferidas": inventory["counts"], "locale_igual": True,
                                   "env_atual_inalterado": True},
                      observacao="Backup e copia separados. Sem migracoes, inicializacao, envio ao ERP ou alteracao no Caddy. A copia nao recebe novas sincronizacoes.")
        return 0
    finally:
        source.dispose()
        if admin is not None:
            admin.dispose()
        if clone is not None:
            clone.dispose()
        if directory is not None:
            (directory / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, default=Path(r"C:\Program Files\PostgreSQL\18\bin"))
    args = parser.parse_args()
    report = {"computador": os.environ.get("COMPUTERNAME", "nao informado"), "status": "NAO_CONCLUIDO"}
    try:
        if os.name != "nt" or report["computador"].upper() != "WIN-JG1E0O7FSBS":
            raise PreparationError("Execute somente na VM Windows WIN-JG1E0O7FSBS.")
        if not (args.current_root / "backend/app/main.py").is_file():
            raise PreparationError("Backend atual nao encontrado nessa pasta.")
        backup_root = Path(os.environ["PROGRAMDATA"]) / "PIGO Backups"
        code = prepare(args.current_root, args.pg_bin, backup_root, report)
    except Exception as error:
        report.update(status="NAO_CONCLUIDO", tipo_erro=type(error).__name__,
                      motivo=str(error) if isinstance(error, PreparationError) else "Operacao interrompida. Nenhuma mensagem de conexao ou credencial sera exibida.")
        code = 1
    if report.get("pasta_privada"):
        (Path(report["pasta_privada"]) / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
