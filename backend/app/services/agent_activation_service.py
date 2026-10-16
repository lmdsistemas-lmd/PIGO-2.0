import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.core import config
from app.models.official import Company
from app.models.saas import AgentInstallation, Tenant
from app.services.audit_service import write_audit_log
from app.services.tenant_access_service import validate_tenant_access


logger = logging.getLogger(__name__)


class ActivationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def normalize_cnpj(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 14:
        raise ActivationError("CNPJ_MISMATCH", "CNPJ informado e invalido.", 400)
    return digits


def validate_license_control(license_api_key: str, cnpj: str, request_id: str = "unknown") -> dict[str, Any]:
    url = f"{config.LICENSE_CENTRAL_URL.rstrip('/')}/api/licenses/activate"
    started = time.perf_counter()
    logger.info("agent.activation.license_control.started request_id=%s", request_id)
    try:
        response = requests.post(
            url,
            json={
                "licenseKey": license_api_key,
                "cnpj": cnpj,
                "projectSlug": config.LICENSE_PROJECT_SLUG,
                "productName": "PIGO Remote Sync",
            },
            timeout=(10, 20),
        )
    except requests.RequestException as exc:
        logger.warning("agent.activation.license_control.failed request_id=%s duration_ms=%s error=%s", request_id, round((time.perf_counter() - started) * 1000), type(exc).__name__)
        raise ActivationError(
            "LICENSE_CONTROL_UNAVAILABLE",
            "Nao foi possivel validar a licenca neste momento.",
            503,
        ) from exc

    if response.status_code >= 400:
        logger.warning("agent.activation.license_control.rejected request_id=%s duration_ms=%s status=%s", request_id, round((time.perf_counter() - started) * 1000), response.status_code)
        code = "INVALID_LICENSE_API_KEY"
        try:
            message = str(response.json().get("message") or "").lower()
        except ValueError:
            message = ""
        if "expir" in message:
            code = "LICENSE_EXPIRED"
        elif "projeto" in message or "project" in message:
            code = "PROJECT_MISMATCH"
        elif "cnpj" in message:
            code = "CNPJ_MISMATCH"
        elif "revog" in message or "inativ" in message:
            code = "LICENSE_INACTIVE"
        raise ActivationError(code, "Licenca nao autorizada para ativacao.")

    try:
        result = response.json()
    except ValueError as exc:
        raise ActivationError("LICENSE_CONTROL_INVALID_RESPONSE", "Resposta invalida do License Control.", 502) from exc

    project = result.get("project") or {}
    license_data = result.get("license") or {}
    if project.get("slug") != config.LICENSE_PROJECT_SLUG:
        raise ActivationError("PROJECT_MISMATCH", "Licenca pertence a outro projeto.")
    if str(license_data.get("status") or "").lower() != "active":
        raise ActivationError("LICENSE_INACTIVE", "Licenca nao esta ativa.")
    logger.info("agent.activation.license_control.completed request_id=%s duration_ms=%s status=%s", request_id, round((time.perf_counter() - started) * 1000), response.status_code)
    return result


def activate_agent(db: Session, payload: Any, request_id: str, ip_address: str | None) -> dict[str, Any]:
    total_started = time.perf_counter()
    cnpj = normalize_cnpj(payload.company_cnpj)
    license_started = time.perf_counter()
    validate_license_control(payload.license_api_key, cnpj, request_id)
    logger.info("agent.activation.stage request_id=%s stage=license_control duration_ms=%s", request_id, round((time.perf_counter() - license_started) * 1000))

    tenant_started = time.perf_counter()
    tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj).first()
    if not tenant:
        raise ActivationError("COMPANY_NOT_FOUND", "Empresa ainda nao foi sincronizada com o PIGO.", 404)
    allowed, message = validate_tenant_access(tenant)
    if not allowed:
        code = "LICENSE_EXPIRED" if "expirada" in message.lower() else "PIGO_ACCESS_DENIED"
        raise ActivationError(code, "Acesso ao PIGO nao autorizado.")

    company = db.query(Company).filter(Company.cnpj == cnpj).first()
    if not company:
        raise ActivationError("COMPANY_NOT_FOUND", "Empresa local nao encontrada.", 404)
    logger.info("agent.activation.stage request_id=%s stage=tenant_resolution duration_ms=%s", request_id, round((time.perf_counter() - tenant_started) * 1000))

    installation = (
        db.query(AgentInstallation)
        .filter(AgentInstallation.installation_id == payload.installation_id)
        .first()
    )
    if installation and installation.tenant_id != tenant.id:
        raise ActivationError("TENANT_CONFLICT", "Instalacao vinculada a outro tenant.", 409)
    if installation and installation.status == "BLOCKED":
        raise ActivationError("INSTALLATION_BLOCKED", "Instalacao bloqueada.")
    if installation and installation.status == "REVOKED" and not payload.reactivate:
        raise ActivationError("INSTALLATION_BLOCKED", "Instalacao revogada; use reativacao.")
    if installation and installation.machine_fingerprint != payload.machine_fingerprint:
        raise ActivationError("TENANT_CONFLICT", "Identidade da maquina nao corresponde a instalacao.", 409)

    if not tenant.api_token or not tenant.api_token_active or payload.reactivate:
        tenant.api_token = uuid.uuid4()
        tenant.api_token_active = True
        tenant.api_token_created_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    if not installation:
        installation = AgentInstallation(
            tenant_id=tenant.id,
            company_id=company.id,
            installation_id=payload.installation_id,
            machine_name=payload.machine_name,
            machine_fingerprint=payload.machine_fingerprint,
            agent_version=payload.agent_version,
            status="ACTIVE",
            activated_at=now,
        )
        db.add(installation)
        action = "agent.installation_activated"
    else:
        installation.machine_name = payload.machine_name
        installation.agent_version = payload.agent_version
        installation.status = "ACTIVE"
        installation.revoked_at = None
        installation.activated_at = now
        action = "agent.installation_reactivated" if payload.reactivate else "agent.installation_confirmed"

    installation.last_seen_at = now
    write_audit_log(
        db,
        action=action,
        entity_type="agent_installation",
        entity_id=payload.installation_id,
        metadata={
            "tenant_id": str(tenant.id),
            "company_id": str(company.id),
            "agent_version": payload.agent_version,
            "request_id": request_id,
            "ip_address": ip_address,
        },
    )
    persistence_started = time.perf_counter()
    db.commit()
    logger.info("agent.activation.stage request_id=%s stage=persistence duration_ms=%s total_ms=%s", request_id, round((time.perf_counter() - persistence_started) * 1000), round((time.perf_counter() - total_started) * 1000))
    return {
        "remote_sync_token": str(tenant.api_token),
        "tenant_id": str(tenant.id),
        "company_id": str(company.id),
        "activated_at": installation.activated_at.isoformat(),
    }
