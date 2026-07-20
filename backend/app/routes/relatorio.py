from fastapi import APIRouter, Depends, HTTPException, status

from app.routes.auth import get_current_user


router = APIRouter(prefix="/relatorios", tags=["Relatorios"])


def _relatorios_desativados():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Modulo de relatorios em desenvolvimento. Execucao de SQL de relatorios "
            "esta desativada ate a camada multi-tenant ser reimplementada."
        ),
    )


@router.get("/categoria/{categoria}")
def listar_relatorios(categoria: str, current_user: dict = Depends(get_current_user)):
    _relatorios_desativados()


@router.get("/{cdarquivo}/inspecionar")
def inspecionar_relatorio(cdarquivo: int, current_user: dict = Depends(get_current_user)):
    _relatorios_desativados()


@router.get("/{cdarquivo}/xml")
def obter_xml_relatorio(cdarquivo: int, current_user: dict = Depends(get_current_user)):
    _relatorios_desativados()


@router.post("/{cdarquivo}/opcoes")
def opcoes_relatorio(cdarquivo: int, current_user: dict = Depends(get_current_user)):
    _relatorios_desativados()


@router.post("/{cdarquivo}/preview")
def preview_relatorio(cdarquivo: int, current_user: dict = Depends(get_current_user)):
    _relatorios_desativados()
