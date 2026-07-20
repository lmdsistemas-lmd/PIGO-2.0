import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.services.audit_service import write_audit_log
from app.services.sync_service import SyncService
from app.services.tenant_access_service import get_tenant_by_api_token, validate_tenant_access


router = APIRouter(prefix="/sync", tags=["Sincronismo"])
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SyncData(BaseModel):
    cnpj: str
    type: str
    content: Any
    timestamp: str


@router.post("")
async def receive_sync_data(
    data: SyncData,
    authorization: str = Header(None),
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
        logger.warning(f"[SYNC] Chamada sem token de autorizacao do CNPJ: {data.cnpj}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sincronismo nao informado",
        )

    cnpj = re.sub(r"\D", "", str(data.cnpj or ""))

    token = authorization.replace("Bearer ", "").strip()
    tenant = get_tenant_by_api_token(db, token)

    if not tenant:
        logger.warning(f"[SYNC] API_TOKEN invalido ou inativo para CNPJ declarado: {cnpj}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": "API Token invalido ou inativo",
            },
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": "CNPJ do agente nao corresponde ao tenant do API Token",
            },
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=access_message)

    try:
        stats = SyncService.process_sync_data(
            db=db,
            tenant=tenant,
            cnpj=tenant_cnpj,
            data_type=data.type,
            content=data.content,
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
                "timestamp": datetime.now().isoformat(),
            }

        raise RuntimeError(stats.get("error") or "Falha ao persistir dados no banco de dados")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[SYNC] Erro ao processar sincronismo: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
