import csv
from io import BytesIO, StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.erp_connection import current_tenant_id
from app.models.reporting import ReportExport, ReportRun
from app.routes.auth import get_current_user
from app.schemas.reporting import ReportDefinition, ReportExportInput, ReportPreviewInput, ReportTemplateInput
from app.services.relatorio_export_service import RelatorioExportService
from app.services.relatorio_pdf_service import RelatorioPdfService
from app.services.business_semantic_layer import BusinessSemanticLayer
from app.services.report_catalog import CATALOG, READY_TEMPLATES, ReportCatalog
from app.services.report_engine import ReportEngine, clear_report_cache
from app.services.report_template_service import ReportTemplateService

router = APIRouter(prefix="/reports", tags=["Report Engine"])


def _tenant():
    tenant_id = current_tenant_id.get()
    if not tenant_id:
        raise HTTPException(401, "Tenant autenticado não encontrado.")
    return str(tenant_id)


def _service(db, user):
    return ReportTemplateService(db, _tenant(), user)


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), user=Depends(get_current_user)):
    report_catalog = ReportCatalog()
    report_catalog.sync_metadata(db)
    return report_catalog.public_catalog()


@router.get("/semantics")
def semantics(user=Depends(get_current_user)):
    return BusinessSemanticLayer().public_dictionary(CATALOG)


@router.get("/catalog/{category}/{source}/filters/{filter_key}/options")
def filter_options(category: str, source: str, filter_key: str, empresa_id: int, search: str = "", user=Depends(get_current_user)):
    try:
        return ReportEngine().filter_options(category, source, filter_key, _tenant(), empresa_id, search)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/ready-templates")
def ready_templates(category: str | None = None, user=Depends(get_current_user)):
    return [item for item in READY_TEMPLATES if not category or item["definition"]["category"] == category]


@router.get("")
def list_reports(category: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _service(db, user).list(category)


@router.post("", status_code=201)
def create_report(payload: ReportTemplateInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        ReportEngine().builder.build(payload.definition, 1, 1)
        return _service(db, user).create(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/{template_id}")
def update_report(template_id: UUID, payload: ReportTemplateInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        ReportEngine().builder.build(payload.definition, 1, 1)
        result = _service(db, user).update(template_id, payload)
        clear_report_cache(_tenant())
        return result
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{template_id}/duplicate", status_code=201)
def duplicate_report(template_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try: return _service(db, user).duplicate(template_id)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc: raise HTTPException(403, str(exc)) from exc


@router.delete("/{template_id}", status_code=204)
def delete_report(template_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try: _service(db, user).delete(template_id)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc: raise HTTPException(403, str(exc)) from exc


@router.post("/preview")
def preview(payload: ReportPreviewInput, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    request_id = request.headers.get("x-request-id") or getattr(request.state, "trace_id", "")
    try:
        result = ReportEngine().execute(payload.definition, _tenant(), payload.empresa_id, payload.limit, request_id)
        db.add(ReportRun(tenant_id=UUID(_tenant()), company_erp_id=str(payload.empresa_id), requested_by=str(user.get("sub") or user.get("id")), status="SUCCESS", row_count=result["row_count"], duration_ms=round(result["query_time_ms"]), request_id=request_id))
        db.commit()
        return result
    except ValueError as exc:
        db.add(ReportRun(tenant_id=UUID(_tenant()), company_erp_id=str(payload.empresa_id), requested_by=str(user.get("sub") or user.get("id")), status="REJECTED", error_code="INVALID_REPORT_SCHEMA", request_id=request_id))
        db.commit()
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        db.rollback()
        db.add(ReportRun(tenant_id=UUID(_tenant()), company_erp_id=str(payload.empresa_id), requested_by=str(user.get("sub") or user.get("id")), status="ERROR", error_code="REPORT_EXECUTION_ERROR", request_id=request_id))
        db.commit()
        raise


@router.post("/export")
def export(payload: ReportExportInput, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = ReportEngine().execute(payload.definition, _tenant(), payload.empresa_id, 50, request.headers.get("x-request-id", ""))
    columns = [item["key"] for item in result["columns"]]
    report = {"nome": "Relatório PIGO", "colunas": columns, "linhas": result["rows"]}
    if payload.format == "pdf":
        content, media, suffix = RelatorioPdfService.gerar_pdf_bytes(report), "application/pdf", "pdf"
    elif payload.format == "excel":
        content, media, suffix = RelatorioExportService.gerar_excel_bytes(report), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        stream = StringIO(); writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(result["rows"])
        content, media, suffix = stream.getvalue().encode("utf-8-sig"), "text/csv", "csv"
    db.add(ReportExport(tenant_id=UUID(_tenant()), template_id=payload.template_id, requested_by=str(user.get("sub") or user.get("id")), format=payload.format, row_count=result["row_count"]))
    db.commit()
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="relatorio-pigo.{suffix}"'})
