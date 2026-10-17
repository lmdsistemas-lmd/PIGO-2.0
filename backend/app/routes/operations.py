import csv
from datetime import date
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from openpyxl import Workbook
from typing import Literal
from sqlalchemy import text

from app.database.connection import get_db
from app.routes.auth import get_current_user
from app.routes.commercial_analytics import tenant
from app.ai.validators.permission_validator import ReportPermissionValidator
from app.services.operations_service import OperationsService, SOURCES
from app.services.cash_export_service import export_closing

router = APIRouter(prefix="/operacoes", tags=["Consultas operacionais"])


def service_for(resource, db, user):
    if resource not in SOURCES:
        raise HTTPException(404, "Consulta não encontrada.")
    if SOURCES[resource]["group"] == "Financeiro":
        try:
            ReportPermissionValidator().validate("finance", user)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
    return OperationsService(db, tenant(user))


@router.get("/fluxo-caixa")
def forecast(empresa_id: int = Query(gt=0), start: date = Query(...), end: date = Query(...),
             db=Depends(get_db), user=Depends(get_current_user)):
    service = service_for("receber", db, user)
    try:
        return service.forecast(empresa_id, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{resource}")
def listing(resource: str, empresa_id: int = Query(gt=0), search: str = Query("", max_length=200),
            status: str = "", start: date | None = None, end: date | None = None,
            page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
            sort: str | None = None, direction: Literal["asc", "desc"] = "asc",
            db=Depends(get_db), user=Depends(get_current_user)):
    try:
        result = service_for(resource, db, user).list(resource, empresa_id, search, status, start, end, page, page_size, sort, direction)
        result["last_sync_at"] = db.execute(text("""SELECT MAX(finished_at) FROM sync_jobs
            WHERE tenant_id=:tenant AND table_name=:table AND status='COMPLETED'"""),
            {"tenant": tenant(user), "table": SOURCES[resource]["table"]}).scalar()
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def spreadsheet_value(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/{resource}/export")
def export(resource: str, empresa_id: int = Query(gt=0), search: str = "", status: str = "",
           start: date | None = None, end: date | None = None, format: Literal["csv", "excel"] = "csv",
           db=Depends(get_db), user=Depends(get_current_user)):
    try:
        result = service_for(resource, db, user).list(resource, empresa_id, search, status, start, end, export=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not result["available"]:
        raise HTTPException(409, "Dados ainda não sincronizados.")
    if result["total"] > 10000:
        raise HTTPException(422, "Refine os filtros para exportar até 10.000 registros.")
    rows = [[column["label"] for column in result["columns"]]]
    rows += [[spreadsheet_value(row.get(column["key"])) for column in result["columns"]] for row in result["rows"]]
    if format == "excel":
        book = Workbook(); sheet = book.active; sheet.title = "Consulta"
        for row in rows:
            sheet.append(row)
        stream = BytesIO(); book.save(stream)
        return Response(stream.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{resource}.xlsx"'})
    stream = StringIO(); writer = csv.writer(stream, delimiter=";"); writer.writerows(rows)
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{resource}.csv"'})


@router.get('/fechamentos/{record_id}/export')
def export_cash_closing(record_id: str, empresa_id: int = Query(gt=0),
        tab: Literal['financeiro','vendas','produtos','recebimentos','pagamentos','sangrias','suprimentos','canceladas'] = 'financeiro',
        format: Literal['excel','pdf'] = 'excel', db=Depends(get_db), user=Depends(get_current_user)):
    try:
        data=service_for('fechamentos',db,user).detail('fechamentos',empresa_id,record_id)
        body,media_type,extension=export_closing(data,record_id,tab,format)
        return Response(body,media_type=media_type,headers={'Content-Disposition':f'attachment; filename="fechamento-{record_id}-{tab}.{extension}"'})
    except LookupError as exc:
        raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get("/{resource}/{record_id}")
def detail(resource: str, record_id: str, empresa_id: int = Query(gt=0), db=Depends(get_db), user=Depends(get_current_user)):
    try:
        return service_for(resource, db, user).detail(resource, empresa_id, record_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
