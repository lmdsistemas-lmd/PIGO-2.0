from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)


def normalize_cnpj(value: str) -> str:
    cnpj = re.sub(r"\D", "", str(value or ""))
    if len(cnpj) != 14:
        raise ValueError("CNPJ invalido")
    return cnpj


def _default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=365)


def _token_is_active(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return bool(row.get("api_token")) and bool(row.get("api_token_active"))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y", "sim", "s"}


def _clean_text(value: Any) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _is_generic_company_name(value: str | None, cnpj: str) -> bool:
    if not value:
        return True

    normalized = re.sub(r"\s+", " ", value).strip().lower()
    digits = re.sub(r"\D", "", normalized)
    generic_values = {
        "",
        "nome da empresa",
        "nome fantasia",
        "razao social",
        "razão social",
        "cliente licenca p.i.g.o",
        "cliente licença p.i.g.o",
        "cliente p.i.g.o",
        "empresa p.i.g.o teste",
        "empresa pigo teste",
        f"empresa {cnpj}",
        f"empresa license control {cnpj}",
    }
    return (
        normalized in generic_values
        or normalized.startswith("empresa license control")
        or normalized.startswith("cliente licenca")
        or normalized.startswith("cliente licença")
        or normalized.startswith("empresa p.i.g.o teste")
        or digits == cnpj
    )


def _valid_company_text(value: str | None, cnpj: str) -> str | None:
    cleaned = _clean_text(value)
    if _is_generic_company_name(cleaned, cnpj):
        return None
    return cleaned


def _parse_expires_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("expires_at invalido") from exc
    return _default_expires_at()


def _normalize_license_status(value: Any) -> str:
    status = str(value or "unknown").strip().lower()
    allowed = {
        "active",
        "valid",
        "trial",
        "inactive",
        "blocked",
        "suspended",
        "expired",
        "revoked",
        "cancelled",
        "canceled",
        "unknown",
    }
    if status not in allowed:
        raise ValueError(f"license_status invalido: {status}")
    return status


def _normalize_environment(value: Any) -> str:
    environment = str(value or "production").strip().lower()
    aliases = {"prod": "production", "homolog": "homologation", "dev": "development"}
    environment = aliases.get(environment, environment)
    allowed = {"production", "homologation", "staging", "development", "test"}
    if environment not in allowed:
        raise ValueError(f"environment invalido: {environment}")
    return environment


def _masked_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked = dict(payload or {})
    for key in ["api_token", "token", "secret", "password", "senha", "license_key"]:
        if key in masked and masked[key]:
            value = str(masked[key])
            masked[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
    return masked


def sync_license_control_tenant(
    db: Session,
    payload: dict[str, Any],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    logger.info(
        "License Control sync payload recebido: %s",
        _masked_payload(payload),
    )

    cnpj = normalize_cnpj(payload.get("cnpj"))
    incoming_razao_social = _valid_company_text(
        payload.get("razao_social")
        or payload.get("legal_name")
        or payload.get("name"),
        cnpj,
    )
    incoming_nome_fantasia = _valid_company_text(
        payload.get("nome_fantasia") or payload.get("trade_name"),
        cnpj,
    )
    license_status = _normalize_license_status(payload.get("license_status"))
    has_pigo_access = _as_bool(payload.get("has_pigo_access"))
    environment = _normalize_environment(payload.get("environment"))
    product_slug = str(
        payload.get("project_slug")
        or payload.get("product_slug")
        or payload.get("license_project_slug")
        or "p-i-g-o-dashboard"
    ).strip()
    license_control_id = _clean_text(
        payload.get("license_control_id")
        or payload.get("license_id")
        or payload.get("id")
    )
    if not license_control_id:
        raise ValueError("license_control_id obrigatorio")

    email = _clean_text(payload.get("email")) or "license-control@pigo.local"
    telefone = _clean_text(payload.get("telefone") or payload.get("phone"))
    responsavel = _clean_text(payload.get("responsavel") or payload.get("responsible"))
    expires_at = payload.get("expires_at") or payload.get("license_expires_at")
    expires_at = _parse_expires_at(expires_at)

    status = "ATIVO" if has_pigo_access and license_status in {"active", "trial", "valid"} else "INATIVO"

    existing_company = db.execute(
        text(
            """
            SELECT name, legal_name, email, phone
            FROM companies
            WHERE cnpj = :cnpj
            """
        ),
        {"cnpj": cnpj},
    ).mappings().first()

    tenant_before = db.execute(
        text(
            """
            SELECT
                id,
                cnpj,
                razao_social,
                nome_fantasia,
                email,
                telefone,
                responsavel,
                api_token,
                api_token_active,
                api_token_created_at
            FROM tenants
            WHERE cnpj = :cnpj
            """
        ),
        {"cnpj": cnpj},
    ).mappings().first()

    if not incoming_razao_social and not tenant_before:
        raise ValueError("razao_social real obrigatoria para criar tenant")

    razao_social = (
        incoming_razao_social
        or (tenant_before["razao_social"] if tenant_before else None)
        or (existing_company["legal_name"] if existing_company else None)
        or f"Empresa {cnpj}"
    )
    nome_fantasia = (
        incoming_nome_fantasia
        or (tenant_before["nome_fantasia"] if tenant_before else None)
        or (existing_company["name"] if existing_company else None)
    )
    company_name = nome_fantasia or razao_social
    company_legal_name = razao_social

    company = db.execute(
        text(
            """
            INSERT INTO companies (name, legal_name, cnpj, email, phone, status, metadata, updated_at)
            VALUES (:name, :legal_name, :cnpj, :email, :phone, :status, :metadata, now())
            ON CONFLICT (cnpj)
            DO UPDATE SET
                name = CASE
                    WHEN EXCLUDED.name IS NOT NULL AND btrim(EXCLUDED.name) <> ''
                    THEN EXCLUDED.name
                    ELSE companies.name
                END,
                legal_name = CASE
                    WHEN EXCLUDED.legal_name IS NOT NULL AND btrim(EXCLUDED.legal_name) <> ''
                    THEN EXCLUDED.legal_name
                    ELSE companies.legal_name
                END,
                email = COALESCE(EXCLUDED.email, companies.email),
                phone = COALESCE(EXCLUDED.phone, companies.phone),
                status = EXCLUDED.status,
                metadata = companies.metadata || EXCLUDED.metadata,
                updated_at = now()
            RETURNING id
            """
        ),
        {
            "name": company_name,
            "legal_name": company_legal_name,
            "cnpj": cnpj,
            "email": email,
            "phone": telefone,
            "status": "active" if has_pigo_access else "inactive",
            "metadata": {
                "source": "license_control",
                "license_control_id": license_control_id,
                "has_pigo_access": has_pigo_access,
                "license_status": license_status,
                "product_slug": product_slug,
                "environment": environment,
            },
        },
    ).mappings().first()

    created = tenant_before is None
    api_token_created = False
    token_revoked = False
    tenant_id = tenant_before["id"] if tenant_before else uuid.uuid4()
    api_token = tenant_before["api_token"] if tenant_before else None
    api_token_active = bool(tenant_before["api_token_active"]) if tenant_before else False

    if has_pigo_access and not _token_is_active(tenant_before):
        api_token = uuid.uuid4()
        api_token_active = True
        api_token_created = True
    elif not has_pigo_access and api_token_active:
        api_token_active = False
        token_revoked = True

    api_token_created_at = datetime.now(timezone.utc) if api_token_created else None

    tenant = db.execute(
        text(
            """
            INSERT INTO tenants (
                id,
                cnpj,
                razao_social,
                nome_fantasia,
                email,
                telefone,
                responsavel,
                status,
                plano,
                data_vencimento,
                api_token,
                api_token_active,
                api_token_created_at,
                license_status,
                has_pigo_access,
                license_expires_at,
                license_control_id,
                product_slug,
                environment
            )
            VALUES (
                :id,
                :cnpj,
                :razao_social,
                :nome_fantasia,
                :email,
                :telefone,
                :responsavel,
                :status,
                :plano,
                :data_vencimento,
                :api_token,
                :api_token_active,
                :api_token_created_at,
                :license_status,
                :has_pigo_access,
                :license_expires_at,
                :license_control_id,
                :product_slug,
                :environment
            )
            ON CONFLICT (cnpj)
            DO UPDATE SET
                razao_social = EXCLUDED.razao_social,
                nome_fantasia = EXCLUDED.nome_fantasia,
                email = COALESCE(EXCLUDED.email, tenants.email),
                telefone = COALESCE(EXCLUDED.telefone, tenants.telefone),
                responsavel = COALESCE(EXCLUDED.responsavel, tenants.responsavel),
                status = EXCLUDED.status,
                plano = EXCLUDED.plano,
                data_vencimento = EXCLUDED.data_vencimento,
                api_token = EXCLUDED.api_token,
                api_token_active = EXCLUDED.api_token_active,
                api_token_created_at = CASE
                    WHEN tenants.api_token IS DISTINCT FROM EXCLUDED.api_token
                    THEN EXCLUDED.api_token_created_at
                    ELSE tenants.api_token_created_at
                END,
                license_status = EXCLUDED.license_status,
                has_pigo_access = EXCLUDED.has_pigo_access,
                license_expires_at = EXCLUDED.license_expires_at,
                license_control_id = EXCLUDED.license_control_id,
                product_slug = EXCLUDED.product_slug,
                environment = EXCLUDED.environment,
                updated_at = now()
            RETURNING
                id,
                cnpj,
                razao_social,
                nome_fantasia,
                status,
                api_token,
                api_token_active,
                api_token_created_at,
                api_token_last_used_at,
                license_status,
                has_pigo_access,
                license_expires_at,
                license_control_id,
                product_slug,
                environment,
                updated_at
            """
        ),
        {
            "id": tenant_id,
            "cnpj": cnpj,
            "razao_social": razao_social,
            "nome_fantasia": nome_fantasia,
            "email": email,
            "telefone": telefone,
            "responsavel": responsavel,
            "status": status,
            "plano": product_slug,
            "data_vencimento": expires_at,
            "api_token": api_token,
            "api_token_active": api_token_active,
            "api_token_created_at": api_token_created_at,
            "license_status": license_status,
            "has_pigo_access": has_pigo_access,
            "license_expires_at": expires_at,
            "license_control_id": license_control_id,
            "product_slug": product_slug,
            "environment": environment,
        },
    ).mappings().first()

    action = "license_control.tenant_created" if created else "license_control.tenant_updated"
    write_audit_log(
        db,
        action=action,
        company_id=company["id"] if company else None,
        entity_type="tenant",
        entity_id=str(tenant["id"]),
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "cnpj": cnpj,
            "license_control_id": license_control_id,
            "has_pigo_access": has_pigo_access,
            "license_status": license_status,
            "api_token_created": api_token_created,
            "token_revoked": token_revoked,
        },
    )

    if api_token_created:
        write_audit_log(
            db,
            action="license_control.api_token_generated",
            company_id=company["id"] if company else None,
            entity_type="tenant",
            entity_id=str(tenant["id"]),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"cnpj": cnpj, "license_control_id": license_control_id},
        )

    if token_revoked:
        write_audit_log(
            db,
            action="license_control.api_token_deactivated",
            company_id=company["id"] if company else None,
            entity_type="tenant",
            entity_id=str(tenant["id"]),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"cnpj": cnpj, "license_control_id": license_control_id},
        )

    result = {
        "success": True,
        "created": created,
        "updated": not created,
        "api_token_created": api_token_created,
        "tenant_id": str(tenant["id"]),
        "cnpj": tenant["cnpj"],
        "has_pigo_access": bool(tenant["has_pigo_access"]),
        "license_status": tenant["license_status"],
        "api_token": str(tenant["api_token"]) if tenant["api_token"] else None,
        "api_token_active": bool(tenant["api_token_active"]),
        "api_token_created_at": tenant["api_token_created_at"].isoformat() if tenant["api_token_created_at"] else None,
        "api_token_last_used_at": tenant["api_token_last_used_at"].isoformat() if tenant["api_token_last_used_at"] else None,
        "expires_at": tenant["license_expires_at"].isoformat() if tenant["license_expires_at"] else None,
        "license_control_id": tenant["license_control_id"],
        "product_slug": tenant["product_slug"],
        "environment": tenant["environment"],
        "updated_at": tenant["updated_at"].isoformat() if tenant["updated_at"] else None,
    }
    logger.info(
        "License Control sync upsert concluido: tenant_id=%s cnpj=%s has_pigo_access=%s "
        "license_status=%s api_token_created=%s api_token_active=%s razao_social=%s nome_fantasia=%s",
        result["tenant_id"],
        result["cnpj"],
        result["has_pigo_access"],
        result["license_status"],
        result["api_token_created"],
        result["api_token_active"],
        tenant["razao_social"],
        tenant["nome_fantasia"],
    )
    return result
