from fastapi.responses import JSONResponse
from uuid import UUID

from app.core.security import decode_access_token
from app.database.connection import SessionLocal
from app.models.saas import Tenant
from app.services.tenant_access_service import get_tenant_by_cnpj, validate_tenant_access


LICENSED_PATH_PREFIXES = (
    "/api/dashboard",
    "/funcionarios",
    "/performance",
    "/indicadores",
    "/erp",
    "/rh",
    "/relatorio",
    "/relatorios",
    "/empresa",
    "/empresas",
    "/departamentos",
    "/cargos",
)


async def license_middleware(request, call_next):
    path = request.url.path
    should_validate = any(path.startswith(prefix) for prefix in LICENSED_PATH_PREFIXES)

    if should_validate:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token nao informado", "code": "AUTH_REQUIRED"},
            )

        db = SessionLocal()
        try:
            try:
                payload = decode_access_token(authorization.replace("Bearer ", "").strip())
            except Exception:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Sessao invalida ou expirada", "code": "AUTH_INVALID"},
                )

            tenant = None
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                try:
                    tenant = db.query(Tenant).filter(Tenant.id == UUID(str(tenant_id))).first()
                except ValueError:
                    tenant = None
            if not tenant:
                tenant = get_tenant_by_cnpj(db, payload.get("cnpj"))

            ok, message = validate_tenant_access(tenant)
            if not ok:
                return JSONResponse(
                    status_code=403,
                    content={"detail": message, "code": "LICENSE_CONTROL_BLOCKED"},
                )
        finally:
            db.close()

    return await call_next(request)
