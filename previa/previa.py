"""PIGO visual preview: local synthetic snapshots; no database or ERP connection."""
import argparse
import copy
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'painel'
TOKEN = 'pigo-preview-local-only'
SNAPSHOT = json.loads((ROOT / 'samples.json').read_text(encoding='utf-8'))
SAMPLES = SNAPSHOT['samples']
NOTICE = '''<style>
.pigo-preview-banner{position:fixed;top:0;left:0;right:0;z-index:2147483647;min-height:64px;box-sizing:border-box;padding:9px 18px;background:#fff3c4;color:#473500;border-bottom:1px solid #cda93a;font:14px/1.5 system-ui;display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:5px 18px}
.pigo-preview-banner a{color:#1e40af}body{padding-top:var(--preview-height,96px)!important}.sidebar{top:var(--preview-height,96px)!important;height:calc(100vh - var(--preview-height,96px))!important}.topbar-shell{top:var(--preview-height,96px)!important}
dialog::before{content:'PRÉVIA · DADOS FICTÍCIOS · SEM GRAVAÇÃO';display:block;margin-bottom:16px;padding:8px 10px;background:#fff3c4;color:#473500;border-radius:8px;font:12px/1.5 system-ui}
@media(max-width:700px){.pigo-preview-banner{font-size:12px;padding:7px;gap:2px 7px}}
</style><aside class="pigo-preview-banner" aria-label="Aviso de demonstracao"><strong>PRÉVIA · DADOS FICTÍCIOS</strong><span>Sem conexão com ERP ou produção. Alterações não são gravadas.</span><span>CNPJ: 00000000000191 · usuário: demo · senha: demo</span></aside>
<script>new ResizeObserver(entries=>document.documentElement.style.setProperty('--preview-height',entries[0].target.offsetHeight+'px')).observe(document.querySelector('.pigo-preview-banner'));</script>'''


def sample(method, path, query):
    candidates = [item for item in SAMPLES if item['method'] == method and item['path'] == path]
    if not candidates:
        return None
    def score(item):
        recorded = parse_qs(item['query'])
        return sum(2 if recorded.get(key) == value else -1 for key, value in query.items())
    return copy.deepcopy(max(candidates, key=score)['data'])


class Preview(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Do not log submitted credentials, request bodies or query parameters.
        pass

    def send_data(self, status, data, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def handle_request(self):
        host = self.headers.get('Host', '')
        if host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
            return self.send_data(403, {'detail': 'Esta previa permite apenas acesso local.'})
        url = urlsplit(self.path)
        path = unquote(url.path)
        query = parse_qs(url.query)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 65536:
                raise ValueError()
            payload = json.loads(self.rfile.read(length)) if length else {}
        except (ValueError, UnicodeError):
            return self.send_data(400, {'detail': 'Solicitacao invalida.'})

        if path == '/api/health' and self.command == 'GET':
            return self.send_data(200, {'status': 'ok', 'service': 'pigo-visual-preview', 'demo': True,
                                        'fixture_date': SNAPSHOT['fixture_date']})
        if path == '/api/auth/login' and self.command == 'POST':
            if not isinstance(payload, dict) or (re.sub(r'\D', '', str(payload.get('cnpj', ''))),
                    payload.get('login'), payload.get('senha')) != ('00000000000191', 'demo', 'demo'):
                return self.send_data(401, {'detail': 'Previa: use CNPJ 00000000000191, usuario demo e senha demo.'})
            user = sample('GET', '/api/auth/me', {})
            return self.send_data(200, {'access_token': TOKEN, 'token_type': 'bearer', 'user': user})

        if path.startswith('/api/'):
            if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
                return self.send_data(401, {'detail': 'Entre com o usuario de demonstracao.'})
            if any(value != '1' for value in query.get('empresa_id', [])):
                return self.send_data(404, {'detail': 'A previa contem somente a empresa ficticia 1.'})
            if self.command == 'POST' and path == '/api/reports/assistant/interpret':
                if not isinstance(payload, dict) or str(payload.get('prompt', '')).strip().casefold() != 'Vendas por produto deste mês'.casefold():
                    return self.send_data(422, {'detail': 'Exemplo disponivel nesta previa: Vendas por produto deste mês. A interpretacao completa faz parte do backend.'})
            elif self.command == 'POST' and path == '/api/reports/preview':
                known = sample('POST', '/api/reports/assistant/interpret', {})
                if not isinstance(payload, dict) or payload.get('definition') != known.get('report_definition'):
                    return self.send_data(422, {'detail': 'A previa contem a amostra do relatorio Vendas por produto deste mês.'})
            elif self.command not in {'GET', 'HEAD'}:
                return self.send_data(405, {'detail': 'Previa visual: nenhuma alteracao e gravada ou enviada ao ERP. Use os formularios apenas para avaliacao.'})

            export = self.command == 'GET' and path.startswith('/api/operacoes/') and path.endswith('/export')
            lookup = path[:-7] if export else path
            data = sample('GET' if self.command == 'HEAD' else self.command, lookup, query)
            if data is None:
                return self.send_data(404, {'detail': 'Esta consulta nao possui amostra na previa visual.'})
            if lookup.startswith('/api/operacoes/') and isinstance(data, dict) and isinstance(data.get('rows'), list):
                rows = data['rows']
                search = query.get('search', [''])[0].casefold().strip()
                if search:
                    rows = [row for row in rows if search in ' '.join(str(v) for v in row.values()).casefold()]
                data['total'] = len(rows)
                if export:
                    stream = io.StringIO(newline='')
                    columns = data.get('columns', [])
                    writer = csv.writer(stream)
                    writer.writerow([column['label'] for column in columns])
                    writer.writerows([[row.get(column['key'], '') for column in columns] for row in rows])
                    return self.send_data(200, stream.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', 'amostra-previa.csv')
                try:
                    page = max(1, int(query.get('page', ['1'])[0]))
                    size = min(100, max(1, int(query.get('page_size', ['20'])[0])))
                except ValueError:
                    return self.send_data(422, {'detail': 'Paginacao invalida.'})
                data['rows'] = rows[(page - 1) * size:page * size]
            return self.send_data(200, data)

        if self.command not in {'GET', 'HEAD'}:
            return self.send_data(405, {'detail': 'Metodo indisponivel.'})
        target = (SITE / path.lstrip('/')).resolve()
        if not target.is_relative_to(SITE.resolve()):
            return self.send_data(404, {'detail': 'Arquivo indisponivel.'})
        if target.is_file() and target.name != 'index.html':
            content_type = {'.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml'}.get(target.suffix)
            return self.send_data(200, target.read_bytes(), content_type or mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        if path in {'/', '/index.html', '/login'} or path.startswith(('/dashboard/', '/cadastros/', '/financeiro/', '/relatorios', '/funcionarios', '/performance')):
            html = (SITE / 'index.html').read_text(encoding='utf-8')
            html = html.replace('<body>', '<body>' + NOTICE, 1)
            return self.send_data(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        return self.send_data(404, {'detail': 'Arquivo indisponivel.'})

    do_GET = handle_request
    do_HEAD = handle_request
    do_POST = handle_request
    do_PUT = handle_request
    do_DELETE = handle_request
    do_PATCH = handle_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4020, choices=range(4020, 4100))
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Preview)
    except OSError:
        raise SystemExit('Porta indisponivel. Nenhum processo existente foi encerrado.')
    print(f'PIGO - PREVIA VISUAL COM DADOS FICTICIOS\nhttp://127.0.0.1:{args.port}/login\nCNPJ 00000000000191 | usuario demo | senha demo\nSem conexao com banco, ERP ou producao. Ctrl+C encerra somente esta previa.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
