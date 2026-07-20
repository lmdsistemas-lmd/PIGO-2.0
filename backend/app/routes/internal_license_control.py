import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import config
from app.database.connection import get_db
from app.middlewares.license_control_auth import validate_license_control_token
from app.schemas.license_control_sync import LicenseControlSyncResponse
from app.services.license_control_batch_sync_service import sync_license_control_batch
from app.services.license_control_sync_service import sync_license_control_tenant


router = APIRouter(prefix="/internal/license-control", tags=["License Control Internal"])
logger = logging.getLogger(__name__)


@router.post(
    "/tenants/sync",
    response_model=LicenseControlSyncResponse,
    response_model_exclude_none=True,
)
def sync_tenants_from_license_control(
    request: Request,
    payload: Any = Body(...),
    _: None = Depends(validate_license_control_token),
    db: Session = Depends(get_db),
):
    if isinstance(payload, dict) and "tenants" in payload:
        raw_items = payload["tenants"]
        if not isinstance(raw_items, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo tenants deve ser uma lista.",
            )
    elif isinstance(payload, dict):
        # Contrato real atual do PigoIntegrationService.ts: um tenant direto.
        raw_items = [payload]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload deve ser um objeto ou envelope com tenants.",
        )
    if not raw_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum tenant foi enviado.",
        )

    try:
        result = sync_license_control_batch(
            db=db,
            raw_items=raw_items,
            ip_address=request.client.host if request.client else None,
        )
        if len(raw_items) == len(result["errors"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result,
            )
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha geral na sincronizacao em lote do License Control.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar sincronizacao.",
        )


class SyncTenantPayload(BaseModel):
    cnpj: str
    razao_social: str | None = None
    nome_fantasia: str | None = None
    license_status: str = "unknown"
    has_pigo_access: bool = Field(default=False)
    expires_at: str | None = None
    license_control_id: str | None = None
    environment: str = "production"
    product_slug: str | None = None
    project_slug: str | None = None
    email: str | None = None
    telefone: str | None = None
    responsavel: str | None = None


def _extract_internal_key(
    authorization: str | None,
    x_internal_api_key: str | None,
) -> str:
    if x_internal_api_key:
        return x_internal_api_key.strip()

    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1).strip()

    return ""


def _validate_internal_key(authorization: str | None, x_internal_api_key: str | None) -> None:
    expected = str(
        config.LICENSE_CONTROL_INTEGRATION_TOKEN
        or config.LICENSE_CONTROL_SYNC_KEY
        or ""
    ).strip()
    provided = _extract_internal_key(authorization, x_internal_api_key)

    if not expected:
        logger.error("LICENSE_CONTROL_SYNC_KEY nao configurada. Endpoint interno bloqueado.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chave interna do License Control nao configurada no P.I.G.O.",
        )

    if not provided or not hmac.compare_digest(provided, expected):
        logger.warning("Chave interna invalida no sync de tenant do License Control.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave interna invalida",
        )


@router.post("/sync-tenant")
def sync_tenant_from_license_control(
    request: Request,
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
    db: Session = Depends(get_db),
):
    _validate_internal_key(authorization, x_internal_api_key)

    try:
        if {"tenant_id", "company_id", "empresa", "produto", "ativo"} <= payload.keys():
            result = sync_license_control_batch(
                db=db,
                raw_items=[payload],
                ip_address=request.client.host if request.client else None,
            )
            if result["errors"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result,
                )
            return result

        legacy_payload = SyncTenantPayload.model_validate(payload)
        logger.info(
            "Recebida requisicao sync-tenant do License Control. cnpj=%s ip=%s user_agent=%s",
            legacy_payload.cnpj,
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
        result = sync_license_control_tenant(
            db=db,
            payload=legacy_payload.model_dump(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        logger.info(
            "sync-tenant finalizado. tenant_id=%s cnpj=%s has_pigo_access=%s license_status=%s api_token_created=%s api_token_active=%s",
            result.get("tenant_id"),
            result.get("cnpj"),
            result.get("has_pigo_access"),
            result.get("license_status"),
            result.get("api_token_created"),
            result.get("api_token_active"),
        )
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Erro ao sincronizar tenant vindo do License Control")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao sincronizar tenant vindo do License Control",
        )
