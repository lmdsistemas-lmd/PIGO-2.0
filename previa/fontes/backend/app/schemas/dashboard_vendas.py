from pydantic import BaseModel
from typing import List


class VendasResumo(BaseModel):
    faturamento: float
    pedidos: int
    ticketMedio: float
    itensPorVenda: float
    custoTotal: float
    lucroBruto: float
    margemLucro: float
    markup: float
    lucratividade: float
    variation: str


class HistoricoVendaItem(BaseModel):
    ano: int | None = None
    label: str
    valor: float
    pedidos: int


class TopClienteVendaItem(BaseModel):
    nome: str
    valor: float
    pedidos: int


class TopProdutoVendaItem(BaseModel):
    produto: str
    quantidade: float
    valor: float


class CidadeVendaItem(BaseModel):
    cidade: str
    quantidade: int


class VendedorVendaItem(BaseModel):
    vendedor: str
    pedidos: int
    valor: float


class DistribuicaoVendaItem(BaseModel):
    label: str
    valor: float


class FaixaHorarioVendaItem(BaseModel):
    faixa: str
    valor: float
    pedidos: int


class DiaSemanaVendaItem(BaseModel):
    dia: str
    valor: float
    pedidos: int


class DashboardVendasResponse(BaseModel):
    resumo: VendasResumo
    historico: List[HistoricoVendaItem]
    topClientes: List[TopClienteVendaItem]
    topProdutos: List[TopProdutoVendaItem]
    vendasPorCidade: List[CidadeVendaItem]
    vendasPorVendedor: List[VendedorVendaItem]
    vendasPorGrupo: List[DistribuicaoVendaItem]
    vendasPorMarca: List[DistribuicaoVendaItem]
    mediaPorFaixaHoraria: List[FaixaHorarioVendaItem]
    mediaPorDiaSemana: List[DiaSemanaVendaItem]