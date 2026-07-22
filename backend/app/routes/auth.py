import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, text
from sqlalchemy.exc import DBAPIError, TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token
from app.database.connection import get_db
from app.models.saas import SyncErpUser, Tenant
from app.services.audit_service import write_audit_log
from app.services.tenant_access_service import get_tenant_by_cnpj, validate_tenant_access


router = APIRouter(prefix="/auth", tags=["Autenticacao"])
logger = logging.getLogger("pigo.auth")


def _login_stage(request: Request, stage: str, started_at: float, **context) -> None:
    logger.info(
        "%s request_id=%s duration_ms=%s %s",
        stage,
        getattr(request.state, "trace_id", ""),
        round((time.perf_counter() - started_at) * 1000, 2),
        " ".join(f"{key}={value}" for key, value in context.items()),
    )


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _only_digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _is_admin_flag(value) -> bool:
    return str(value or "").strip().upper() in {"S", "SIM", "TRUE", "1", "Y"}


def _password_matches(stored_password, typed_password: str) -> bool:
    if stored_password is None:
        return False
    return str(stored_password).strip().upper() == str(typed_password or "").strip().upper()


def _tenant_display_name(tenant: Tenant) -> str:
    return tenant.nome_fantasia or tenant.razao_social or tenant.cnpj


def _find_synced_erp_user(db: Session, tenant: Tenant, login_value: str):
    erp_user = (
        db.query(SyncErpUser)
        .filter(
            SyncErpUser.tenant_id == tenant.id,
            func.upper(SyncErpUser.usu_login) == login_value.upper(),
        )
        .first()
    )
    if erp_user:
        return {
            "id": erp_user.usu_login,
            "login": erp_user.usu_login,
            "nome": erp_user.usu_nome or erp_user.usu_login,
            "senha": erp_user.usu_senha,
            "administrador": erp_user.usu_administrador,
            "source": "sync_erp_users",
        }

    exists = db.execute(
        text(
            """
            SELECT to_regclass('public."TB_USUARIO"') IS NOT NULL
            """
        )
    ).scalar()
    if not exists:
        return None

    row = (
        db.execute(
            text(
                """
                SELECT *
                FROM public."TB_USUARIO"
                WHERE tenant_id = :tenant_id
                  AND UPPER(TRIM(COALESCE("USU_LOGIN", ''))) = UPPER(:login)
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant.id), "login": login_value},
        )
        .mappings()
        .first()
    )
    if not row:
        return None

    return {
        "id": row.get("USU_ID") or row.get("USU_LOGIN"),
        "login": row.get("USU_LOGIN"),
        "nome": row.get("USU_NOME") or row.get("USU_LOGIN"),
        "senha": row.get("USU_SENHA"),
        "administrador": row.get("USU_ADMINISTRADOR") or row.get("USU_ADM") or "S",
        "source": "TB_USUARIO",
    }


@router.post("/login")
def login(payload: dict, request: Request, db: Session = Depends(get_db)):
    started_at = time.perf_counter()
    _login_stage(request, "login.request.received", started_at)
    _login_stage(request, "login.validation.started", started_at)
    cnpj_value = _only_digits(payload.get("cnpj") or payload.get("license_cnpj") or "")
    login_value = str(payload.get("login") or payload.get("email") or "").strip()
    password = str(payload.get("senha") or payload.get("password") or "").strip()

    if not cnpj_value or not login_value or not password:
        _login_stage(request, "login.response.sent", started_at, status=400, code="INVALID_LOGIN_PAYLOAD")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CNPJ, login e senha do ERP sao obrigatorios",
        )

    _login_stage(request, "login.database.started", started_at, operation="tenant_lookup")
    try:
        tenant = get_tenant_by_cnpj(db, cnpj_value)
    except (SQLAlchemyTimeoutError, DBAPIError) as exc:
        db.rollback()
        logger.error(
            "login.database.failed request_id=%s duration_ms=%s error_type=%s",
            getattr(request.state, "trace_id", ""),
            round((time.perf_counter() - started_at) * 1000, 2),
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_DATABASE_UNAVAILABLE", "message": "Serviço de autenticação temporariamente indisponível."},
        ) from exc
    _login_stage(request, "login.database.finished", started_at, operation="tenant_lookup", found=bool(tenant))
    if not tenant:
        write_audit_log(
            db,
            action="auth.login_failed_tenant_not_found",
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata={"login": login_value, "cnpj": cnpj_value, "source": "license_control"},
        )
        db.commit()
        _login_stage(request, "login.authentication.finished", started_at, success=False, code="TENANT_NOT_FOUND")
        _login_stage(request, "login.response.sent", started_at, status=403)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa nao sincronizada pelo License Control")

    access_ok, access_message = validate_tenant_access(tenant)
    if not access_ok:
        write_audit_log(
            db,
            action="auth.login_blocked_by_license_control",
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata={
                "login": login_value,
                "cnpj": cnpj_value,
                "tenant_id": str(tenant.id),
                "status": tenant.status,
                "license_status": tenant.license_status,
                "has_pigo_access": tenant.has_pigo_access,
                "reason": access_message,
            },
        )
        db.commit()
        _login_stage(request, "login.authentication.finished", started_at, success=False, code="LICENSE_BLOCKED")
        _login_stage(request, "login.response.sent", started_at, status=403)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=access_message)

    _login_stage(request, "login.database.started", started_at, operation="user_lookup")
    try:
        erp_user = _find_synced_erp_user(db, tenant, login_value)
    except (SQLAlchemyTimeoutError, DBAPIError) as exc:
        db.rollback()
        logger.error(
            "login.database.failed request_id=%s duration_ms=%s error_type=%s",
            getattr(request.state, "trace_id", ""),
            round((time.perf_counter() - started_at) * 1000, 2),
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_DATABASE_UNAVAILABLE", "message": "Serviço de autenticação temporariamente indisponível."},
        ) from exc
    _login_stage(request, "login.database.finished", started_at, operation="user_lookup", found=bool(erp_user))
    if not erp_user or not _password_matches(erp_user["senha"], password):
        write_audit_log(
            db,
            action="auth.erp_login_failed",
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata={"login": login_value, "cnpj": cnpj_value},
        )
        db.commit()
        _login_stage(request, "login.authentication.finished", started_at, success=False, code="INVALID_CREDENTIALS")
        _login_stage(request, "login.response.sent", started_at, status=401)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario ou senha invalidos no ERP")

    if not _is_admin_flag(erp_user["administrador"]):
        write_audit_log(
            db,
            action="auth.erp_login_blocked_not_admin",
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata={"login": login_value, "cnpj": cnpj_value},
        )
        db.commit()
        _login_stage(request, "login.authentication.finished", started_at, success=False, code="ADMIN_REQUIRED")
        _login_stage(request, "login.response.sent", started_at, status=403)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sem permissao administrativa no ERP")

    write_audit_log(
        db,
        action="auth.erp_login_success",
        company_id=None,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        metadata={
            "login": erp_user["login"],
            "cnpj": cnpj_value,
            "tenant_id": str(tenant.id),
            "source": erp_user["source"],
        },
    )
    db.commit()

    access_token = create_access_token(
        {
            "sub": str(erp_user["id"]),
            "login": erp_user["login"],
            "nome": erp_user["nome"],
            "perfil": "Administrador ERP",
            "role": "erp-admin",
            "cnpj": cnpj_value,
            "tenant_id": str(tenant.id),
            "empresa": _tenant_display_name(tenant),
        }
    )

    _login_stage(request, "login.authentication.finished", started_at, success=True)
    _login_stage(request, "login.response.sent", started_at, status=200)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(erp_user["id"]),
            "login": erp_user["login"],
            "nome": erp_user["nome"],
            "perfil": "Administrador ERP",
            "cnpj": cnpj_value,
            "empresa": _tenant_display_name(tenant),
        },
    }


@router.get("/me")
def me(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token nao informado")

    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)

    return {
        "id": payload["sub"],
        "login": payload.get("login"),
        "nome": payload.get("nome"),
        "perfil": payload.get("perfil") or payload.get("role"),
        "cnpj": payload.get("cnpj"),
        "tenant_id": payload.get("tenant_id"),
        "empresa": payload.get("empresa", "P.I.G.O Dashboard"),
    }


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token nao informado")

    token = authorization.replace("Bearer ", "").strip()
    try:
        return decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao invalida ou expirada")
