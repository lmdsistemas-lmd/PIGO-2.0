"""Read-only PIGO publication diagnostic. No database, task or Caddy changes."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

DOMAIN = 'pigo.lmdsistemasdev.qzz.io'
ROOT = Path(r'C:\Projetos\PIGO-Producao-20261017')
OPENER = build_opener(ProxyHandler({}))
USER_AGENT = dict(OPENER.addheaders).get('User-agent', 'PIGO-Publication-Diagnostic/1')
LIMIT = 512 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def safe_error(error):
    if isinstance(error, URLError):
        error = error.reason
    result = {'tipo_erro': type(error).__name__}
    if isinstance(error, ssl.SSLCertVerificationError):
        result['codigo_tls'] = error.verify_code
    if isinstance(error, OSError) and error.errno is not None:
        result['codigo_sistema'] = error.errno
    return result


def differences(left, right, path='$', result=None):
    """Report structural paths, never configuration values."""
    if result is None:
        result = []
    if left == right:
        return result
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            child = path + '/' + key
            if key not in left or key not in right:
                result.append(child + ' [presenca]')
            else:
                differences(left[key], right[key], child, result)
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            result.append(path + ' [quantidade]')
        for index, (a, b) in enumerate(zip(left, right)):
            differences(a, b, path + '/' + str(index), result)
    else:
        result.append(path)
    return result


def route_summary(config):
    matches = []
    def find(node):
        if isinstance(node, list):
            for item in node:
                find(item)
        elif isinstance(node, dict):
            if any(DOMAIN in group.get('host', []) for group in node.get('match', []) if isinstance(group, dict)):
                matches.append(node)
            for key, value in node.items():
                if key != 'match':
                    find(value)
    find(config)
    handlers, destinations, statuses = set(), set(), set()
    def details(node):
        if isinstance(node, list):
            for item in node:
                details(item)
        elif isinstance(node, dict):
            handler = node.get('handler')
            if isinstance(handler, str) and re.fullmatch(r'[a-z_]{1,60}', handler):
                handlers.add(handler)
            for item in node.get('upstreams', []):
                address = item.get('dial', '') if isinstance(item, dict) else ''
                destinations.add(address if isinstance(address, str) and re.fullmatch(r'(?:127\.0\.0\.1|localhost):\d+', address) else '<destino omitido>')
            if handler == 'static_response':
                status = str(node.get('status_code', '200'))
                if status.isdecimal():
                    statuses.add(status)
            for value in node.values():
                details(value)
    for match in matches:
        details(match)
    return {'grupos': len(matches), 'handlers': sorted(handlers), 'destinos_locais': sorted(destinations), 'respostas_fixas_http': sorted(statuses)}


def response_summary(response, body, deployment, index_sha=None):
    headers = response.headers
    result = {'http': response.status if hasattr(response, 'status') else response.code,
              'instancia_nova': headers.get('X-Pigo-Deployment') == deployment,
              'identificador_instancia_presente': bool(headers.get('X-Pigo-Deployment')),
              'tipo_conteudo': headers.get('Content-Type', '').split(';')[0][:80],
              'cloudflare': headers.get('CF-Ray') is not None,
              'servidor_caddy': 'caddy' in headers.get('Server', '').lower(),
              'servidor_iis': 'iis' in headers.get('Server', '').lower(),
              'bytes_lidos': len(body)}
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        value = None
    if isinstance(value, dict):
        if value.get('service') == 'pigo':
            result['service_pigo'] = True
        code = value.get('code')
        if code in {'LICENSE_CONTROL_BLOCKED', 'PIGO_ACCESS_DENIED', 'INSTALLATION_BLOCKED', 'TENANT_CONFLICT'}:
            result['codigo_aplicacao'] = code
    if index_sha is not None:
        result['html_novo'] = digest(body) == index_sha
    result['resposta_excede_limite'] = len(body) > LIMIT
    return result


def probe(url, deployment, index_sha=None, opener=None):
    request = Request(url, headers={'Accept': 'text/html' if index_sha else 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': USER_AGENT})
    try:
        with (opener or OPENER).open(request, timeout=10) as response:
            return response_summary(response, response.read(LIMIT + 1), deployment, index_sha)
    except HTTPError as error:
        return response_summary(error, error.read(LIMIT + 1), deployment, index_sha)
    except (OSError, URLError, http.client.HTTPException) as error:
        return safe_error(error)


class LoopbackHTTPS(http.client.HTTPSConnection):
    """Use local Caddy TCP while retaining the real hostname, SNI and TLS checks."""
    def connect(self):
        raw = socket.create_connection(('127.0.0.1', self.port or 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def probe_local_caddy(path, deployment, index_sha=None, context=None, port=443):
    connection = LoopbackHTTPS(DOMAIN, port=port, timeout=10, context=context or ssl.create_default_context())
    try:
        connection.request('GET', path, headers={'Host': DOMAIN, 'Accept': 'text/html' if index_sha else 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': USER_AGENT})
        response = connection.getresponse()
        return response_summary(response, response.read(LIMIT + 1), deployment, index_sha)
    except (OSError, http.client.HTTPException) as error:
        return safe_error(error)
    finally:
        connection.close()


def inspect(root):
    state = read_json(root / 'producao.json')
    if state.get('root') != str(root.resolve()) or state.get('banco') != 'pigo-dashboard' or state.get('schema') != 1:
        raise ValueError('Estado nao corresponde a producao esperada.')
    report = {'status': 'DIAGNOSTICO_SOMENTE_LEITURA', 'instalacao_preparada': True, 'fase': state['phase'],
              'verificado_em_utc': datetime.now(timezone.utc).isoformat(), 'configuracao_conferida': True}
    manifest = read_json(root / 'manifesto.json')
    files = [(Path(state['configuracao']), state['configuracao_sha256']),
             (root / 'manifesto.json', state['manifest_sha256']),
             (root / 'backend/run_production.py', state['runner_sha256'])]
    files.extend((root / relative, sha) for relative, sha in manifest['files'].items())
    if any(digest(file.read_bytes()) != sha for file, sha in files):
        raise ValueError('Integridade dos arquivos mudou; interrompido.')
    plan = state['caddy']
    api = urlsplit(plan['api_url'])
    if api.scheme != 'http' or api.hostname not in {'127.0.0.1', 'localhost', '::1'} or api.username or api.password:
        raise ValueError('API Caddy deve ser local.')
    with OPENER.open(plan['api_url'].rstrip('/') + '/config/', timeout=8) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Limite de configuracao excedido.')
    active = json.loads(data)
    report['caddy_ativo'] = {'igual_anterior': digest(canonical(active)) == plan['active_original_sha'],
                             'igual_candidato': digest(canonical(active)) == plan['active_candidate_sha'],
                             'rota_pigo': route_summary(active)}
    source_sha = digest(Path(plan['file']).read_bytes())
    report['caddy_arquivo'] = {'igual_anterior': source_sha == plan['original_sha'], 'igual_candidato': source_sha == plan['candidate_sha']}
    before = read_json(Path(state['pasta_privada']) / 'caddy-active-original.json')
    diff = differences(before, active)
    report['diferencas_ativo_anterior'] = {'total': len(diff), 'caminhos': diff[:40]}
    try:
        report['dns_enderecos'] = sorted({item[4][0] for item in socket.getaddrinfo(DOMAIN, 443, type=socket.SOCK_STREAM)})
    except OSError as error:
        report['dns'] = safe_error(error)
    deployment = state['deployment_id']
    index_sha = digest((root / 'frontend/dist/index.html').read_bytes())
    report['api_nova_local'] = probe('http://127.0.0.1:' + str(state['porta']) + '/api/health', deployment)
    report['https_caddy_local_health'] = probe_local_caddy('/api/health', deployment)
    report['https_caddy_local_login'] = probe_local_caddy('/login', deployment, index_sha)
    report['https_publico_health'] = probe('https://' + DOMAIN + '/api/health', deployment)
    report['https_publico_login'] = probe('https://' + DOMAIN + '/login', deployment, index_sha)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-root', type=Path, default=ROOT)
    args = parser.parse_args()
    report = {'status': 'DIAGNOSTICO_INTERROMPIDO'}
    try:
        if os.name != 'nt' or os.environ.get('COMPUTERNAME', '').upper() != 'WIN-JG1E0O7FSBS':
            raise ValueError('Execute na VM correta.')
        report = inspect(args.production_root)
    except Exception as error:
        report.update(safe_error(error))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
