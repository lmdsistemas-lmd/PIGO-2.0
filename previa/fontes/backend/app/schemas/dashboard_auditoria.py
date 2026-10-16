from pydantic import BaseModel
from typing import List


class AuditoriaResumo(BaseModel):
    totalAcoes: int
    totalUsuarios: int
    totalTabelas: int
    ultimaAcaoEm: str | None


class AuditoriaTimelineItem(BaseModel):
    empresa: int | None
    tabela: str
    tabelaDesc: str | None
    idRegistro: int | None
    sequencia: int | None
    acao: str | None
    dataLancamento: str | None
    dataAcao: str | None
    usuarioId: int | None
    vendedorId: int | None
    descricaoRegistro: str | None


class AuditoriaPorUsuarioItem(BaseModel):
    usuarioId: int | None
    usuarioNome: str
    totalAcoes: int


class AuditoriaPorTabelaItem(BaseModel):
    tabela: str
    tabelaDesc: str | None
    totalAcoes: int


class AuditoriaCampoAlteradoItem(BaseModel):
    empresa: int | None
    tabela: str
    idRegistro: int | None
    auditoriaSequencia: int | None
    campo: str
    campoDesc: str | None
    valorAntigo: str | None
    valorNovo: str | None


class DashboardAuditoriaResponse(BaseModel):
    resumo: AuditoriaResumo
    ultimasAcoes: List[AuditoriaTimelineItem]
    acoesPorUsuario: List[AuditoriaPorUsuarioItem]
    acoesPorTabela: List[AuditoriaPorTabelaItem]


class AuditoriaFuncionarioResumo(BaseModel):
    colaboradorPessoa: int
    nome: str
    funcao: str | None
    status: str | None
    vendedor: bool
    usuarioId: int | None
    usuarioNome: str | None
    totalAcoes: int


class DashboardAuditoriaFuncionarioResponse(BaseModel):
    resumo: AuditoriaFuncionarioResumo
    ultimasAcoes: List[AuditoriaTimelineItem]
    camposAlterados: List[AuditoriaCampoAlteradoItem]