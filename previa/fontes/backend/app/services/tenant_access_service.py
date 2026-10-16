from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.models.saas import Tenant


ACTIVE_LICENSE_STATUSES = {"active", "valid", "trial"}


def normalize_cnpj(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def get_tenant_by_cnpj(db: Session, cnpj: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.cnpj == normalize_cnpj(cnpj)).first()


def get_tenant_by_api_token(db: Session, api_token: str) -> Tenant | None:
    token = str(api_token or "").strip()
    if not token:
        return None

    return (
        db.query(Tenant)
        .filter(cast(Tenant.api_token, String) == token)
        .filter(Tenant.api_token_active.is_(True))
        .first()
    )


def validate_tenant_access(tenant: Tenant | None) -> Tuple[bool, str]:
    if not tenant:
        return False, "Empresa nao sincronizada pelo License Control"

    if str(tenant.status or "").upper() != "ATIVO":
        return False, "Empresa inativa ou bloqueada pelo License Control"

    if not tenant.has_pigo_access:
        return False, "Empresa sem acesso ao P.I.G.O. no License Control"

    license_status = str(tenant.license_status or "").strip().lower()
    if license_status not in ACTIVE_LICENSE_STATUSES:
        return False, "Licenca sem status ativo no License Control"

    expires_at = tenant.license_expires_at or tenant.data_vencimento
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return False, "Licenca expirada no License Control"

    return True, "Acesso liberado pelo License Control"
