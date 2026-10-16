import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import config
from app.database.connection import get_db
from app.services.agent_activation_service import ActivationError, activate_agent
from app.models.saas import AgentInstallation, Tenant
from app.routes.auth import get_current_user
from app.services.audit_service import write_audit_log


router = APIRouter(prefix="/agent", tags=["Remote Sync Agent"])
logger = logging.getLogger(__name__)
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = threading.Lock()


class AgentActivationPayload(BaseModel):
    license_api_key: str = ""
    company_cnpj: str = Field(min_length=1, max_length=30)
    installation_id: str = Field(min_length=16, max_length=100)
    machine_name: str = Field(min_length=1, max_length=255)
    machine_fingerprint: str = Field(min_length=16, max_length=128)
    agent_version: str = Field(min_length=1, max_length=50)
    reactivate: bool = False


def _activation_error(request_id: str, error: ActivationError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
        },
        headers={"X-Trace-Id": request_id},
    )


def _check_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    with _attempts_lock:
        attempts = _attempts[client_key]
        while attempts and attempts[0] < now - 3600:
            attempts.popleft()
        if len(attempts) >= config.AGENT_ACTIVATION_LIMIT_PER_HOUR:
            raise ActivationError(
                "ACTIVATION_LIMIT_REACHED",
                "Limite de tentativas de ativacao atingido.",
                429,
            )
        attempts.append(now)


def _require_installation_admin(current_user: dict) -> None:
    if current_user.get("auth_source") == "pigo":
        if "access.manage" in current_user.get("permissions", []):
            return
        raise ActivationError("PIGO_ACCESS_DENIED", "Usuario sem permissao para administrar instalacoes.", 403)
    role = str(current_user.get("role") or "").upper()
    if role not in {"MASTER", "ADMIN", "ADMINISTRATOR", "SUPPORT"}:
        raise ActivationError("PIGO_ACCESS_DENIED", "Usuario sem permissao para administrar instalacoes.", 403)


@router.post("/activate")
def activate_remote_sync_agent(
    request: Request,
    payload: AgentActivationPayload,
    db: Session = Depends(get_db),
):
    activation_started = time.perf_counter()
    request_id = str(request.state.trace_id)
    client_ip = request.client.host if request.client else "unknown"
    try:
        _check_rate_limit(client_ip)
        if not payload.license_api_key.strip():
            raise ActivationError(
                "MISSING_LICENSE_API_KEY",
                "Chave de licenca nao informada.",
                400,
            )
        result = activate_agent(db, payload, request_id, client_ip)
        logger.info(
            "agent.activation approved request_id=%s tenant_id=%s company_id=%s "
            "installation_id=%s reactivate=%s duration_ms=%s code=%s",
            request_id,
            result["tenant_id"],
            result["company_id"],
            payload.installation_id,
            payload.reactivate,
            round((time.perf_counter() - activation_started) * 1000),
            "AGENT_REACTIVATED" if payload.reactivate else "AGENT_ACTIVATED",
        )
        return {
            "success": True,
            "code": "AGENT_REACTIVATED" if payload.reactivate else "AGENT_ACTIVATED",
            **result,
            "request_id": request_id,
        }
    except ActivationError as exc:
        db.rollback()
        logger.warning(
            "agent.activation rejected request_id=%s cnpj=%s installation_id=%s code=%s status=%s duration_ms=%s",
            request_id,
            f"{payload.company_cnpj[:2]}********{payload.company_cnpj[-2:]}",
            payload.installation_id,
            exc.code,
            exc.status_code,
            round((time.perf_counter() - activation_started) * 1000),
        )
        return _activation_error(request_id, exc)


@router.post("/installations/{installation_id}/revoke")
def revoke_installation(
    installation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        _require_installation_admin(current_user)
        installation = db.query(AgentInstallation).filter(
            AgentInstallation.installation_id == installation_id,
            AgentInstallation.tenant_id == current_user.get("tenant_id"),
        ).first()
        if not installation:
            raise ActivationError("INSTALLATION_NOT_FOUND", "Instalacao nao encontrada.", 404)
        installation.status = "REVOKED"
        installation.revoked_at = datetime.now(timezone.utc)
        write_audit_log(
            db,
            action="agent.installation_revoked",
            entity_type="agent_installation",
            entity_id=installation_id,
            metadata={"request_id": request.state.trace_id},
        )
        db.commit()
        return {"success": True, "code": "INSTALLATION_REVOKED", "request_id": request.state.trace_id}
    except ActivationError as exc:
        db.rollback()
        return _activation_error(str(request.state.trace_id), exc)


@router.post("/installations/{installation_id}/regenerate-token")
def regenerate_remote_sync_token(
    installation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        _require_installation_admin(current_user)
        installation = db.query(AgentInstallation).filter(
            AgentInstallation.installation_id == installation_id,
            AgentInstallation.tenant_id == current_user.get("tenant_id"),
        ).first()
        if not installation or installation.status != "ACTIVE":
            raise ActivationError("INSTALLATION_BLOCKED", "Instalacao nao esta ativa.", 403)
        tenant = db.query(Tenant).filter(Tenant.id == installation.tenant_id).first()
        if not tenant:
            raise ActivationError("TENANT_CONFLICT", "Tenant da instalacao nao encontrado.", 409)
        tenant.api_token = uuid.uuid4()
        tenant.api_token_active = True
        tenant.api_token_created_at = datetime.now(timezone.utc)
        write_audit_log(
            db,
            action="agent.remote_sync_token_regenerated",
            entity_type="agent_installation",
            entity_id=installation_id,
            metadata={"tenant_id": str(tenant.id), "request_id": request.state.trace_id},
        )
        db.commit()
        return {
            "success": True,
            "code": "REMOTE_SYNC_TOKEN_REGENERATED",
            "remote_sync_token": str(tenant.api_token),
            "request_id": request.state.trace_id,
        }
    except ActivationError as exc:
        db.rollback()
        return _activation_error(str(request.state.trace_id), exc)
