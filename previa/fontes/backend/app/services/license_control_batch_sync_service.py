import json
import ipaddress
import logging
import re
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.license_control_repository import LicenseControlRepository
from app.schemas.license_control_sync import LicenseControlTenant


logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"active", "valid", "trial"}
ALLOWED_STATUSES = ACTIVE_STATUSES | {
    "inactive",
    "blocked",
    "suspended",
    "expired",
    "revoked",
    "cancelled",
    "canceled",
    "unknown",
}


def normalize_cnpj(value: str) -> str:
    normalized = re.sub(r"\D", "", value or "")
    if len(normalized) != 14:
        raise ValueError("cnpj deve conter 14 digitos")
    return normalized


def _mask_cnpj(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 14:
        return None
    return f"{digits[:2]}.***.***/****-{digits[-2:]}"


def _identity(item: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(item, dict):
        return None, None, None
    return (
        str(item.get("tenant_id") or "").strip() or None,
        str(item.get("company_id") or "").strip() or None,
        _mask_cnpj(item.get("cnpj")),
    )


def _error(
    index: int,
    item: Any,
    *,
    field: str,
    code: str,
    message: str,
    trace_id: str | None,
) -> dict[str, Any]:
    tenant_id, company_id, masked_cnpj = _identity(item)
    error = {
        "index": index,
        "tenant_id": tenant_id,
        "company_id": company_id,
        "field": field,
        "code": code,
        "message": message,
        "trace_id": trace_id,
    }
    logger.warning(
        "license_control.sync.record_rejected trace_id=%s tenant_id=%s "
        "company_id=%s cnpj=%s field=%s code=%s message=%s",
        trace_id,
        tenant_id,
        company_id,
        masked_cnpj,
        field,
        code,
        message,
    )
    return error


def _validation_error(
    index: int,
    item: Any,
    exc: ValidationError,
    trace_id: str | None,
) -> dict[str, Any]:
    issue = exc.errors()[0]
    field = str(issue.get("loc", ("payload",))[-1])
    issue_type = str(issue.get("type") or "")

    if issue_type == "missing":
        code = f"MISSING_{field.upper()}"
        message = f"Campo obrigatorio ausente: {field}."
    elif field in {"updated_at", "validade"}:
        code = f"INVALID_{field.upper()}"
        message = f"Data invalida no campo {field}."
    elif field in {"tenant_id", "company_id", "empresa", "produto", "status"}:
        code = f"EMPTY_{field.upper()}"
        message = f"Campo obrigatorio vazio: {field}."
    else:
        code = "INVALID_PAYLOAD"
        message = f"Valor invalido no campo {field}."

    return _error(
        index,
        item,
        field=field,
        code=code,
        message=message,
        trace_id=trace_id,
    )


def sync_license_control_batch(
    db: Session,
    raw_items: list[Any],
    ip_address: str | None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    repository = LicenseControlRepository(db)
    try:
        safe_ip_address = str(ipaddress.ip_address(ip_address)) if ip_address else None
    except ValueError:
        safe_ip_address = None
    metrics = {
        "received": len(raw_items),
        "created": 0,
        "updated": 0,
        "disabled": 0,
        "ignored": 0,
    }
    errors: list[dict[str, Any]] = []
    actions: list[str] = []

    for index, raw_item in enumerate(raw_items):
        try:
            item = LicenseControlTenant.model_validate(raw_item)
        except ValidationError as exc:
            errors.append(_validation_error(index, raw_item, exc, trace_id))
            continue

        try:
            cnpj = normalize_cnpj(item.cnpj)
        except ValueError:
            errors.append(
                _error(
                    index,
                    raw_item,
                    field="cnpj",
                    code="INVALID_CNPJ",
                    message="CNPJ invalido.",
                    trace_id=trace_id,
                )
            )
            continue

        status_value = item.status.strip().lower()
        if status_value not in ALLOWED_STATUSES:
            errors.append(
                _error(
                    index,
                    raw_item,
                    field="status",
                    code="INVALID_STATUS",
                    message="Status de licenca nao reconhecido.",
                    trace_id=trace_id,
                )
            )
            continue

        normalized_product = re.sub(r"[^A-Z0-9]", "", item.produto.upper())
        if normalized_product != "PIGO":
            errors.append(
                _error(
                    index,
                    raw_item,
                    field="produto",
                    code="INVALID_PRODUCT",
                    message="Produto diferente de PIGO.",
                    trace_id=trace_id,
                )
            )
            continue

        enabled = item.ativo and status_value in ACTIVE_STATUSES
        values = {
            "external_tenant_id": item.tenant_id,
            "external_company_id": item.company_id,
            "cnpj": cnpj,
            "razao_social": item.empresa,
            "nome_fantasia": item.nome_fantasia,
            "name": item.nome_fantasia or item.empresa,
            "legal_name": item.empresa,
            "produto": item.produto,
            "license_status": status_value,
            "has_pigo_access": enabled,
            "access_status": "ATIVO" if enabled else "INATIVO",
            "status": "active" if enabled else "inactive",
            "validade": item.validade,
            "source_updated_at": item.updated_at,
            "metadata": json.dumps(
                {
                    "source": "license_control",
                    "tenant_id": item.tenant_id,
                    "company_id": item.company_id,
                    "produto": item.produto,
                    "license_status": status_value,
                    "validade": item.validade.isoformat() if item.validade else None,
                    "source_updated_at": item.updated_at.isoformat(),
                }
            ),
        }

        try:
            with db.begin_nested():
                tenant = repository.find_tenant(item.tenant_id, cnpj)
                company = repository.find_company(item.company_id, cnpj)

                if tenant and tenant["external_tenant_id"] not in (None, item.tenant_id):
                    errors.append(
                        _error(
                            index,
                            raw_item,
                            field="tenant_id",
                            code="TENANT_CNPJ_CONFLICT",
                            message="CNPJ ja vinculado a outro tenant externo.",
                            trace_id=trace_id,
                        )
                    )
                    continue
                if company and company["external_company_id"] not in (None, item.company_id):
                    errors.append(
                        _error(
                            index,
                            raw_item,
                            field="company_id",
                            code="COMPANY_CNPJ_CONFLICT",
                            message="CNPJ ja vinculado a outra empresa externa.",
                            trace_id=trace_id,
                        )
                    )
                    continue

                repository.upsert_company(values, company["id"] if company else None)
                repository.upsert_tenant(values, tenant["id"] if tenant else None)

            action = "updated" if tenant else "created"
            actions.append(action)
            metrics[action] += 1
            if not enabled and (not tenant or bool(tenant["has_pigo_access"])):
                metrics["disabled"] += 1
        except IntegrityError:
            errors.append(
                _error(
                    index,
                    raw_item,
                    field="identifiers",
                    code="IDENTIFIER_CONFLICT",
                    message="Conflito entre tenant_id, company_id e CNPJ.",
                    trace_id=trace_id,
                )
            )
        except Exception:
            logger.exception(
                "license_control.sync.persistence_error trace_id=%s tenant_id=%s company_id=%s",
                trace_id,
                item.tenant_id,
                item.company_id,
            )
            errors.append(
                _error(
                    index,
                    raw_item,
                    field="record",
                    code="PERSISTENCE_ERROR",
                    message="Falha interna ao persistir o registro.",
                    trace_id=trace_id,
                )
            )

    duration = round((time.perf_counter() - started_at) * 1000)
    result = {
        "success": not errors,
        **metrics,
        "errors": errors,
        "processing_time": duration,
    }
    log_values = {
        **metrics,
        "failed": len(errors),
        "duration_ms": duration,
        "status": "success" if not errors else ("partial" if actions else "failed"),
        "message": (
            "Sincronizacao concluida."
            if not errors
            else f"Sincronizacao concluida com {len(errors)} falha(s)."
        ),
        "ip_address": safe_ip_address,
        "error_details": json.dumps(errors),
    }
    try:
        repository.write_sync_log(log_values)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if len(raw_items) == 1 and not errors:
        result["action"] = actions[0]
    return result
