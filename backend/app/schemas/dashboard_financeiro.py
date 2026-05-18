from pydantic import BaseModel
from typing import List


class ContasResumo(BaseModel):
    total: float
    variation: str
    subtitle: str
    highlight: str
    history: List[int]


class InadimplenciaResumo(BaseModel):
    taxa: float
    totalVencido: float
    totalReceber: float
    recuperadoMes: float


class ReceitaDespesaItem(BaseModel):
    label: str
    receitas: float
    despesas: float


class AgingItem(BaseModel):
    faixa: str
    valor: float
    titulos: int
    tone: str


class ClienteItem(BaseModel):
    nome: str
    valor: float
    pedidos: int


class FornecedorItem(BaseModel):
    nome: str
    quantidade: int
    volume: float


class EstoqueCriticoItem(BaseModel):
    produto: str
    estoque: int
    minimo: int
    status: str


class CidadeClienteItem(BaseModel):
    cidade: str
    quantidade: int
    x: int
    y: int
    cor: str


class DashboardFinanceiroResponse(BaseModel):
    contasPagar: ContasResumo
    contasReceber: ContasResumo
    inadimplencia: InadimplenciaResumo
    receitasDespesas: List[ReceitaDespesaItem]
    aging: List[AgingItem]
    melhoresClientes: List[ClienteItem]
    melhoresFornecedores: List[FornecedorItem]
    estoqueCritico: List[EstoqueCriticoItem]
    cidadesClientes: List[CidadeClienteItem]