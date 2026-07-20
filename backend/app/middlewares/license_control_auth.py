import hmac
import logging

from fastapi import Header, HTTPException, Request, status

from app.core import config


logger = logging.getLogger(__name__)

INTERNAL_LICENSE_CONTROL_PATHS = frozenset(
    {
        "/api/internal/license-control/tenants/sync",
        "/api/internal/license-control/sync-tenant",
    }
)


def is_license_control_integration_path(path: str) -> bool:
    return path.rstrip("/") in INTERNAL_LICENSE_CONTROL_PATHS


def validate_license_control_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_integration_source: str | None = Header(default=None, alias="X-Integration-Source"),
) -> None:
    expected = str(config.LICENSE_CONTROL_INTEGRATION_TOKEN or "").strip()
    if not expected:
        logger.critical(
            "LICENSE_CONTROL_INTEGRATION_TOKEN ausente; sincronizacao bloqueada."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integracao com License Control nao configurada.",
        )

    scheme, separator, provided = (authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(provided.strip())
        and hmac.compare_digest(provided.strip(), expected)
    )
    if not valid:
        logger.warning("Token ausente ou invalido na integracao License Control.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de integracao ausente ou invalido.",
        )

    if x_integration_source and x_integration_source.lower() != "license-control":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Origem da integracao invalida.",
        )

    request.state.auth_type = "integration"
    request.state.integration_source = "license-control"
