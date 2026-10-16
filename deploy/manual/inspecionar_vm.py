"""Inspect installation prerequisites; no migrations, backup or application import."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess


def read_settings(path):
    result = {}
    if path.is_file():
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            line = raw.strip()
            if line and not line.startswith('#') and '=' in line:
                name, value = line.split('=', 1)
                result[name.strip()] = value.strip().strip('"').strip("'")
    return result


def inspect_database(value):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    url = make_url(value)
    result = {'tipo': url.get_backend_name(), 'local': url.host in {'localhost','127.0.0.1','::1'}, 'porta': url.port or 5432}
    if result['tipo'] != 'postgresql':
        return {**result, 'status': 'Banco PostgreSQL esperado; nenhum acesso realizado.'}
    engine = create_engine(url, connect_args={'timeout': 8}, pool_pre_ping=True)
    try:
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            row = db.execute(text("SELECT current_database(), current_setting('server_version')")).one()
            tables = set(db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).scalars())
            result.update(status='conexao_somente_leitura_ok', banco=row[0], versao_servidor=row[1],
                          tabelas_vm={name:name in tables for name in ['agent_installations','municipality_geocodes','TB_FECHAMENTO_CAIXA','TB_FECHAMENTO_CAIXA_ITEM']},
                          tabelas_novas={name:name in tables for name in ['sales_goals','erp_commands','pigo_access_profiles','pigo_access_users']})
            db.rollback()
    except Exception as error:
        result.update(status='conexao_nao_validada', tipo_erro=type(error).__name__)
    finally:
        engine.dispose()
    return result


def find_clients():
    candidates = []
    found = shutil.which('pg_dump') or shutil.which('pg_dump.exe')
    if found:
        candidates.append(Path(found))
    for variable in ['ProgramFiles','ProgramFiles(x86)']:
        root = os.environ.get(variable)
        if root:
            candidates.extend(Path(root).glob('PostgreSQL/*/bin/pg_dump.exe'))
            candidates.extend(Path(root).glob('pgAdmin 4/runtime/pg_dump.exe'))
    results = []
    for path in sorted(set(candidates)):
        try:
            process = subprocess.run([str(path),'--version'], capture_output=True, text=True, timeout=5)
            results.append({'pg_dump':str(path),'versao':process.stdout.strip() if process.returncode==0 else 'nao validada',
                            'pg_restore_existe':(path.parent/('pg_restore.exe' if os.name=='nt' else 'pg_restore')).is_file()})
        except (OSError,subprocess.SubprocessError):
            results.append({'pg_dump':str(path),'versao':'nao validada'})
    return results


def inspect_environment(root):
    settings = read_settings(root/'backend/.env')
    report = {'computador':os.environ.get('COMPUTERNAME','nao informado'),
              'env_existe':(root/'backend/.env').is_file(),
              'configuracao_presente':{name:bool(settings.get(name) or os.environ.get(name)) for name in ['DATABASE_URL','JWT_SECRET_KEY','LICENSE_CONTROL_INTEGRATION_TOKEN','LICENSE_CONTROL_SYNC_KEY']}}
    baseline_file = Path(__file__).resolve().parent/'base_vm.json'
    if baseline_file.is_file():
        baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
        changed, missing = [], []
        for relative, digest in baseline['files'].items():
            path = root/relative
            if not path.is_file():
                missing.append(relative)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                changed.append(relative)
        report['fontes_vm'] = {'iguais':len(baseline['files'])-len(changed)-len(missing),
                               'alterados':changed,'ausentes':missing,
                               'resultado':'CONFERE_COM_UPLOAD' if not changed and not missing else 'REVISAR_DIFERENCAS'}
    value = settings.get('DATABASE_URL') or os.environ.get('DATABASE_URL')
    try:
        report['banco'] = inspect_database(value) if value else {'status':'DATABASE_URL ausente; nenhum acesso realizado.'}
    except Exception as error:
        report['banco'] = {'status':'configuracao_nao_validada','tipo_erro':type(error).__name__}
    report['clientes_postgresql'] = find_clients()
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1',4023));report['porta_4023_livre'] = True
        except OSError:
            report['porta_4023_livre'] = False
    report['observacao'] = 'Somente leitura do ambiente. Senhas/tokens nao exibidos. Nenhuma migracao, copia de banco, inicializacao ou alteracao no Caddy.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current-root', required=True, type=Path)
    args = parser.parse_args()
    if not (args.current_root/'backend/app/main.py').is_file():
        parser.error('Backend atual nao encontrado nessa pasta.')
    print(json.dumps(inspect_environment(args.current_root),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
