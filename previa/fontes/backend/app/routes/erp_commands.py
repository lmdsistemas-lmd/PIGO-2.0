from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database.connection import get_db
from app.routes.auth import get_current_user
from app.routes.commercial_analytics import tenant
from app.routes.sync import sync_health
from app.services.erp_command_service import EDITABLE, ErpCommandService

router = APIRouter(tags=["Gravação no ERP"])


def administrator(user=Depends(get_current_user)):
    if str(user.get("role", "")).lower() not in {"admin", "administrator", "administrador", "erp-admin"}:
        raise HTTPException(403, "Somente administradores podem solicitar alterações no ERP.")
    return user


class CommandInput(BaseModel):
    request_id: UUID
    empresa_id: int = Field(gt=0)
    action: Literal["create", "update"]
    record_id: str | None = Field(default=None, max_length=100)
    payload: dict
    expected: dict = Field(default_factory=dict)


@router.get("/erp/cadastros/{resource}")
def commands(resource: str, empresa_id: int = Query(gt=0), db=Depends(get_db), user=Depends(administrator)):
    if resource not in EDITABLE:
        raise HTTPException(404, "Cadastro não editável.")
    agent = db.execute(text("SELECT resources,seen_at,(seen_at > now()-interval '10 minutes') AS online FROM erp_agent_capabilities WHERE tenant_id=:tenant"), {"tenant": tenant(user)}).mappings().first()
    return {"fields": EDITABLE[resource], "agent_ready": bool(agent and agent["online"] and resource in agent["resources"]),
            "agent_seen_at": agent["seen_at"] if agent else None,
            "commands": ErpCommandService(db, tenant(user)).list(empresa_id, resource)}


@router.post("/erp/cadastros/{resource}", status_code=202)
def enqueue(resource: str, payload: CommandInput, db=Depends(get_db), user=Depends(administrator)):
    try:
        return ErpCommandService(db, tenant(user)).enqueue(payload.request_id, payload.empresa_id, resource,
            payload.action, payload.record_id, payload.payload, payload.expected, str(user["sub"]))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


class ClaimInput(BaseModel):
    cnpj: str
    resources: list[str] = Field(default_factory=list, max_length=8)


def authenticated_agent(cnpj, authorization, db):
    # Same API token, tenant/CNPJ binding and LicenseControl gate as inbound sync.
    return sync_health(cnpj=cnpj, authorization=authorization, db=db)["tenant_id"]


@router.post("/sync/commands/claim")
def claim(payload: ClaimInput, authorization: str | None = Header(None), db=Depends(get_db)):
    return {"commands": ErpCommandService(db, authenticated_agent(payload.cnpj, authorization, db)).claim(payload.resources)}


class AckInput(BaseModel):
    cnpj: str
    lease_token: UUID
    status: Literal["applied", "rejected"]
    record_id: str | None = Field(default=None, max_length=100)
    message: str = Field(max_length=300)


@router.post("/sync/commands/{command_id}/ack")
def acknowledge(command_id: UUID, payload: AckInput, authorization: str | None = Header(None), db=Depends(get_db)):
    identity = authenticated_agent(payload.cnpj, authorization, db)
    if payload.status == "applied" and not payload.record_id:
        raise HTTPException(422, "A confirmação deve informar o código do ERP.")
    try:
        return ErpCommandService(db, identity).acknowledge(command_id, payload.lease_token, payload.status, payload.record_id, payload.message)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
