from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.saas import Tenant
from app.services.tenant_access_service import get_tenant_by_cnpj, validate_tenant_access


router = APIRouter(prefix="/license", tags=["Licenciamento"])


def _tenant_from_authorization(db: Session, authorization: str | None) -> Tenant | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None

    payload = decode_access_token(authorization.replace("Bearer ", "").strip())
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            return tenant

    return get_tenant_by_cnpj(db, payload.get("cnpj"))


@router.get("/status")
def license_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    tenant = _tenant_from_authorization(db, authorization)
    if not tenant:
        return {
            "source": "license_control",
            "status": "not_authenticated",
            "message": "Licenciamento local desativado. Acesse com um tenant sincronizado pelo License Control.",
        }

    access_ok, message = validate_tenant_access(tenant)
    return {
        "source": "license_control",
        "tenant_id": str(tenant.id),
        "cnpj": tenant.cnpj,
        "razao_social": tenant.razao_social,
        "nome_fantasia": tenant.nome_fantasia,
        "status": "active" if access_ok else "blocked",
        "message": message,
        "license_status": tenant.license_status,
        "has_pigo_access": tenant.has_pigo_access,
        "expires_at": tenant.license_expires_at.isoformat() if tenant.license_expires_at else None,
        "environment": tenant.environment,
        "product_slug": tenant.product_slug,
        "api_token_active": tenant.api_token_active,
        "api_token_last_used_at": tenant.api_token_last_used_at.isoformat()
        if tenant.api_token_last_used_at
        else None,
    }
