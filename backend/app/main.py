from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes.home import router as home_router
from app.routes.funcionarios import router as funcionarios_router
from app.routes.erp_test import router as erp_test_router
from app.routes.erp_pessoas import router as erp_pessoas_router
from app.routes.erp_colaboradores import router as erp_colaboradores_router
from app.routes.indicadores import router as indicadores_router
from app.routes.performance import router as performance_router
from app.routes.dashboard_financeiro import router as dashboard_financeiro_router
from app.routes.dashboard_vendas import router as dashboard_vendas_router
from app.routes.relatorio import router as relatorio_router
from app.routes.auth import router as auth_router
from app.routes.empresa import router as empresa_router
from app.routes.departamentos import router as departamentos_router
from app.routes.cargos import router as cargos_router
from app.routes.dashboard_consolidado import router as dashboard_consolidado_router
from app.routes.dashboard_estoque import router as dashboard_estoque_router
from app.routes.sync import router as sync_router
from app.database.erp_connection import current_cnpj
from app.core.security import decode_access_token
from fastapi import Request

app = FastAPI(
    title="Dashboard App API",
    version="1.0.0"
)

@app.middleware("http")
async def multi_company_middleware(request: Request, call_next):
    auth_header = request.headers.get("Authorization", "")
    cnpj = "default"
    
    print(f"[Middleware] Chamado para URL: {request.url.path}")

    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "").strip()
            
            # Se for uma rota de sync, podemos ter um token diferenciado
            if request.url.path.endswith("/sync"):
                # Para simplificar, aceitamos qualquer Bearer no sync por enquanto
                # ou podemos validar contra um STATIC_TOKEN
                cnpj = "remote_sync" 
                print(f"[Middleware] Sync detectado.")
            else:
                payload = decode_access_token(token)
                if payload and "cnpj" in payload:
                    cnpj = str(payload["cnpj"])
                    print(f"[Middleware] Token OK! CNPJ: {cnpj}")
                else:
                    print("[Middleware] Token sem CNPJ no payload.")
        except Exception as e:
            if not request.url.path.endswith("/sync"):
                print(f"[Middleware] Erro no Token: {e}")
            cnpj = "error"
            
    # Seta o CNPJ no contexto da requisição atual
    token_var = current_cnpj.set(cnpj)
    try:
        response = await call_next(request)
        return response
    finally:
        current_cnpj.reset(token_var)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(home_router)
app.include_router(funcionarios_router)
app.include_router(erp_test_router)
app.include_router(erp_pessoas_router)
app.include_router(erp_colaboradores_router)
app.include_router(indicadores_router)
app.include_router(performance_router)
app.include_router(dashboard_financeiro_router)
app.include_router(dashboard_vendas_router)
app.include_router(relatorio_router)
app.include_router(auth_router)
app.include_router(empresa_router)
app.include_router(departamentos_router)
app.include_router(cargos_router)
app.include_router(dashboard_consolidado_router)
app.include_router(dashboard_estoque_router)
app.include_router(sync_router, prefix="/api")


@app.get("/health", tags=["Sistema"])
def health_check():
    return {
        "success": True,
        "message": "API online"
    }


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")


@app.get("/", include_in_schema=False)
def serve_frontend_root():
    index_file = FRONTEND_DIST_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": "Frontend buildado não encontrado. Execute o build do React."
        }
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_spa(full_path: str):
    blocked_prefixes = (
        "docs",
        "redoc",
        "openapi.json",
        "assets",
        "health",
        "auth",
        "funcionarios",
        "erp_test",
        "erp_pessoas",
        "erp_colaboradores",
        "indicadores",
        "performance",
        "dashboard_financeiro",
        "dashboard_vendas",
        "relatorio",
        "empresa",
        "departamentos",
        "cargos",
        "dashboard",
        "sync",
    )

    if full_path.startswith(blocked_prefixes):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Rota não encontrada"}
        )

    index_file = FRONTEND_DIST_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": "Frontend buildado não encontrado. Execute o build do React."
        }
    )
