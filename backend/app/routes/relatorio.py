from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Body, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db
from app.services.relatorios_service import RelatoriosService

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


def get_relatorios_service(db: Session = Depends(get_erp_db)) -> RelatoriosService:
    return RelatoriosService(db)


@router.get("/categoria/{categoria}")
def listar_relatorios(
    categoria: str,
    service: RelatoriosService = Depends(get_relatorios_service),
):
    return service.listar_relatorios(categoria)


@router.get("/{cdarquivo}/inspecionar")
def inspecionar_relatorio(
    cdarquivo: int,
    service: RelatoriosService = Depends(get_relatorios_service),
):
    return service.inspecionar_relatorio(cdarquivo)


@router.get("/{cdarquivo}/xml", response_class=PlainTextResponse)
def obter_xml_relatorio(
    cdarquivo: int,
    service: RelatoriosService = Depends(get_relatorios_service),
):
    return service.obter_xml_bruto(cdarquivo)


@router.post("/{cdarquivo}/opcoes")
def opcoes_relatorio(
    cdarquivo: int,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    service: RelatoriosService = Depends(get_relatorios_service),
):
    return service.opcoes_relatorio(cdarquivo, payload or {})


@router.post("/{cdarquivo}/preview")
def preview_relatorio(
    cdarquivo: int,
    payload: Dict[str, Any] = Body(...),
    limit: int = Query(200, ge=1, le=5000),
    service: RelatoriosService = Depends(get_relatorios_service),
):
    return service.preview_relatorio(cdarquivo, payload, limit=limit)