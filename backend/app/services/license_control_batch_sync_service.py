import json
import ipaddress
import re
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.license_control_repository import LicenseControlRepository
from app.schemas.license_control_sync import LicenseControlTenant


ACTIVE_STATUSES = {"active", "valid", "trial"}


def normalize_cnpj(value: str) -> str:
    normalized = re.sub(r"\D", "", value or "")
    if len(normalized) != 14:
        raise ValueError("cnpj deve conter 14 digitos")
    return normalized


def _error(index: int, item: Any, message: str) -> dict[str, Any]:
    reference = None
    if isinstance(item, dict):
        reference = item.get("company_id") or item.get("tenant_id")
    return {"index": index, "reference": reference, "message": message}


def sync_license_control_batch(
    db: Session,
    raw_items: list[Any],
    ip_address: str | None,
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
            cnpj = normalize_cnpj(item.cnpj)
        except (ValidationError, ValueError) as exc:
            errors.append(_error(index, raw_item, str(exc)))
            continue

        status_value = item.status.strip().lower()
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
                    raise ValueError("CNPJ ja vinculado a outro tenant externo")
                if company and company["external_company_id"] not in (None, item.company_id):
                    raise ValueError("CNPJ ja vinculado a outra empresa externa")

                repository.upsert_company(values, company["id"] if company else None)
                repository.upsert_tenant(values, tenant["id"] if tenant else None)

            action = "updated" if tenant else "created"
            actions.append(action)
            metrics[action] += 1
            if not enabled and (not tenant or bool(tenant["has_pigo_access"])):
                metrics["disabled"] += 1
        except (IntegrityError, ValueError) as exc:
            errors.append(_error(index, raw_item, str(exc).splitlines()[0][:300]))
        except Exception:
            errors.append(
                _error(index, raw_item, "Falha interna ao persistir o registro.")
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
