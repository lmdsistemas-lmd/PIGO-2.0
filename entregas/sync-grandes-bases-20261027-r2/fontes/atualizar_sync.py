"""Source-only update. --check is the default; no automatic source fallback."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent
TASK = "PigoDashboardProduction"


class UpdateError(Exception):
    pass


def is_windows():
    return os.name == "nt"


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def manifest():
    return json.loads((ROOT / "manifesto-sync.json").read_text(encoding="utf-8"))


def files_for(kind, target):
    entries = manifest()[kind]
    for relative, entry in entries.items():
        source = ROOT / entry["source"]
        dest = Path(target) / relative
        if digest(source) != entry["new_sha256"]:
            raise UpdateError("PACOTE_ALTERADO:" + relative)
        if dest.exists() and digest(dest) not in {entry.get("old_sha256"), entry["new_sha256"], *entry.get("compatible_old_sha256", [])}:
            raise UpdateError("ARQUIVO_ATUAL_DIVERGENTE:" + relative)
        if not dest.exists() and entry.get("old_sha256"):
            raise UpdateError("ARQUIVO_ATUAL_AUSENTE:" + relative)
    return entries


def backup_sources(kind, target, directory):
    directory.mkdir(parents=True, exist_ok=False)
    original = {}
    for relative in manifest()[kind]:
        path = Path(target) / relative
        if path.exists():
            backup = directory / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            original[relative] = digest(path)
        else:
            original[relative] = None
    (directory / "originais.json").write_text(json.dumps(original, indent=2), encoding="utf-8")


def replace_sources(kind, target):
    for relative, entry in manifest()[kind].items():
        dest = Path(target) / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(dest.name + ".pigo-update.tmp")
        shutil.copyfile(ROOT / entry["source"], temporary)
        os.replace(temporary, dest)


def restore_sources(kind, target, directory):
    originals = json.loads((directory / "originais.json").read_text())
    for relative, old_sha in reversed(list(originals.items())):
        dest = Path(target) / relative
        current = digest(dest) if dest.exists() else None
        if current not in {old_sha, manifest()[kind][relative]["new_sha256"]}:
            raise UpdateError("RETORNO_INTERROMPIDO_ARQUIVO_DIVERGENTE:" + relative)
        if old_sha:
            temporary = dest.with_name(dest.name + ".pigo-return.tmp")
            shutil.copyfile(directory / relative, temporary)
            os.replace(temporary, dest)
        elif dest.exists():
            dest.unlink()


def source_check_agent(agent_dir, data_dir):
    # Imports updated code, but all existing credential/driver dependencies remain installed.
    if not (data_dir / "config.json").is_file():
        raise UpdateError("CONFIG_DESKTOP_NAO_LOCALIZADA; informe --data-dir")
    os.environ["PIGO_REMOTE_SYNC_DATA_DIR"] = str(data_dir)
    os.chdir(agent_dir)
    sys.path.insert(0, str(agent_dir))
    import owner  # Use the installed IPC contract during this read-only preflight.
    sys.path.insert(0, str(ROOT / "remote-sync-agent"))
    import agent
    if agent.CONFIG.mode != "desktop":
        raise UpdateError("MODO_DESKTOP_NECESSARIO")
    from sync_engine import windows_protect
    try:
        probe = b"pigo-sync-checkpoint-v2"
        if windows_protect(windows_protect(probe), decrypt=True) != probe:
            raise ValueError("roundtrip")
    except Exception as exc:
        raise UpdateError("DPAPI_CHECKPOINT_TEST_FAILED:" + type(exc).__name__) from exc
    if not agent.INSTALLATION_FILE.is_file():
        raise UpdateError("IDENTIDADE_EXISTENTE_NAO_LOCALIZADA; nenhuma identidade nova foi criada")
    identity = json.loads(agent.INSTALLATION_FILE.read_text(encoding="utf-8-sig"))
    if not identity.get("installation_id"):
        raise UpdateError("IDENTIDADE_EXISTENTE_INVALIDA")
    remote = agent.diagnose_remote_result()
    if not remote.get("success"):
        raise UpdateError("TESTE_REMOTO:" + str(remote.get("code")))
    if agent.REMOTE_SYNC_PROTOCOL != 2:
        raise UpdateError("ATUALIZE_O_BACKEND_PRIMEIRO")
    connection = None
    try:
        connection = agent.get_db_connection()
        schema = agent.FirebirdSchema(connection).load()
        plans = agent.build_sync_plans(schema)
        cursor = connection.cursor()
        try:
            companies = None
            if schema.has_table("TB_EMPRESA"):
                cursor.execute("SELECT COUNT(*) FROM TB_EMPRESA")
                companies = int(cursor.fetchone()[0])
        finally:
            cursor.close()
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc
    except Exception as exc:
        raise UpdateError("FIREBIRD_TESTE_FALHOU:" + type(exc).__name__) from exc
    finally:
        if connection:
            connection.close()
    return {"protocolo_servidor": 2, "checkpoint_dpapi_ok": True, "firebird_leitura_ok": True, "empresas_na_base": companies,
            "tabelas_planejadas": len(plans), "recursos_indisponiveis": getattr(plans, "unavailable", []), "tabelas_sem_pk_declarada": [plan.name for plan in plans if not plan.order_keys], "sem_envio_de_registros": True}


@contextmanager
def owner_stopped(data_dir):
    if not is_windows():
        raise UpdateError("INSTALACAO_CLIENTE_REQUER_WINDOWS")
    import msvcrt
    handles = []
    try:
        for name in ("agent.lock", "sync-cycle.lock"):
            handle = (data_dir / name).open("a+b")
            handles.append(handle)
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                handles.pop().close()
                raise UpdateError("FECHE_O_REMOTE_SYNC_E_AGUARDE_O_AGENTE_ENCERRAR") from exc
        yield
    finally:
        for handle in handles:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                handle.close()


def update_agent(args):
    target = Path(args.agent_dir).resolve()
    data_dir = Path(args.data_dir)
    files_for("agent", target)
    result = {"computador": os.environ.get("COMPUTERNAME"), "modo": "agente", "pasta_agente": str(target)}
    if not args.apply:
        return {**result, **source_check_agent(target, data_dir), "status": "CONFERIDO_SEM_INSTALAR"}
    if all((target / relative).is_file() and digest(target / relative) == entry["new_sha256"] for relative, entry in manifest()["agent"].items()):
        return {**result, "status": "AGENTE_JA_ATUALIZADO", "progresso": str(data_dir / "progresso.html")}
    with owner_stopped(data_dir):
        result.update(source_check_agent(target, data_dir))
        files_for("agent", target)
        backup = data_dir / "updates" / ("sync-" + stamp())
        backup_sources("agent", target, backup)
        try:
            replace_sources("agent", target)
        except Exception:
            restore_sources("agent", target, backup)
            raise
    return {**result, "status": "AGENTE_ATUALIZADO", "backup_fontes": str(backup),
            "progresso": str(data_dir / "progresso.html"),
            "observacao": "Abra novamente o aplicativo. Configuracao, cofre e credenciais preservados. A primeira execucao v2 refaz a carga completa em lotes."}


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]


def load_production(root):
    state = json.loads((root / "producao.json").read_text(encoding="utf-8-sig"))
    config = Path(state["configuracao"])
    if digest(config) != state["configuracao_sha256"]:
        raise UpdateError("CONFIGURACAO_PRODUCAO_DIVERGENTE")
    for raw in config.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ[name.strip()] = value.strip().strip('"').strip("'")
    from sqlalchemy.engine import make_url
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != state["banco"]:
        raise UpdateError("BANCO_ATUAL_NAO_CONFERE")
    return state, url


def local_json(port, path):
    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}" + path, timeout=5) as response:
        return json.loads(response.read())


def ps(command):
    proc = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise UpdateError("TAREFA_WINDOWS_FALHOU")
    return proc.stdout.strip()


def wait_health(port, *, updated=False, timeout=45):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        try:
            if local_json(port, "/api/health").get("status") == "ok":
                if not updated or local_json(port, "/api/sync/capabilities").get("protocol_version") == 2:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1): return True
    except OSError:
        return False


def find_dump():
    return next((path for path in [Path(r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"),
                                  Path(r"C:\Program Files\pgAdmin 4\runtime\pg_dump.exe")] if path.is_file()), None)


def update_backend(args):
    if not is_windows() or os.environ.get("COMPUTERNAME") != "WIN-JG1E0O7FSBS":
        raise UpdateError("EXECUTE_NA_VM_WIN-JG1E0O7FSBS")
    root = Path(args.production_root).resolve()
    target = root / "backend"
    files_for("backend", target)
    state, url = load_production(root)
    port = int(state["porta"])
    if port != 4024:
        raise UpdateError("PORTA_PRODUCAO_DIVERGENTE")
    current_healthy = wait_health(port, timeout=5)
    # Check the registered task; never choose or stop another Python or shared Caddy process.
    task = json.loads(ps("Get-ScheduledTask -TaskName 'PigoDashboardProduction' -ErrorAction Stop | Select-Object TaskName,State,@{N='Acoes';E={@($_.Actions | Select-Object Execute,Arguments)}} | ConvertTo-Json -Depth 5"))
    actions = json.dumps(task.get("Acoes", []), ensure_ascii=False).lower().replace("\\\\", "\\")
    if "run_production.py" not in actions or str(target).lower() not in actions:
        raise UpdateError("TAREFA_NAO_APONTA_PARA_ESTA_PRODUCAO")
    if not current_healthy:
        os.environ["PIGO_PATCH_ROOT"] = str(root)
        check = json.loads(ps("$p=@(Get-NetTCPConnection -State Listen -LocalPort 4024 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique); $v=@($p | ForEach-Object { Get-CimInstance Win32_Process -Filter ('ProcessId='+$_) }); [PSCustomObject]@{Quantidade=$v.Count; Confere=($v.Count -gt 0 -and @($v | Where-Object { -not $_.CommandLine -or $_.CommandLine.IndexOf($env:PIGO_PATCH_ROOT,[StringComparison]::OrdinalIgnoreCase) -lt 0 -or $_.CommandLine.IndexOf('run_production.py',[StringComparison]::OrdinalIgnoreCase) -lt 0 }).Count -eq 0)} | ConvertTo-Json"))
        if not check.get("Confere"):
            raise UpdateError("API_INDISPONIVEL_E_PROCESSO_NAO_CONFIRMADO; nenhum processo foi encerrado")
    result = {"api_atual_responde": current_healthy, "computador": os.environ.get("COMPUTERNAME"), "modo": "backend", "pasta": str(target), "porta": port,
              "tarefa": TASK, "configuracao_preservada": True}
    if not args.apply:
        return {**result, "status": "CONFERIDO_SEM_INSTALAR"}
    if all((target / relative).is_file() and digest(target / relative) == entry["new_sha256"] for relative, entry in manifest()["backend"].items()):
        if local_json(port, "/api/sync/capabilities").get("protocol_version") == 2:
            return {**result, "status": "BACKEND_JA_ATUALIZADO", "protocolo": 2}
    backup = Path(state["pasta_privada"]) / ("sync-update-" + stamp())
    backup_sources("backend", target, backup)
    dump = find_dump()
    if not dump:
        raise UpdateError("PG_DUMP_NAO_LOCALIZADO")
    env = {**os.environ, "PGHOST": str(url.host), "PGPORT": str(url.port or 5432), "PGDATABASE": str(url.database),
           "PGUSER": str(url.username or "postgres"), "PGPASSWORD": str(url.password or "")}
    database_backup = backup / "pigo-antes-sync-v2.dump"
    print("Criando backup consistente do PostgreSQL antes da atualizacao...", flush=True)
    with (backup / "pg_dump.log").open("wb") as log:
        proc = subprocess.run([str(dump), "--no-password", "--format=custom", "--file", str(database_backup)], env=env, stdout=log, stderr=log)
    if proc.returncode or not database_backup.is_file() or database_backup.stat().st_size == 0:
        raise UpdateError("BACKUP_POSTGRESQL_FALHOU; nenhuma API foi parada")
    restore = dump.with_name("pg_restore.exe")
    if not restore.is_file():
        raise UpdateError("PG_RESTORE_NAO_LOCALIZADO; API nao foi parada")
    with (backup / "pg_restore-list.log").open("wb") as log:
        checked = subprocess.run([str(restore), "--list", str(database_backup)], stdout=log, stderr=log)
    if checked.returncode:
        raise UpdateError("BACKUP_POSTGRESQL_LISTAGEM_FALHOU; API nao foi parada")
    files_for("backend", target)
    print("Reiniciando somente PigoDashboardProduction. O Caddy permanece em execucao...", flush=True)
    ps("Stop-ScheduledTask -TaskName 'PigoDashboardProduction' -ErrorAction Stop")
    until = time.monotonic() + 20
    while port_open(port) and time.monotonic() < until:
        time.sleep(1)
    if port_open(port):
        raise UpdateError("PORTA_4024_CONTINUA_OCUPADA; arquivos nao alterados")
    try:
        replace_sources("backend", target)
        ps("Start-ScheduledTask -TaskName 'PigoDashboardProduction' -ErrorAction Stop")
        if not wait_health(port, updated=True):
            raise UpdateError("API_ATUALIZADA_NAO_RESPONDEU")
    except Exception:
        ps("Stop-ScheduledTask -TaskName 'PigoDashboardProduction' -ErrorAction Stop")
        until = time.monotonic() + 20
        while port_open(port) and time.monotonic() < until:
            time.sleep(1)
        if port_open(port):
            raise UpdateError("RETORNO_REQUER_REVISAO: processo da API continua ativo; backup em " + str(backup))
        restore_sources("backend", target, backup)
        ps("Start-ScheduledTask -TaskName 'PigoDashboardProduction' -ErrorAction Stop")
        recovered = wait_health(port)
        raise UpdateError("ATUALIZACAO_REVERTIDA; API_anterior_responde=" + str(recovered))
    return {**result, "status": "BACKEND_ATUALIZADO", "protocolo": 2, "backup_fontes": str(backup),
            "backup_banco": {"arquivo": str(database_backup), "bytes": database_backup.stat().st_size, "sha256": digest(database_backup)},
            "caddy_alterado": False, "observacao": "Atualize agora o agente do cliente. Nenhum dado do ERP foi enviado pelo instalador."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["backend", "agent"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--agent-dir")
    parser.add_argument("--data-dir", default=os.environ.get("PIGO_REMOTE_SYNC_DATA_DIR") or str(Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "PIGO Remote Sync"))
    parser.add_argument("--production-root", default=r"C:\Projetos\PIGO-Producao-20261017")
    args = parser.parse_args()
    if args.apply and args.check:
        parser.error("Escolha --check ou --apply")
    if args.mode == "agent" and not args.agent_dir:
        parser.error("Informe --agent-dir")
    try:
        result = update_agent(args) if args.mode == "agent" else update_backend(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except UpdateError as exc:
        print(json.dumps({"status": "INTERROMPIDO", "motivo": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    except ImportError as exc:
        print(json.dumps({"status": "INTERROMPIDO", "tipo_erro": type(exc).__name__, "modulo": getattr(exc, "name", None)}, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "INTERROMPIDO", "tipo_erro": type(exc).__name__,
                          "motivo": "Falha inesperada; envie esta saida, sem arquivos de credenciais."}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
