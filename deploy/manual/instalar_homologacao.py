"""Install and run the approved PIGO against the verified database copy only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


MANIFEST_SHA = "d796b327dcd0a2d96cc1d5cac5eb70864965f87650bcc2427c58d6af6661525d"
BACKUP_HELPER_SHA = "b6dfcb2b2dd0d012fcea5fb3a8fb1867141dba81dc6efd4795faf147c230e126"
MIGRATIONS = ["012_sales_goals.sql", "013_erp_commands.sql", "014_pigo_access.sql"]
REQUIRED_TABLES = {"sales_goals", "erp_commands", "erp_agent_capabilities", "pigo_access_profiles", "pigo_access_users"}
APP_ENTRY = '''"""Homologation entry point: no agent integration or ERP commands."""
import os
import re
from sqlalchemy.engine import make_url
from starlette.responses import JSONResponse

url = make_url(os.environ["DATABASE_URL"])
if (url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not re.fullmatch(r"pigo_homolog_[0-9]{8}_[0-9a-f]{12}", url.database or "")
        or url.database != os.environ.get("PIGO_HOMOLOG_DATABASE")
        or os.environ.get("PIGO_ENVIRONMENT") != "homologacao"):
    raise RuntimeError("Homologation database configuration required")
os.environ["ENABLE_LEGACY_FIREBIRD"] = "false"
from app.main import app as application

async def app(scope, receive, send):
    if scope["type"] == "http":
        path = scope.get("path", "").rstrip("/")
        integration = any(path == prefix or path.startswith(prefix + "/")
                          for prefix in ("/api/sync", "/api/agent", "/api/internal"))
        writeback = (path == "/api/erp" or path.startswith("/api/erp/")) and scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if integration or writeback or path == "/api/erp/teste":
            response = JSONResponse({"detail": "Integracao com agente e gravacao no ERP desabilitadas na homologacao."}, status_code=403)
            return await response(scope, receive, send)
    return await application(scope, receive, send)
'''


class InstallError(Exception):
    pass


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def backup_helpers(root):
    path = root / "preparar_homologacao.py"
    if not path.is_file() or sha(path) != BACKUP_HELPER_SHA:
        raise InstallError("Helper de backup anterior ausente ou diferente da versao conferida.")
    spec = importlib.util.spec_from_file_location("pigo_verified_backup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_package(root):
    manifest = root / "manifesto.json"
    if not manifest.is_file() or sha(manifest) != MANIFEST_SHA:
        raise InstallError("Manifesto diferente da entrega conciliada. Nenhuma instalacao iniciada.")
    for relative, expected in json.loads(manifest.read_text(encoding="utf-8"))["files"].items():
        file = root / relative
        if not file.is_file() or sha(file) != expected:
            raise InstallError("Arquivo da entrega ausente ou alterado: " + relative)


def check_port(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise InstallError(f"Porta {port} ocupada; nenhum processo sera encerrado.") from None


def clone_url(source_url, destination, expected_source):
    from sqlalchemy.engine import make_url
    url = make_url(source_url)
    if (url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost", "::1"}
            or url.database != expected_source):
        raise InstallError("Banco de origem diverge do ambiente conferido.")
    if not re.fullmatch(r"pigo_homolog_[0-9]{8}_[0-9a-f]{12}", destination or "") or destination == url.database:
        raise InstallError("Destino deve ser exclusivamente o banco de homologacao criado pelo backup.")
    return url.set(database=destination)


def environment_from(settings, destination):
    environment = dict(os.environ)
    environment.update(settings)
    # Force these even if inherited from another PowerShell session.
    environment.update(PIGO_ENVIRONMENT="homologacao", PIGO_HOMOLOG_DATABASE=destination,
                       ENABLE_LEGACY_FIREBIRD="false", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    return environment


def python_path(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_dependencies(root, python, log):
    venv = root / "backend/.venv-homologacao"
    interpreter = python_path(venv)
    print("Preparando ambiente Python separado...", flush=True)
    with log.open("ab") as output:
        if not interpreter.is_file():
            process = subprocess.run([str(python), "-m", "venv", str(venv)], stdout=output, stderr=subprocess.STDOUT)
            if process.returncode:
                raise InstallError("Falha ao criar ambiente Python; consulte o log privado de instalacao.")
        process = subprocess.run([str(interpreter), "-m", "pip", "--disable-pip-version-check", "--no-input",
                                  "install", "--requirement", str(root / "backend/requirements.txt")],
                                 stdout=output, stderr=subprocess.STDOUT)
        if process.returncode:
            raise InstallError("Instalacao de dependencias interrompida; consulte o log privado de instalacao.")
        process = subprocess.run([str(interpreter), "-m", "pip", "check"], stdout=output, stderr=subprocess.STDOUT)
        if process.returncode:
            raise InstallError("Dependencias com conflito; consulte o log privado de instalacao.")
    return interpreter


def inventory(connection, helper):
    return helper.database_inventory(connection)


def migrate_copy(root, url, backup, helper):
    from sqlalchemy import create_engine, text
    engine = create_engine(url, connect_args={"timeout": 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='10s'"))
            connection.execute(text("SET LOCAL statement_timeout='60s'"))
            if connection.execute(text("SELECT current_database()")).scalar_one() != backup["banco_homologacao"]:
                raise InstallError("A conexao nao aponta para o banco de homologacao.")
            before = inventory(connection, helper)
            expected = backup["verificacao"]
            if len(before["tables"]) < expected["tabelas_publicas"] or before["counts"] != expected["contagens_conferidas"]:
                raise InstallError("Dados da copia mudaram desde a restauracao. Nenhuma migracao aplicada.")
            print("Aplicando 012, 013 e 014 somente na copia...", flush=True)
            for name in MIGRATIONS:
                sql = (root / "backend/migrations" / name).read_text(encoding="utf-8")
                for statement in sql.split(";"):
                    if statement.strip():
                        connection.execute(text(statement))
            after = inventory(connection, helper)
            if before["counts"] != after["counts"] or not REQUIRED_TABLES.issubset(after["tables"]):
                raise InstallError("Verificacao das migracoes falhou; transacao revertida.")
        return {"migracoes": MIGRATIONS, "tabelas_novas_conferidas": sorted(REQUIRED_TABLES),
                "contagens_preservadas": after["counts"]}
    finally:
        engine.dispose()


def server_arguments(python, port):
    return [str(python), "-m", "uvicorn", "homologacao_entry:app", "--host", "127.0.0.1",
            "--port", str(port), "--workers", "1", "--no-use-colors"]


def smoke(root, python, environment, log, port=4023):
    check_port(port)
    opener = build_opener(ProxyHandler({}))
    with log.open("ab") as output:
        process = subprocess.Popen(server_arguments(python, port), cwd=root / "backend", env=environment,
                                   stdout=output, stderr=subprocess.STDOUT)
        try:
            end = time.monotonic() + 45
            while True:
                if process.poll() is not None:
                    raise InstallError("A API nao iniciou. Consulte o log privado de inicializacao.")
                try:
                    with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                        health = json.loads(response.read())
                        if health.get("service") != "pigo":
                            raise InstallError("Resposta inesperada da API de teste.")
                        break
                except (URLError, TimeoutError, ConnectionError):
                    if time.monotonic() > end:
                        raise InstallError("A API nao respondeu dentro do prazo.") from None
                    time.sleep(0.3)
            checks = {}
            for route in ["/login", "/dashboard/vendas", "/dashboard/financeiro", "/dashboard/estoque",
                          "/funcionarios", "/performance", "/acesso/usuarios", "/cadastros/produtos"]:
                request = Request(f"http://127.0.0.1:{port}" + route, headers={"Accept": "text/html"})
                with opener.open(request, timeout=8) as response:
                    if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                        raise InstallError("Painel compilado nao respondeu corretamente: " + route)
                    response.read()
                    checks[route] = 200
            for route, status in [("/api/me/tenant", 401), ("/api/sync/health", 403), ("/api/agent/activate", 403)]:
                try:
                    opener.open(f"http://127.0.0.1:{port}" + route, timeout=8).close()
                    raise InstallError("Protecao esperada nao aplicada: " + route)
                except HTTPError as error:
                    if error.code != status:
                        raise InstallError("Status de protecao inesperado: " + route) from None
                    error.close()
                    checks[route] = status
            return checks
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)


def prepare(current_root, new_root, backup_result, report, python=None, expected_source="pigo-dashboard", port=4023):
    if current_root.resolve() == new_root.resolve():
        raise InstallError("A instalacao nova deve ficar separada do PIGO atual.")
    verify_package(new_root)
    helper = backup_helpers(new_root)
    state_file = new_root / "homologacao.json"
    if state_file.exists():
        raise InstallError("Homologacao ja preparada. Use --action start; configuracao existente preservada.")
    backup = json.loads(backup_result.read_text(encoding="utf-8"))
    if backup.get("status") != "BACKUP_E_RESTAURACAO_CONFERIDOS" or backup.get("banco_origem") != expected_source:
        raise InstallError("Resultado de backup conferido obrigatorio.")
    original_backup = Path(backup["backup"]["arquivo"])
    print("Conferindo a integridade do backup e da entrega...", flush=True)
    if not original_backup.is_file() or sha(original_backup) != backup["backup"]["sha256"]:
        raise InstallError("Backup ausente ou SHA256 diferente; nenhuma migracao iniciada.")
    settings_file = current_root / "backend/.env"
    current_hash = sha(settings_file)
    settings = helper.settings_from(settings_file)
    url = clone_url(settings.get("DATABASE_URL", ""), backup.get("banco_homologacao"), expected_source)
    check_port(port)
    directory = helper.private_directory(backup_result.resolve().parent / "instalacao")
    report["pasta_privada"] = str(directory)
    configuration = dict(settings)
    configuration.update(DATABASE_URL=url.render_as_string(hide_password=False),
                         JWT_SECRET_KEY=secrets.token_urlsafe(48),
                         LICENSE_CONTROL_INTEGRATION_TOKEN=secrets.token_urlsafe(48),
                         LICENSE_CONTROL_SYNC_KEY=secrets.token_urlsafe(48),
                         PIGO_ENVIRONMENT="homologacao", PIGO_HOMOLOG_DATABASE=url.database,
                         ENABLE_LEGACY_FIREBIRD="false")
    private_env = directory / "homologacao.env"
    private_env.write_text("\n".join(name + "=" + value for name, value in configuration.items()) + "\n", encoding="utf-8")
    interpreter = install_dependencies(new_root, python or Path(sys.executable), directory / "instalacao.log")
    report.update(migrate_copy(new_root, url, backup, helper))
    entry = new_root / "backend/homologacao_entry.py"
    if entry.exists() and entry.read_text(encoding="utf-8") != APP_ENTRY:
        raise InstallError("Arquivo de inicializacao existente e diferente; preservado para revisao.")
    entry.write_text(APP_ENTRY, encoding="utf-8")
    print("Conferindo a API e as telas na porta local de teste...", flush=True)
    checks = smoke(new_root, interpreter, environment_from(configuration, url.database), directory / "api-teste.log", port)
    if sha(settings_file) != current_hash:
        raise InstallError("O .env de producao mudou durante a operacao; revise antes de continuar.")
    report.update(status="HOMOLOGACAO_INSTALADA_E_CONFERIDA", banco_homologacao=url.database,
                  porta=port, verificacoes_http=checks, env_producao_inalterado=True,
                  observacao="Migracoes aplicadas somente na copia. Integracao/ERP bloqueados. Caddy, tarefa e banco de producao preservados. Login e consultas autenticadas aguardam teste manual.")
    state = {"status": report["status"], "banco": url.database, "porta": port, "python": str(interpreter),
             "configuracao": str(private_env), "configuracao_sha256": sha(private_env), "entry_sha256": sha(entry),
             "backup_result": str(backup_result.resolve()), "pasta_privada": str(directory)}
    with state_file.open("x", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
    return 0


def start(root):
    verify_package(root)
    helper = backup_helpers(root)
    state = json.loads((root / "homologacao.json").read_text(encoding="utf-8"))
    config = Path(state["configuracao"])
    if (state.get("status") != "HOMOLOGACAO_INSTALADA_E_CONFERIDA"
            or sha(config) != state["configuracao_sha256"]
            or sha(root / "backend/homologacao_entry.py") != state["entry_sha256"]):
        raise InstallError("Configuracao de homologacao divergiu; inicializacao interrompida.")
    settings = helper.settings_from(config)
    from sqlalchemy.engine import make_url
    url = make_url(settings["DATABASE_URL"])
    if url.database != state["banco"] or not re.fullmatch(r"pigo_homolog_[0-9]{8}_[0-9a-f]{12}", url.database or ""):
        raise InstallError("Banco de homologacao invalido.")
    check_port(state["porta"])
    print("Iniciando somente em 127.0.0.1:" + str(state["porta"]) + ". Mantenha este terminal aberto.", flush=True)
    return subprocess.run(server_arguments(Path(state["python"]), state["porta"]), cwd=root / "backend",
                          env=environment_from(settings, state["banco"])).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["prepare", "start"], default="prepare")
    parser.add_argument("--current-root", type=Path)
    parser.add_argument("--backup-result", type=Path)
    parser.add_argument("--start", action="store_true", help="Start foreground after successful installation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    report = {"computador": os.environ.get("COMPUTERNAME", "nao informado"), "status": "NAO_CONCLUIDO"}
    try:
        if os.name != "nt" or report["computador"].upper() != "WIN-JG1E0O7FSBS":
            raise InstallError("Execute somente na VM Windows WIN-JG1E0O7FSBS.")
        if args.action == "start":
            return start(root)
        if args.current_root is None or args.backup_result is None:
            raise InstallError("Informe --current-root e --backup-result.")
        result = prepare(args.current_root, root, args.backup_result, report)
    except Exception as error:
        report.update(status="NAO_CONCLUIDO", tipo_erro=type(error).__name__,
                      motivo=str(error) if isinstance(error, InstallError) else "Operacao interrompida. Consulte os logs privados; credenciais nao serao exibidas.")
        result = 1
    if report.get("pasta_privada"):
        (Path(report["pasta_privada"]) / "instalacao-resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if result == 0 and args.start:
        try:
            return start(root)
        except (Exception, KeyboardInterrupt) as error:
            print(json.dumps({"status": "INICIALIZACAO_INTERROMPIDA", "tipo_erro": type(error).__name__}), flush=True)
            return 1
    return result


if __name__ == "__main__":
    sys.exit(main())
