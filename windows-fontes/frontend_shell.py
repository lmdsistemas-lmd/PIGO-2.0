"""Serve public React navigation URLs while delegating the existing API intact."""
from pathlib import Path
import re

from starlette.datastructures import Headers
from starlette.responses import FileResponse, JSONResponse


# Match React routes explicitly. In particular /api, /assets, /docs and legacy
# JSON endpoints are never turned into HTML by a catch-all or a 404 handler.
FRONTEND_ROUTES = tuple(re.compile(pattern) for pattern in (
    r"/", r"/login", r"/estoque",
    r"/dashboard/(?:consolidado|vendas|financeiro|estoque|clientes|curva-abc|metas)",
    r"/dashboard/vendas/detalhes",
    r"/funcionarios", r"/funcionarios/novo", r"/funcionarios/[^/]+/analise",
    r"/performance(?:/(?:exclusoes|inclusoes|alteracoes|cancelamentos))?",
    r"/relatorios", r"/relatorios/[^/]+",
    r"/relatorios/[^/]+/(?:novo|preview-temporario)",
    r"/relatorios/[^/]+/[^/]+/(?:editar|preview)",
    r"/cadastros/(?:clientes|fornecedores|produtos|departamentos|grupos|subgrupos|marcas|plano-contas)",
    r"/financeiro/(?:receber|pagar|fechamentos|fluxo-caixa|cheques|sangrias)",
))


def wants_html(scope):
    for item in Headers(scope=scope).get("accept", "").split(","):
        media, *parameters = item.strip().lower().split(";")
        if media != "text/html":
            continue
        for parameter in parameters:
            name, separator, value = parameter.strip().partition("=")
            if separator and name == "q":
                try:
                    if float(value) <= 0:
                        break
                except ValueError:
                    break
        else:
            return True
    return False


class FrontendShell:
    def __init__(self, backend, index_file):
        self.backend = backend
        self.index_file = Path(index_file)

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope["method"] in {"GET", "HEAD"}
                and any(route.fullmatch(scope["path"]) for route in FRONTEND_ROUTES)
                and wants_html(scope)):
            if self.index_file.is_file():
                response = FileResponse(self.index_file, media_type="text/html",
                                        headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
            else:
                response = JSONResponse({"detail": "Frontend compilado nao encontrado."}, status_code=503)
            await response(scope, receive, send)
            return
        # This includes auth, licensing, sync, activation, assets, unknown paths,
        # non-HTML requests, writes, WebSockets and the application's lifespan.
        await self.backend(scope, receive, send)
