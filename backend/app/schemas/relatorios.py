from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RelatorioListItem(BaseModel):
    cdarquivo: int
    nome: str
    descricao: Optional[str] = None
    cdpastamae: Optional[int] = None
    pasta_nome: Optional[str] = None
    pasta_descricao: Optional[str] = None
    ultima_alteracao: Optional[str] = None
    exportar: Optional[str] = None
    periodo_app: Optional[str] = None
    vendedor_app: Optional[str] = None
    cliente_app: Optional[str] = None
    empresa_app: Optional[str] = None
    categoria: str


class RelatorioDatasetInfo(BaseModel):
    dataset: Optional[str] = None
    dataset_name: Optional[str] = None


class RelatorioVariableInfo(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None


class RelatorioParametroInfo(BaseModel):
    name: Optional[str] = None
    datatype: Optional[str] = None


class RelatorioParametroDetectadoInfo(BaseModel):
    original_name: str
    inferred_type: str
    semantic_key: str
    default_value: Any = None


class RelatorioQueryInfo(BaseModel):
    name: Optional[str] = None
    user_name: Optional[str] = None
    sql_text: Optional[str] = None
    parametros: List[RelatorioParametroInfo] = Field(default_factory=list)


class RelatorioLayoutPageInfo(BaseModel):
    name: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None


class RelatorioLayoutBandInfo(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    page_name: Optional[str] = None
    page_index: Optional[int] = None
    parent_band_name: Optional[str] = None
    child_band_name: Optional[str] = None
    data_set: Optional[str] = None
    condition: Optional[str] = None
    left: Optional[str] = None
    top: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None


class RelatorioLayoutMemoInfo(BaseModel):
    name: Optional[str] = None
    text: Optional[str] = None

    page_name: Optional[str] = None
    page_index: Optional[int] = None

    left: Optional[str] = None
    top: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None

    data_field: Optional[str] = None
    data_set: Optional[str] = None

    h_align: Optional[str] = None
    v_align: Optional[str] = None

    font_name: Optional[str] = None
    font_size: Optional[str] = None
    font_style: Optional[str] = None

    color: Optional[str] = None
    fill_color: Optional[str] = None

    border_color: Optional[str] = None
    border_width: Optional[str] = None

    band_name: Optional[str] = None
    band_type: Optional[str] = None


class RelatorioLayoutVisualInfo(BaseModel):
    pages: List[RelatorioLayoutPageInfo] = Field(default_factory=list)
    bands: List[RelatorioLayoutBandInfo] = Field(default_factory=list)
    memos: List[RelatorioLayoutMemoInfo] = Field(default_factory=list)


class RelatorioInspecaoResponse(BaseModel):
    cdarquivo: int
    nome: str
    descricao: Optional[str] = None
    pasta_nome: Optional[str] = None
    pasta_pai_nome: Optional[str] = None
    categoria: str
    xml_valido: bool
    datasets: List[RelatorioDatasetInfo] = Field(default_factory=list)
    variables: List[RelatorioVariableInfo] = Field(default_factory=list)
    queries: List[RelatorioQueryInfo] = Field(default_factory=list)
    parameters_detected: List[RelatorioParametroDetectadoInfo] = Field(default_factory=list)
    layout_visual: Optional[RelatorioLayoutVisualInfo] = None
    observacoes: List[str] = Field(default_factory=list)