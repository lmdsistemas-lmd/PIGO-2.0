from pydantic import BaseModel

class ResumoEstoque(BaseModel):
    totalProdutos: int
    ativos: int
    inativos: int

class ValoresEstoque(BaseModel):
    custoTotal: float
    vendaTotal: float

class AlertasEstoque(BaseModel):
    total: int
    semEstoque: int
    abaixoMinimo: int

class ComprasResumo(BaseModel):
    quantidade: int
    valorTotal: float

class ProdutoRotatividade(BaseModel):
    produto: str
    vendida: float
    estoque: float

class ProdutoCritico(BaseModel):
    produto: str
    estoque: float
    minimo: float

class DashboardEstoqueResponse(BaseModel):
    resumo: ResumoEstoque
    valores: ValoresEstoque
    alertas: AlertasEstoque
    compras: ComprasResumo
    rotatividade: list[ProdutoRotatividade]
    criticos: list[ProdutoCritico]
