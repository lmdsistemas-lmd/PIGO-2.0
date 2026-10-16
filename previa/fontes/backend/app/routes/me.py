from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.saas import Tenant
from app.routes.auth import get_current_user


router = APIRouter(prefix="/me", tags=["Usuario Atual"])


@router.get("/tenant")
def current_tenant(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao sem tenant_id.",
        )

    try:
        tenant_uuid = UUID(str(tenant_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="tenant_id invalido na sessao.",
        ) from exc

    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant nao encontrado.",
        )

    display_name = tenant.nome_fantasia or tenant.razao_social or tenant.cnpj
    return {
        "tenant_id": str(tenant.id),
        "cnpj": tenant.cnpj,
        "razao_social": tenant.razao_social,
        "nome_fantasia": tenant.nome_fantasia,
        "display_name": display_name,
        "has_pigo_access": bool(tenant.has_pigo_access),
        "license_status": tenant.license_status,
        "expires_at": tenant.license_expires_at.isoformat() if tenant.license_expires_at else None,
        "environment": tenant.environment,
        "api_token_active": bool(tenant.api_token_active),
    }
