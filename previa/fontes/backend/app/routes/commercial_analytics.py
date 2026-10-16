from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.routes.auth import get_current_user
from app.services.commercial_analytics_service import CommercialAnalyticsService

router = APIRouter(prefix="/dashboard", tags=["Análises comerciais"])
Period = Literal["today", "yesterday", "week", "month", "previousMonth", "year", "custom"]


class GoalInput(BaseModel):
    empresa_id: int = Field(gt=0)
    mes: date
    vendedor_id: int = Field(default=0, ge=0)
    valor: Decimal = Field(gt=0, max_digits=18, decimal_places=2)

    @field_validator("mes")
    @classmethod
    def first_day(cls, value):
        if value.day != 1:
            raise ValueError("Use o primeiro dia do mês.")
        return value


def tenant(user):
    try:
        return str(UUID(str(user.get("tenant_id"))))
    except (TypeError, ValueError):
        raise HTTPException(401, "Tenant autenticado não encontrado.") from None


def admin(user):
    if str(user.get("role", "")).lower() not in {"erp-admin", "admin", "administrator"}:
        raise HTTPException(403, "Somente administradores podem alterar metas.")


@router.get("/clientes")
def customers(empresa_id: int = Query(gt=0), period: Period = "month",
              start: str | None = None, end: str | None = None, user=Depends(get_current_user)):
    tenant(user)
    try:
        return CommercialAnalyticsService().customers(empresa_id, period, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/curva-abc")
def abc(empresa_id: int = Query(gt=0), period: Period = "month",
        start: str | None = None, end: str | None = None, user=Depends(get_current_user)):
    tenant(user)
    try:
        return CommercialAnalyticsService().abc(empresa_id, period, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/metas")
def goals(empresa_id: int = Query(gt=0), mes: date = Query(...),
          db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant_id = tenant(user)
    start = mes.replace(day=1)
    end = start.replace(day=monthrange(start.year, start.month)[1])
    service = CommercialAnalyticsService()
    sales = service.sales(empresa_id, start, end, "seller")
    sellers = service.sellers(empresa_id)
    names = {str(row["CODIGO"]): row["NOME"] for row in sellers}
    by_seller = {str(row["CODIGO"]): row for row in sales}
    revenue = sum(float(row.get("VALOR") or 0) for row in sales)
    rows = db.execute(text("""
        SELECT id, seller_id, target FROM sales_goals
        WHERE tenant_id=:tenant AND company_erp_id=:company AND month=:month
        ORDER BY seller_id
    """), {"tenant": tenant_id, "company": empresa_id, "month": start}).mappings().all()
    today = date.today()
    elapsed = min(max((today - start).days + 1, 0), end.day)
    result = []
    for row in rows:
        seller = int(row["seller_id"])
        actual = revenue if seller == 0 else float(by_seller.get(str(seller), {}).get("VALOR") or 0)
        target = float(row["target"])
        result.append({"id": str(row["id"]), "vendedor_id": seller,
                       "responsavel": "Toda a empresa" if seller == 0 else names.get(str(seller)) or f"Vendedor {seller}",
                       "meta": target, "realizado": actual, "percentual": actual / target * 100,
                       "faltante": max(target - actual, 0),
                       "projecao": actual / elapsed * end.day if elapsed else 0})
    return {"mes": start, "metas": result,
            "vendedores": [{"id": row["CODIGO"], "nome": row["NOME"]} for row in sellers if row["CODIGO"] is not None],
            "faturamento": revenue}


@router.put("/metas")
def save_goal(payload: GoalInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    admin(user)
    tenant_id = tenant(user)
    service = CommercialAnalyticsService()
    company = service._fetch_one("SELECT E.EMP_ID FROM TB_EMPRESA E WHERE E.EMP_ID=:company",
                                 {"company": str(payload.empresa_id)})
    if not company:
        raise HTTPException(422, "Empresa não encontrada nos dados sincronizados.")
    if payload.vendedor_id and str(payload.vendedor_id) not in {str(row["CODIGO"]) for row in service.sellers(payload.empresa_id)}:
        raise HTTPException(422, "Vendedor sem vínculo com as vendas desta empresa.")
    db.execute(text("""
        INSERT INTO sales_goals (tenant_id, company_erp_id, month, seller_id, target, updated_by)
        VALUES (:tenant, :company, :month, :seller, :target, :user)
        ON CONFLICT (tenant_id, company_erp_id, month, seller_id)
        DO UPDATE SET target=EXCLUDED.target, updated_by=EXCLUDED.updated_by, updated_at=now()
    """), {"tenant": tenant_id, "company": payload.empresa_id, "month": payload.mes,
            "seller": payload.vendedor_id, "target": payload.valor, "user": str(user["sub"])})
    db.commit()
    return {"success": True}


@router.delete("/metas/{goal_id}", status_code=204)
def delete_goal(goal_id: UUID, empresa_id: int = Query(gt=0),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    admin(user)
    result = db.execute(text("""
        DELETE FROM sales_goals WHERE id=:id AND tenant_id=:tenant AND company_erp_id=:company
        RETURNING id
    """), {"id": str(goal_id), "tenant": tenant(user), "company": empresa_id}).first()
    if not result:
        db.rollback()
        raise HTTPException(404, "Meta não encontrada.")
    db.commit()
