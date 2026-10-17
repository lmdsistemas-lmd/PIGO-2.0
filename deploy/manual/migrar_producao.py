"""PIGO production migration: fresh backup, additive SQL, Windows task, scoped Caddy reload."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

DOMAIN = "pigo.lmdsistemasdev.qzz.io"
DATABASE = "pigo-dashboard"
PORT = 4024
TASK = "PigoDashboardProduction"
CADDY_TASK = "LmdSharedCaddy"
SETUP_SHA = "8ec982b0faa8c414628460085d3518bce540d7ed853e47bf21968ce3cca8cbca"
MIGRATIONS = ["012_sales_goals.sql", "013_erp_commands.sql", "014_pigo_access.sql"]
ALLOWED_DIALS = {host + ":" + str(port) for host in ["127.0.0.1", "localhost"] for port in [4000, 4010, 5176]}
OPENER = build_opener(ProxyHandler({}))


class MigrationError(Exception):
    pass


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def helpers(root):
    file = root / "instalar_homologacao.py"
    if not file.is_file() or sha_file(file) != SETUP_SHA:
        raise MigrationError("Aplique primeiro o ajuste de interface aprovado na pasta de homologacao.")
    spec = importlib.util.spec_from_file_location("pigo_install_verified", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_package(root)
    return module, module.backup_helpers(root)


def api_config(api_url):
    with OPENER.open(api_url.rstrip("/") + "/config/", timeout=8) as response:
        value = response.read(8 * 1024 * 1024 + 1)
    if len(value) > 8 * 1024 * 1024:
        raise MigrationError("Configuracao Caddy maior que o limite de revisao.")
    return json.loads(value)


def pigo_route(config):
    matches = []
    def walk(node, allowed=True):
        if isinstance(node, list):
            for item in node:
                walk(item, allowed)
        elif isinstance(node, dict):
            groups = node.get("match", [])
            host_groups = [g.get("host") for g in groups if isinstance(g, dict) and g.get("host")]
            has_target = any(DOMAIN in [str(h).lower() for h in group] for group in host_groups)
            compatible = allowed and (not host_groups or has_target)
            if allowed and has_target:
                if any(not isinstance(g, dict) or [str(h).lower() for h in g.get("host", [])] != [DOMAIN] for g in groups):
                    raise MigrationError("PIGO compartilha grupo de hosts ou regra alternativa; revisao necessaria.")
                matches.append(node)
            for key, value in node.items():
                if key != "match":
                    walk(value, compatible)
    walk(config)
    if len(matches) != 1:
        raise MigrationError("Esperado exatamente um grupo dedicado ao dominio PIGO.")
    return matches[0]


def changed_config(config, destination):
    result = copy.deepcopy(config)
    route = pigo_route(result)
    count = 0
    def change(node):
        nonlocal count
        if isinstance(node, list):
            for item in node:
                change(item)
        elif isinstance(node, dict):
            if node.get("handler") == "reverse_proxy":
                upstreams = node.get("upstreams", [])
                if len(upstreams) != 1 or upstreams[0].get("dial") not in ALLOWED_DIALS:
                    raise MigrationError("Destino atual do PIGO fora do conjunto conhecido; nenhuma troca aplicada.")
                upstreams[0]["dial"] = destination
                count += 1
            for value in node.values():
                change(value)
    change(route)
    if count == 0:
        raise MigrationError("Proxy do PIGO nao encontrado.")
    return result, count


def caddy_tokens(value):
    """Only standalone unquoted braces delimit Caddyfile blocks; placeholders do not."""
    index = 0
    while index < len(value):
        if value[index].isspace():
            index += 1
            continue
        if value[index] == "#":
            index = value.find("\n", index)
            if index < 0:
                return
            continue
        start = index
        quote = value[index] if value[index] in {'"', '`'} else None
        if quote:
            index += 1
            while index < len(value):
                if value[index] == quote:
                    index += 1
                    break
                if quote == '"' and value[index] == "\\":
                    index += 1
                index += 1
        else:
            while index < len(value) and not value[index].isspace():
                index += 1
        yield value[start:index], start, index, quote


def candidate_text(original, destination):
    text = original.decode("utf-8-sig")
    header = list(re.finditer(r"(?im)^[ \t]*(?:https?://)?" + re.escape(DOMAIN) + r"(?::[0-9]+)?[ \t]+\{(?=\s|$)", text))
    if len(header) != 1:
        raise MigrationError("Bloco PIGO explicito nao identificado no Caddyfile; arquivo preservado.")
    opening = header[0].end() - 1
    depth = 0
    closing = None
    tokens = list(caddy_tokens(text))
    for token, start, end, quote in tokens:
        if start < opening or quote:
            continue
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth == 0:
                closing = end
                break
    if closing is None:
        raise MigrationError("Limites do bloco PIGO nao identificados; arquivo preservado.")
    edits = []
    for token, start, end, quote in tokens:
        if not opening < start < closing:
            continue
        bare = token[1:-1] if quote else token
        scheme = "http://" if bare.startswith("http://") else ""
        if bare.removeprefix("http://") in ALLOWED_DIALS:
            replacement = scheme + destination
            edits.append((start, end, quote + replacement + quote if quote else replacement))
    if not edits:
        raise MigrationError("Enderecos de proxy conhecidos ausentes no bloco PIGO.")
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    encoded = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + encoded) if original.startswith(b"\xef\xbb\xbf") else encoded


def run_private(arguments, log, **kwargs):
    with log.open("ab") as output:
        result = subprocess.run(arguments, stdout=output, stderr=subprocess.STDOUT, **kwargs)
    if result.returncode:
        raise MigrationError("Comando interrompido; consulte o diagnostico privado: " + log.name)


def adapt(caddy, path):
    result = subprocess.run([str(caddy), "adapt", "--config", str(path), "--adapter", "caddyfile"],
                            cwd=path.parent, capture_output=True)
    if result.returncode:
        raise MigrationError("Caddyfile nao passou na adaptacao; nenhuma rota alterada.")
    return json.loads(result.stdout)


def preserve_acl(source, target, directory):
    if os.name == "nt":
        acl = directory / "preservar-acl.ps1"
        acl.write_text("param([string]$PigoSource,[string]$PigoTarget)\n$ErrorActionPreference='Stop'\nGet-Acl -LiteralPath $PigoSource | Set-Acl -LiteralPath $PigoTarget\n", encoding="utf-8")
        run_private(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(acl), str(source), str(target)], directory / "caddy-acl.log")
    else:
        target.chmod(source.stat().st_mode & 0o777)


def replace_from(source, destination, directory):
    descriptor, name = tempfile.mkstemp(prefix=".pigo-replace-", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    file = Path(name)
    try:
        file.write_bytes(source.read_bytes())
        preserve_acl(destination, file, directory)
        os.replace(file, destination)
    finally:
        if file.exists():
            file.unlink()


def stage_caddy(caddy, config_file, directory, api_url, destination):
    original = config_file.read_bytes()
    live = api_config(api_url)
    if canonical(adapt(caddy, config_file)) != canonical(live):
        raise MigrationError("Caddy em execucao diverge do Caddyfile.production; revisar antes de migrar.")
    expected, proxies = changed_config(live, destination)
    proposed = candidate_text(original, destination)
    descriptor, name = tempfile.mkstemp(prefix=".pigo-candidate-", suffix=".caddyfile", dir=config_file.parent)
    os.close(descriptor)
    candidate = Path(name)
    candidate.write_bytes(proposed)
    preserve_acl(config_file, candidate, directory)
    if canonical(adapt(caddy, candidate)) != canonical(expected):
        raise MigrationError("O candidato altera mais que os destinos do PIGO; nenhuma troca aplicada.")
    run_private([str(caddy), "validate", "--config", str(candidate), "--adapter", "caddyfile"], directory / "caddy-validate.log", cwd=config_file.parent)
    (directory / "Caddyfile.original").write_bytes(original)
    save(directory / "caddy-active-original.json", live)
    return {"file": str(config_file), "candidate": str(candidate), "original_sha": sha_bytes(original),
            "candidate_sha": sha_bytes(proposed), "active_original_sha": sha_bytes(canonical(live)),
            "active_candidate_sha": sha_bytes(canonical(expected)), "api_url": api_url,
            "caddy": str(caddy), "proxy_handlers_changed": proxies}


def backup_database(url, pg_bin, directory, helper):
    from sqlalchemy import create_engine, text
    suffix = ".exe" if os.name == "nt" else ""
    dump, restore = [pg_bin / (name + suffix) for name in ["pg_dump", "pg_restore"]]
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}
    environment.update(PGCONNECT_TIMEOUT="10", PGAPPNAME="pigo-production-migration")
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
    engine = create_engine(url, connect_args={"timeout": 10})
    try:
        with engine.connect() as db:
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            metadata = helper.database_metadata(db)
            if metadata["name"] != url.database:
                raise MigrationError("Conexao do backup divergiu.")
            for binary in [dump, restore]:
                version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, env=environment, check=True)
                match = re.search(r"\(PostgreSQL\)\s+(\d+)", version.stdout)
                if not match or int(match[1]) != metadata["version_number"] // 10000:
                    raise MigrationError("Ferramentas PostgreSQL devem ter a mesma versao principal do servidor.")
            snapshot = db.execute(text("SELECT pg_export_snapshot()")).scalar_one()
            counts = helper.database_inventory(db)["counts"]
            file = directory / "pigo-producao.dump.partial"
            arguments = [str(dump), "--host", url.host, "--port", str(url.port or 5432), "--username", url.username,
                         "--no-password", "--dbname", url.database, "--format=custom", "--snapshot", snapshot, "--file", str(file)]
            helper.run_tool(arguments, environment, directory / "backup-erros.log")
            with file.open("rb") as stream:
                if stream.read(5) != b"PGDMP":
                    raise MigrationError("Backup custom invalido; migracao cancelada.")
            target = directory / "pigo-producao.dump"
            file.rename(target)
            with (directory / "backup-conteudo.txt").open("wb") as listing:
                helper.run_tool([str(restore), "--list", str(target)], environment, directory / "backup-lista-erros.log", listing)
            return {"arquivo": str(target), "bytes": target.stat().st_size, "sha256": sha_file(target), "contagens_no_snapshot": counts}
    finally:
        engine.dispose()


def migrate_database(root, url, helper):
    from sqlalchemy import create_engine, text
    engine = create_engine(url, connect_args={"timeout": 10})
    try:
        with engine.begin() as db:
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            db.execute(text("SET LOCAL lock_timeout='10s'"))
            db.execute(text("SET LOCAL statement_timeout='60s'"))
            if db.execute(text("SELECT current_database()")).scalar_one() != url.database:
                raise MigrationError("Banco de destino divergiu.")
            before = helper.database_inventory(db)["counts"]
            for name in MIGRATIONS:
                for statement in (root / "backend/migrations" / name).read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        db.execute(text(statement))
            after = helper.database_inventory(db)
            if before != after["counts"] or not {"sales_goals", "erp_commands", "erp_agent_capabilities", "pigo_access_profiles", "pigo_access_users"}.issubset(after["tables"]):
                raise MigrationError("Conferencia de migracoes falhou; transacao revertida.")
        return {"migracoes": MIGRATIONS, "contagens_preservadas_na_transacao": before}
    finally:
        engine.dispose()


RUNNER = '''import json,os,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'producao.json').read_text(encoding='utf-8'))
config=Path(state['configuracao'])
if hashlib.sha256(config.read_bytes()).hexdigest()!=state['configuracao_sha256']:
    raise RuntimeError('Production configuration hash mismatch')
for raw in config.read_text(encoding='utf-8').splitlines():
    line=raw.strip()
    if line and not line.startswith('#') and '=' in line:
        name,value=line.split('=',1);os.environ[name.strip()]=value.strip().strip('"').strip("'")
from sqlalchemy.engine import make_url
url=make_url(os.environ['DATABASE_URL'])
if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost','::1'} or url.database!=state['banco'] or url.database.startswith('pigo_homolog_'):
    raise RuntimeError('Production database required')
os.environ['ENABLE_LEGACY_FIREBIRD']='false'
log=Path(state['pasta_privada'])/'pigo-api.log'
output=log.open('a',encoding='utf-8',buffering=1);sys.stdout=output;sys.stderr=output
from app.main import app as original
from starlette.responses import JSONResponse
async def app(scope,receive,send):
    if scope['type']=='http':
        path=scope.get('path','').rstrip('/')
        erp=(path=='/api/erp/cadastros' or path.startswith('/api/erp/cadastros/')) and scope['method'] not in {'GET','HEAD','OPTIONS'}
        agent_commands=path.startswith('/api/sync/commands/')
        if erp or agent_commands:
            return await JSONResponse({'detail':'Gravacao no ERP aguarda homologacao dos procedimentos do agente.'},status_code=503)(scope,receive,send)
    async def identified(message):
        if message['type']=='http.response.start':
            message=dict(message);message['headers']=list(message.get('headers',[]))+[(b'x-pigo-deployment',state['deployment_id'].encode('ascii'))]
        await send(message)
    return await original(scope,receive,identified)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=state['porta'],workers=1,log_level='info',use_colors=False)
'''

TASK_SCRIPT = '''param([string]$PigoPython,[string]$PigoRunner,[string]$PigoWorkingDirectory)
$ErrorActionPreference='Stop'
$pigoIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($pigoIdentity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Abra o PowerShell como Administrador.' }
if (Get-ScheduledTask -TaskPath '\\' -TaskName 'PigoDashboardProduction' -ErrorAction SilentlyContinue) { throw 'Tarefa de producao ja existe; nao sera substituida.' }
$pigoAction=New-ScheduledTaskAction -Execute $PigoPython -Argument ('-u "'+$PigoRunner+'"') -WorkingDirectory $PigoWorkingDirectory
$pigoPrincipal=New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
$pigoTrigger=New-ScheduledTaskTrigger -AtStartup
$pigoTrigger.Delay='PT30S'
$pigoSettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval ([TimeSpan]::FromMinutes(1)) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskPath '\\' -TaskName 'PigoDashboardProduction' -Action $pigoAction -Principal $pigoPrincipal -Trigger $pigoTrigger -Settings $pigoSettings -Description 'PIGO aprovado em producao, Python dedicado, porta local4024.' | Out-Null
Start-ScheduledTask -TaskPath '\\' -TaskName 'PigoDashboardProduction'
'''


def health(port, deployment_id=None):
    checks = {}
    for route in ["/api/health", "/login", "/dashboard/vendas", "/dashboard/financeiro", "/dashboard/estoque", "/funcionarios", "/performance", "/acesso/usuarios"]:
        request = Request(f"http://127.0.0.1:{port}" + route, headers={"Accept": "text/html"} if route != "/api/health" else {})
        with OPENER.open(request, timeout=5) as response:
            body = response.read()
            if response.status != 200 or (route == "/api/health" and json.loads(body).get("service") != "pigo"):
                raise MigrationError("Verificacao da API falhou: " + route)
            if deployment_id and response.headers.get("X-Pigo-Deployment") != deployment_id:
                raise MigrationError("A porta responde por outra instancia; nenhum processo sera encerrado.")
            if route != "/api/health" and "text/html" not in response.headers.get("Content-Type", ""):
                raise MigrationError("Painel compilado indisponivel: " + route)
            checks[route] = 200
    return checks


def prepare(source, current, destination, pg_bin, caddy, config_file, api_url, report, expected_db=DATABASE, port=PORT, register=True, private_root=None):
    from sqlalchemy.engine import make_url
    setup, helper = helpers(source)
    if source.resolve() == destination.resolve() or current.resolve() == destination.resolve() or destination.exists():
        raise MigrationError("Pasta de producao deve ser nova e separada. Nenhuma pasta sera substituida.")
    setup.check_port(port)
    if register:
        check = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                "if (Get-ScheduledTask -TaskPath '\\' -TaskName 'PigoDashboardProduction' -ErrorAction SilentlyContinue) { exit 2 }"], capture_output=True)
        if check.returncode:
            raise MigrationError("Tarefa de producao ja existe ou nao pode ser consultada; nenhuma instalacao iniciada.")
    settings_file = current / "backend/.env"
    original_hash = sha_file(settings_file)
    settings = helper.settings_from(settings_file)
    url = make_url(settings.get("DATABASE_URL", ""))
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"} or url.database != expected_db or url.database.startswith("pigo_homolog_"):
        raise MigrationError("Esperado exclusivamente o banco local de producao conferido.")
    for name in ["JWT_SECRET_KEY", "LICENSE_CONTROL_INTEGRATION_TOKEN", "LICENSE_CONTROL_SYNC_KEY"]:
        if not settings.get(name):
            raise MigrationError("Configuracao obrigatoria ausente no .env atual: " + name)
    directory = helper.private_directory(private_root or Path(os.environ["PROGRAMDATA"]) / "PIGO Production")
    report["pasta_privada"] = str(directory)
    print("Conferindo e validando a troca exclusiva do dominio PIGO...", flush=True)
    plan = stage_caddy(caddy, config_file, directory, api_url, "127.0.0.1:" + str(port))
    print("Criando backup novo do banco de producao...", flush=True)
    report["backup"] = backup_database(url, pg_bin, directory, helper)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((source / "manifesto.json").read_text(encoding="utf-8"))
    for relative in manifest["files"]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    shutil.copy2(source / "manifesto.json", destination / "manifesto.json")
    shutil.copy2(Path(__file__), destination / "migrar_producao.py")
    private_env = directory / "production.env"
    configuration = dict(settings)
    configuration.update(PIGO_ENVIRONMENT="production", ENABLE_LEGACY_FIREBIRD="false")
    private_env.write_text("\n".join(key + "=" + value for key, value in configuration.items()) + "\n", encoding="utf-8")
    print("Criando Python exclusivo para a producao e instalando dependencias...", flush=True)
    venv = destination / "backend/.venv-producao"
    run_private([sys.executable, "-m", "venv", str(venv)], directory / "instalacao.log")
    python = setup.python_path(venv)
    run_private([str(python), "-m", "pip", "--disable-pip-version-check", "--no-input", "install", "--requirement", str(destination / "backend/requirements.txt")], directory / "instalacao.log")
    run_private([str(python), "-m", "pip", "check"], directory / "instalacao.log")
    if sha_file(settings_file) != original_hash:
        raise MigrationError("Configuracao atual mudou durante o preparo; nenhuma migracao aplicada.")
    print("Aplicando somente as migracoes012 a014 no banco atual...", flush=True)
    report.update(migrate_database(destination, url, helper))
    runner = destination / "backend/run_production.py"
    runner.write_text(RUNNER, encoding="utf-8")
    state = {"schema": 1, "phase": "prepared", "deployment_id": uuid.uuid4().hex, "root": str(destination.resolve()), "banco": url.database, "porta": port,
             "pasta_privada": str(directory), "configuracao": str(private_env), "configuracao_sha256": sha_file(private_env),
             "python": str(python), "source_env": str(settings_file), "source_env_sha256": original_hash,
             "manifest_sha256": sha_file(destination / "manifesto.json"), "runner_sha256": sha_file(runner), "caddy": plan, "backup": report["backup"]}
    save(destination / "producao.json", state)
    save(directory / "producao-state.json", state)
    (directory / "registrar-tarefa.ps1").write_text(TASK_SCRIPT, encoding="utf-8-sig")
    report.update(pasta_producao=str(destination), banco_producao=url.database, tarefa=TASK, porta=port)
    if register:
        run_private(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(directory / "registrar-tarefa.ps1"),
                     str(python), str(runner), str(destination / "backend")], directory / "tarefa.log")
        end = time.monotonic() + 50
        while True:
            try:
                report["verificacoes_http"] = health(port, state["deployment_id"])
                break
            except (OSError, URLError):
                if time.monotonic() >= end:
                    raise MigrationError("Tarefa registrada, mas API nao respondeu; Caddy permanece anterior. Consulte pigo-api.log.") from None
                time.sleep(0.5)
    report.update(status="PRODUCAO_PREPARADA", chaves_login_integracao_preservadas=True,
                  caddy_alterado=False, observacao="Banco atual preservado; tabelas adicionais criadas. API nova local, sem troca de dominio ate cutover. Gravacao no ERP aguarda homologacao.")
    return state


def load_state(root):
    state = json.loads((root / "producao.json").read_text(encoding="utf-8"))
    if state.get("root") != str(root.resolve()) or state.get("schema") != 1 or state.get("banco") != DATABASE:
        raise MigrationError("Estado nao corresponde a esta instalacao de producao.")
    for path, expected in [(Path(state["configuracao"]), state["configuracao_sha256"]), (root / "manifesto.json", state["manifest_sha256"]),
                           (root / "backend/run_production.py", state["runner_sha256"])]:
        if sha_file(path) != expected:
            raise MigrationError("Configuracao de producao foi alterada; operacao interrompida.")
    manifest = json.loads((root / "manifesto.json").read_text(encoding="utf-8"))
    for relative, digest in manifest["files"].items():
        if sha_file(root / relative) != digest:
            raise MigrationError("Arquivo de producao ausente ou alterado: " + relative)
    return state


def reload_caddy(plan, file, directory):
    run_private([plan["caddy"], "reload", "--config", str(file), "--adapter", "caddyfile", "--address", plan["api_url"].removeprefix("http://")],
                directory / "caddy-reload.log", cwd=file.parent)


def cutover(root, report):
    state = load_state(root)
    report["verificacoes_http"] = health(state["porta"], state["deployment_id"])
    plan = state["caddy"]
    directory = Path(state["pasta_privada"])
    source = Path(plan["file"])
    candidate = Path(plan["candidate"])
    if sha_file(Path(state["source_env"])) != state["source_env_sha256"]:
        raise MigrationError("O .env de producao original mudou; chaves devem ser revistas antes da troca.")
    if sha_file(source) != plan["original_sha"] or sha_bytes(canonical(api_config(plan["api_url"]))) != plan["active_original_sha"]:
        raise MigrationError("Configuracao Caddy mudou desde o preparo; nenhum dominio alterado.")
    if sha_file(candidate) != plan["candidate_sha"]:
        raise MigrationError("Candidato Caddy alterado; troca cancelada.")
    print("Trocando somente os destinos do dominio PIGO...", flush=True)
    replace_from(candidate, source, directory)
    try:
        reload_caddy(plan, source, directory)
        if sha_bytes(canonical(api_config(plan["api_url"]))) != plan["active_candidate_sha"]:
            raise MigrationError("Configuracao ativa apos reload divergiu.")
        # The new, unprotected health endpoint must be reachable through HTTPS.
        with OPENER.open("https://" + DOMAIN + "/api/health", timeout=15) as response:
            if response.status != 200 or json.load(response).get("service") != "pigo":
                raise MigrationError("Conferencia publica do PIGO falhou.")
            if response.headers.get("X-Pigo-Deployment") != state["deployment_id"]:
                raise MigrationError("O dominio publico respondeu por outra instancia.")
        request = Request("https://" + DOMAIN + "/login", headers={"Accept": "text/html"})
        with OPENER.open(request, timeout=15) as response:
            index = response.read()
            if response.status != 200 or sha_bytes(index) != sha_file(root / "frontend/dist/index.html"):
                raise MigrationError("O dominio publico nao entregou o painel compilado novo.")
        assets = set(re.findall(r'(?:src|href)="(/assets/[^"?#]+)"', index.decode("utf-8")))
        if not assets:
            raise MigrationError("Assets do painel compilado nao identificados.")
        for asset in assets:
            file = root / "frontend/dist" / asset.lstrip("/")
            with OPENER.open("https://" + DOMAIN + asset, timeout=15) as response:
                if response.status != 200 or sha_bytes(response.read()) != sha_file(file):
                    raise MigrationError("O dominio publico nao entregou os novos assets do painel.")
    except Exception:
        if sha_file(source) != plan["candidate_sha"]:
            raise MigrationError("Caddyfile recebeu outra alteracao; retorno automatico suspenso para preservar os demais dominios.") from None
        try:
            active = sha_bytes(canonical(api_config(plan["api_url"])))
        except Exception:
            replace_from(directory / "Caddyfile.original", source, directory)
            raise MigrationError("API Caddy indisponivel; arquivo original restaurado. Confira o processo Caddy antes de prosseguir.") from None
        if active not in {plan["active_original_sha"], plan["active_candidate_sha"]}:
            raise MigrationError("Caddy recebeu outra alteracao concorrente; retorno automatico suspenso para preservar os demais dominios.") from None
        replace_from(directory / "Caddyfile.original", source, directory)
        reload_caddy(plan, source, directory)
        raise MigrationError("Verificacao da troca falhou; Caddy retornou a configuracao anterior. Banco e API nova preservados.") from None
    state["phase"] = "live"
    save(root / "producao.json", state)
    save(directory / "producao-state.json", state)
    report.update(status="MIGRACAO_CONCLUIDA", dominio=DOMAIN, banco=state["banco"], porta=state["porta"], tarefa=TASK,
                  caddy_alterado=True, outros_dominios_preservados=True, pasta_privada=str(directory), backup=state["backup"],
                  observacao="PIGO novo no banco real, tarefa automatica com atraso30s. Caddy recarregado sem parar. Validar login e sincronizacao no dominio; reboot ainda nao testado. Caddy continua no processo atual.")


def rollback(root, report):
    state = load_state(root)
    plan = state["caddy"]
    directory = Path(state["pasta_privada"])
    source = Path(plan["file"])
    if sha_file(source) != plan["candidate_sha"] or sha_bytes(canonical(api_config(plan["api_url"]))) != plan["active_candidate_sha"]:
        raise MigrationError("Configuracao mudou depois da troca; retorno exige revisao para preservar outros dominios.")
    replace_from(directory / "Caddyfile.original", source, directory)
    reload_caddy(plan, source, directory)
    if sha_bytes(canonical(api_config(plan["api_url"]))) != plan["active_original_sha"]:
        raise MigrationError("Retorno nao confirmado; conferir o Caddy.")
    state["phase"] = "rolled_back"
    save(root / "producao.json", state)
    report.update(status="ROTA_ANTERIOR_RESTAURADA", banco_preservado=True,
                  observacao="Nenhuma restauracao destrutiva de banco. Tabelas adicionais e API nova preservadas para diagnostico.")


CADDY_AUTOSTART = '''param([string]$PigoCaddy,[string]$PigoConfig)
$ErrorActionPreference='Stop'
$pigoCurrentSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$pigoProcesses=@(Get-CimInstance Win32_Process -Filter "Name='caddy.exe'" | Where-Object { $_.ExecutablePath -eq $PigoCaddy })
if ($pigoProcesses.Count -ne 1) { throw 'Esperado um unico processo Caddy conhecido.' }
$pigoOwner=Invoke-CimMethod -InputObject $pigoProcesses[0] -MethodName GetOwnerSid
if ($pigoOwner.Sid -ne $pigoCurrentSid) { throw 'Caddy pertence a outra conta; preservar identidade e certificados antes de automatizar.' }
if (Get-ScheduledTask -TaskPath '\\' -TaskName 'LmdSharedCaddy' -ErrorAction SilentlyContinue) { throw 'Tarefa Caddy ja existe; nao sera substituida.' }
$pigoArgument='run --config "'+$PigoConfig+'" --adapter caddyfile'
$pigoAction=New-ScheduledTaskAction -Execute $PigoCaddy -Argument $pigoArgument -WorkingDirectory ([IO.Path]::GetDirectoryName($PigoConfig))
$pigoPrincipal=New-ScheduledTaskPrincipal -UserId $pigoCurrentSid -LogonType S4U -RunLevel Highest
$pigoTrigger=New-ScheduledTaskTrigger -AtStartup
$pigoTrigger.Delay='PT10S'
$pigoSettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval ([TimeSpan]::FromMinutes(1)) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskPath '\\' -TaskName 'LmdSharedCaddy' -Action $pigoAction -Principal $pigoPrincipal -Trigger $pigoTrigger -Settings $pigoSettings -Description 'Caddy compartilhado, mesma conta e certificados, inicio no proximo boot.' | Out-Null
# Do not start or stop shared Caddy now. The current process keeps all domains online.
Get-ScheduledTask -TaskPath '\\' -TaskName 'LmdSharedCaddy' | Select-Object TaskName,State
'''


def enable_caddy_autostart(root, report):
    state = load_state(root)
    if state["phase"] != "live":
        raise MigrationError("Conclua e confira a troca antes de automatizar o Caddy.")
    plan = state["caddy"]
    if sha_file(Path(plan["file"])) != plan["candidate_sha"]:
        raise MigrationError("Caddyfile mudou; revisar a inicializacao automatica.")
    directory = Path(state["pasta_privada"])
    report["pasta_privada"] = str(directory)
    script = directory / "caddy-autostart.ps1"
    script.write_text(CADDY_AUTOSTART, encoding="utf-8-sig")
    run_private(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script), plan["caddy"], plan["file"]], directory / "caddy-autostart.log")
    report.update(status="CADDY_AUTOSTART_CONFIGURADO", tarefa_caddy=CADDY_TASK, processo_atual_preservado=True,
                  observacao="A tarefa usara a mesma conta e configuracao no proximo boot. Mantenha o terminal Caddy atual aberto ate reinicio programado. Reboot nao executado nem testado.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["prepare", "cutover", "status", "rollback", "enable-caddy-autostart"], default="prepare")
    parser.add_argument("--current-root", type=Path, default=Path(r"C:\Projetos\P.I.G.O"))
    parser.add_argument("--production-root", type=Path, default=Path(r"C:\Projetos\PIGO-Producao-20261017"))
    parser.add_argument("--pg-bin", type=Path, default=Path(r"C:\Program Files\PostgreSQL\18\bin"))
    parser.add_argument("--caddy", type=Path, default=Path(r"C:\Projetos\caddy\caddy.exe"))
    parser.add_argument("--caddy-config", type=Path, default=Path(r"C:\Projetos\caddy\Caddyfile.production"))
    parser.add_argument("--cutover", action="store_true")
    args = parser.parse_args()
    report = {"computador": os.environ.get("COMPUTERNAME", "nao informado"), "status": "NAO_CONCLUIDO"}
    try:
        if os.name != "nt" or report["computador"].upper() != "WIN-JG1E0O7FSBS":
            raise MigrationError("Execute somente na VM Windows WIN-JG1E0O7FSBS.")
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise MigrationError("Abra o PowerShell como Administrador para registrar a tarefa Windows.")
        if args.action == "prepare":
            prepare(Path(__file__).resolve().parent, args.current_root, args.production_root, args.pg_bin,
                    args.caddy, args.caddy_config, "http://127.0.0.1:2019", report)
            if args.cutover:
                cutover(args.production_root, report)
        elif args.action == "cutover":
            cutover(args.production_root, report)
        elif args.action == "rollback":
            rollback(args.production_root, report)
        elif args.action == "enable-caddy-autostart":
            enable_caddy_autostart(args.production_root, report)
        else:
            state = load_state(args.production_root)
            report.update(status=state["phase"], banco=state["banco"], porta=state["porta"],
                          verificacoes_http=health(state["porta"], state["deployment_id"]), caddy_config_sha256=sha_bytes(canonical(api_config(state["caddy"]["api_url"]))))
    except Exception as error:
        report.update(status="NAO_CONCLUIDO", tipo_erro=type(error).__name__,
                      motivo=str(error) if isinstance(error, MigrationError) else "Operacao interrompida; consulte os diagnosticos privados. Credenciais nao serao exibidas.")
        code = 1
    else:
        code = 0
    if report.get("pasta_privada"):
        save(Path(report["pasta_privada"]) / "migracao-resultado.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
