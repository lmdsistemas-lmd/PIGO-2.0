from pydantic import BaseModel

class ResumoEstoque(BaseModel):
    totalProdutos: int
    ativos: int
    inativos: int

class ValoresEstoque(BaseModel):
    custoTotal: float | None
    vendaTotal: float | None

class AlertasEstoque(BaseModel):
    total: int | None
    semEstoque: int | None
    abaixoMinimo: int | None

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
    estoqueDisponivel: bool = True
    resumo: ResumoEstoque
    valores: ValoresEstoque
    alertas: AlertasEstoque
    compras: ComprasResumo
    rotatividade: list[ProdutoRotatividade]
    criticos: list[ProdutoCritico]
