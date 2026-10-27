import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.services.audit_service import write_audit_log
from app.services.sync_service import SyncService
from app.services.tenant_access_service import get_tenant_by_api_token, validate_tenant_access
from app.models.saas import AgentInstallation


router = APIRouter(prefix="/sync", tags=["Sincronismo"])
logger = logging.getLogger(__name__)


def _mask_cnpj(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 14:
        return "(invalid)"
    return f"{digits[:2]}********{digits[-2:]}"


def _auth_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    cnpj: str | None,
    authorization: str | None,
    tenant_id: str | None = None,
) -> JSONResponse:
    request_id = str(getattr(request.state, "trace_id", "") or "unknown")
    auth_present = bool(authorization)
    credential_type = (
        "bearer" if str(authorization or "").startswith("Bearer ") else "unsupported"
        if auth_present else "missing"
    )
    logger.warning(
        "sync.auth_rejected request_id=%s route=%s method=%s auth_present=%s "
        "credential_type=%s expected_project=p-i-g-o-dashboard cnpj=%s "
        "tenant_resolved=%s code=%s status=%s",
        request_id,
        request.url.path,
        request.method,
        auth_present,
        credential_type,
        _mask_cnpj(cnpj),
        bool(tenant_id),
        code,
        status_code,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "code": code,
            "message": message,
            "request_id": request_id,
        },
        headers={"X-Trace-Id": request_id},
    )


def _installation_active(db: Session, tenant_id, installation_id: str | None) -> bool:
    if not installation_id:
        return True  # Compatibilidade exclusiva com agentes legados via API_TOKEN.
    return (
        db.query(AgentInstallation)
        .filter(AgentInstallation.tenant_id == tenant_id)
        .filter(AgentInstallation.installation_id == installation_id)
        .filter(AgentInstallation.status == "ACTIVE")
        .first()
        is not None
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/capabilities")
def sync_capabilities():
    return {"protocol_version": 2, "batch_max_records": 500,
            "batch_max_bytes": 1000000, "transactional_ack": True,
            "empty_text_primary_keys": SyncService.EMPTY_TEXT_PRIMARY_KEYS}


class SyncData(BaseModel):
    cnpj: str
    type: str
    content: Any
    timestamp: str
    batch: dict[str, Any] | None = None


@router.get("/health")
def sync_health(
    request: Request,
    cnpj: str,
    authorization: str = Header(None),
    x_installation_id: str | None = Header(None, alias="X-Installation-Id"),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _auth_error(
            request,
            status_code=401,
            code="MISSING_API_KEY",
            message="Credencial de integracao nao informada.",
            cnpj=cnpj,
            authorization=authorization,
        )

    token = authorization.replace("Bearer ", "").strip()
    tenant = get_tenant_by_api_token(db, token)
    if not tenant:
        return _auth_error(
            request,
            status_code=403,
            code="INVALID_API_KEY",
            message="Credencial de integracao invalida.",
            cnpj=cnpj,
            authorization=authorization,
        )

    if not _installation_active(db, tenant.id, x_installation_id):
        return _auth_error(
            request,
            status_code=403,
            code="INSTALLATION_BLOCKED",
            message="Instalacao nao autorizada.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    normalized_cnpj = re.sub(r"\D", "", str(cnpj or ""))
    tenant_cnpj = re.sub(r"\D", "", str(tenant.cnpj or ""))
    if normalized_cnpj != tenant_cnpj:
        return _auth_error(
            request,
            status_code=403,
            code="CNPJ_MISMATCH",
            message="CNPJ nao autorizado para esta credencial.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    access_ok, access_message = validate_tenant_access(tenant)
    if not access_ok:
        code = "LICENSE_EXPIRED" if "expirada" in access_message.lower() else "SYNC_NOT_ALLOWED"
        return _auth_error(
            request,
            status_code=403,
            code=code,
            message="Sincronizacao nao autorizada para esta empresa.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    return {
        "status": "ok",
        "service": "pigo-remote-sync",
        "protocol_version": 2,
        "batch_max_records": 500,
        "transactional_ack": True,
        "authenticated": True,
        "tenant_resolved": True,
        "tenant_id": str(tenant.id),
    }


@router.post("")
def receive_sync_data(
    request: Request,
    data: SyncData,
    authorization: str = Header(None),
    x_installation_id: str | None = Header(None, alias="X-Installation-Id"),
    db: Session = Depends(get_db),
):
    received_count = len(data.content) if isinstance(data.content, list) else 0
    logger.info(
        "[SYNC] request cnpj_payload=%s data_type=%s received=%s",
        data.cnpj,
        data.type,
        received_count,
    )

    if not authorization or not authorization.startswith("Bearer "):
        return _auth_error(
            request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="MISSING_API_KEY",
            message="Credencial de integracao nao informada.",
            cnpj=data.cnpj,
            authorization=authorization,
        )

    cnpj = re.sub(r"\D", "", str(data.cnpj or ""))

    token = authorization.replace("Bearer ", "").strip()
    tenant = get_tenant_by_api_token(db, token)

    if not tenant:
        return _auth_error(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            code="INVALID_API_KEY",
            message="Credencial de integracao invalida.",
            cnpj=cnpj,
            authorization=authorization,
        )

    if not _installation_active(db, tenant.id, x_installation_id):
        return _auth_error(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSTALLATION_BLOCKED",
            message="Instalacao nao autorizada.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    tenant_cnpj = re.sub(r"\D", "", str(tenant.cnpj or ""))
    logger.info(
        "[SYNC] authenticated tenant_id=%s tenant_cnpj=%s payload_cnpj=%s data_type=%s received=%s",
        tenant.id,
        tenant_cnpj,
        cnpj,
        data.type,
        received_count,
    )
    if cnpj != tenant_cnpj:
        logger.warning(
            "[SYNC] CNPJ divergente para API_TOKEN. payload_cnpj=%s tenant_id=%s tenant_cnpj=%s",
            cnpj,
            tenant.id,
            tenant_cnpj,
        )
        write_audit_log(
            db,
            action="sync.api_token_auth_failed",
            entity_type="tenant",
            entity_id=str(tenant.id),
            metadata={
                "payload_cnpj": cnpj,
                "tenant_cnpj": tenant_cnpj,
                "data_type": data.type,
                "reason": "cnpj_mismatch",
            },
        )
        db.commit()
        return _auth_error(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            code="CNPJ_MISMATCH",
            message="CNPJ nao autorizado para esta credencial.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    tenant.api_token_last_used_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        action="sync.api_token_used",
        entity_type="tenant",
        entity_id=str(tenant.id),
        metadata={"cnpj": cnpj, "data_type": data.type},
    )

    access_ok, access_message = validate_tenant_access(tenant)
    if not access_ok:
        logger.warning("[SYNC] Bloqueado pelo License Control para CNPJ %s: %s", cnpj, access_message)
        write_audit_log(
            db,
            action="sync.blocked_by_license_control",
            entity_type="tenant",
            entity_id=str(tenant.id),
            metadata={
                "cnpj": cnpj,
                "data_type": data.type,
                "reason": access_message,
                "license_status": tenant.license_status,
                "has_pigo_access": tenant.has_pigo_access,
            },
        )
        db.commit()
        code = "LICENSE_EXPIRED" if "expirada" in access_message.lower() else "SYNC_NOT_ALLOWED"
        return _auth_error(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message="Sincronizacao nao autorizada para esta empresa.",
            cnpj=cnpj,
            authorization=authorization,
            tenant_id=str(tenant.id),
        )

    try:
        stats = SyncService.process_sync_data(
            db=db,
            tenant=tenant,
            cnpj=tenant_cnpj,
            data_type=data.type,
            content=data.content,
            batch=data.batch,
            installation_id=x_installation_id,
        )

        if stats.get("success"):
            logger.info(
                "[SYNC] persisted tenant_id=%s tenant_cnpj=%s payload_cnpj=%s data_type=%s "
                "destination=%s received=%s inserted=%s updated=%s ignored=%s ignored_reasons=%s",
                tenant.id,
                tenant_cnpj,
                cnpj,
                data.type,
                stats.get("destination_table"),
                stats.get("received"),
                stats.get("inserted"),
                stats.get("updated"),
                stats.get("ignored"),
                stats.get("ignored_reasons"),
            )
            return {
                "success": True,
                "message": f"Dados de {data.type} processados com sucesso",
                "tenant_id": str(tenant.id),
                "tenant_cnpj": tenant_cnpj,
                "payload_cnpj": cnpj,
                "data_type": data.type,
                "destination_table": stats.get("destination_table"),
                "received": stats.get("received"),
                "inserted": stats.get("inserted"),
                "updated": stats.get("updated"),
                "ignored": stats.get("ignored"),
                "ignored_reasons": stats.get("ignored_reasons"),
                "pk_columns": stats.get("pk_columns"),
                **{key: stats[key] for key in ("protocol_version", "batch_id", "payload_sha256", "persisted", "replayed") if key in stats},
                "timestamp": datetime.now().isoformat(),
            }

        if str(stats.get("error") or "").startswith("MIRROR_KEY_MIGRATION_REQUIRED"):
            raise HTTPException(409, detail={"code": "MIRROR_KEY_MIGRATION_REQUIRED",
                "message": "O espelho existente precisa ser migrado com as sequências físicas do ERP antes desta carga. Os registros existentes foram preservados."})
        if data.batch is not None:
            code = str(stats.get("error") or "SYNC_BATCH_PERSISTENCE_FAILED")
            status_code = 503 if code == "SYNC_RECEIVER_BUSY" else 500 if code == "SYNC_BATCH_PERSISTENCE_FAILED" else 422
            raise HTTPException(status_code, detail={"code": code, "message": "Lote nao confirmado; o agente preservou os dados para retomada."})
        raise RuntimeError(stats.get("error") or "Falha ao persistir dados no banco de dados")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[SYNC] Erro ao processar sincronismo: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
