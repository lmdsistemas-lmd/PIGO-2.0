from __future__ import annotations

from app.repositories.dashboard_auditoria_repository import DashboardAuditoriaRepository
from app.services.base_dashboard_service import BaseDashboardService


class DashboardAuditoriaService(BaseDashboardService):
    def __init__(self) -> None:
        self.repository = DashboardAuditoriaRepository()

    def get_dashboard_auditoria(
        self,
        period: str,
        start: str | None,
        end: str | None,
        empresa_id: int | None = None,
    ) -> dict:
        date_range = self._resolve_period(period, start, end)

        ultima_acao_data = self.repository.get_ultima_acao_data(date_range, empresa_id)
        ultimas_acoes_rows = self.repository.get_ultimas_acoes(date_range, empresa_id)
        acoes_por_usuario_rows = self.repository.get_acoes_por_usuario(date_range, empresa_id)
        acoes_por_tabela_rows = self.repository.get_acoes_por_tabela(date_range, empresa_id)

        return {
            "resumo": {
                "totalAcoes": self.repository.get_total_acoes(date_range, empresa_id),
                "totalUsuarios": self.repository.get_total_usuarios(date_range, empresa_id),
                "totalTabelas": self.repository.get_total_tabelas(date_range, empresa_id),
                "ultimaAcaoEm": ultima_acao_data.isoformat() if ultima_acao_data else None,
            },
            "ultimasAcoes": [
                {
                    "empresa": int(row.get("AUD_EMPRESA", 0) or 0) if row.get("AUD_EMPRESA") is not None else None,
                    "tabela": row.get("AUD_TABELA") or "",
                    "tabelaDesc": row.get("AUD_TABELA_DESC"),
                    "idRegistro": int(row.get("AUD_ID_REGISTRO", 0) or 0) if row.get("AUD_ID_REGISTRO") is not None else None,
                    "sequencia": int(row.get("AUD_SEQUENCIA", 0) or 0) if row.get("AUD_SEQUENCIA") is not None else None,
                    "acao": row.get("AUD_ACAO"),
                    "dataLancamento": row.get("AUD_DT_LANCAMENTO").isoformat() if row.get("AUD_DT_LANCAMENTO") else None,
                    "dataAcao": row.get("AUD_DT_ACAO").isoformat() if row.get("AUD_DT_ACAO") else None,
                    "usuarioId": int(row.get("AUD_USUARIO", 0) or 0) if row.get("AUD_USUARIO") is not None else None,
                    "vendedorId": int(row.get("AUD_VENDEDOR", 0) or 0) if row.get("AUD_VENDEDOR") is not None else None,
                    "descricaoRegistro": row.get("AUD_DESC_REGISTRO"),
                }
                for row in ultimas_acoes_rows
            ],
            "acoesPorUsuario": [
                {
                    "usuarioId": int(row.get("USUARIO_ID", 0) or 0) if row.get("USUARIO_ID") is not None else None,
                    "usuarioNome": row.get("USUARIO_NOME") or "Sem nome",
                    "totalAcoes": int(row.get("TOTAL_ACOES", 0) or 0),
                }
                for row in acoes_por_usuario_rows
            ],
            "acoesPorTabela": [
                {
                    "tabela": row.get("AUD_TABELA") or "",
                    "tabelaDesc": row.get("AUD_TABELA_DESC"),
                    "totalAcoes": int(row.get("TOTAL_ACOES", 0) or 0),
                }
                for row in acoes_por_tabela_rows
            ],
        }

    def get_dashboard_auditoria_funcionario(
        self,
        colaborador_pessoa: int,
        period: str,
        start: str | None,
        end: str | None,
        empresa_id: int | None = None,
    ) -> dict:
        date_range = self._resolve_period(period, start, end)
        contexto = self.repository.get_funcionario_contexto(colaborador_pessoa, empresa_id)

        if not contexto:
            return {
                "resumo": {
                    "colaboradorPessoa": colaborador_pessoa,
                    "nome": "Funcionario nao encontrado",
                    "funcao": None,
                    "status": None,
                    "vendedor": False,
                    "usuarioId": None,
                    "usuarioNome": None,
                    "totalAcoes": 0,
                },
                "ultimasAcoes": [],
                "camposAlterados": [],
            }

        usuario_id = int(contexto.get("USU_ID", 0) or 0) if contexto.get("USU_ID") is not None else None

        if usuario_id is None:
            return {
                "resumo": {
                    "colaboradorPessoa": int(contexto.get("COL_PESSOA", 0) or 0),
                    "nome": contexto.get("NOME") or "Sem nome",
                    "funcao": contexto.get("COL_FUNCAO"),
                    "status": contexto.get("COL_STATUS"),
                    "vendedor": str(contexto.get("PES_VENDEDOR") or "N").upper() == "S",
                    "usuarioId": None,
                    "usuarioNome": None,
                    "totalAcoes": 0,
                },
                "ultimasAcoes": [],
                "camposAlterados": [],
            }

        ultimas_acoes_rows = self.repository.get_ultimas_acoes_funcionario(
            usuario_id=usuario_id,
            date_range=date_range,
            empresa_id=empresa_id,
        )
        campos_alterados_rows = self.repository.get_campos_alterados_funcionario(
            usuario_id=usuario_id,
            date_range=date_range,
            empresa_id=empresa_id,
        )

        return {
            "resumo": {
                "colaboradorPessoa": int(contexto.get("COL_PESSOA", 0) or 0),
                "nome": contexto.get("NOME") or "Sem nome",
                "funcao": contexto.get("COL_FUNCAO"),
                "status": contexto.get("COL_STATUS"),
                "vendedor": str(contexto.get("PES_VENDEDOR") or "N").upper() == "S",
                "usuarioId": usuario_id,
                "usuarioNome": contexto.get("USU_NOME"),
                "totalAcoes": len(ultimas_acoes_rows),
            },
            "ultimasAcoes": [
                {
                    "empresa": int(row.get("AUD_EMPRESA", 0) or 0) if row.get("AUD_EMPRESA") is not None else None,
                    "tabela": row.get("AUD_TABELA") or "",
                    "tabelaDesc": row.get("AUD_TABELA_DESC"),
                    "idRegistro": int(row.get("AUD_ID_REGISTRO", 0) or 0) if row.get("AUD_ID_REGISTRO") is not None else None,
                    "sequencia": int(row.get("AUD_SEQUENCIA", 0) or 0) if row.get("AUD_SEQUENCIA") is not None else None,
                    "acao": row.get("AUD_ACAO"),
                    "dataLancamento": row.get("AUD_DT_LANCAMENTO").isoformat() if row.get("AUD_DT_LANCAMENTO") else None,
                    "dataAcao": row.get("AUD_DT_ACAO").isoformat() if row.get("AUD_DT_ACAO") else None,
                    "usuarioId": int(row.get("AUD_USUARIO", 0) or 0) if row.get("AUD_USUARIO") is not None else None,
                    "vendedorId": int(row.get("AUD_VENDEDOR", 0) or 0) if row.get("AUD_VENDEDOR") is not None else None,
                    "descricaoRegistro": row.get("AUD_DESC_REGISTRO"),
                }
                for row in ultimas_acoes_rows
            ],
            "camposAlterados": [
                {
                    "empresa": int(row.get("AUDI_EMPRESA", 0) or 0) if row.get("AUDI_EMPRESA") is not None else None,
                    "tabela": row.get("AUDI_TABELA") or "",
                    "idRegistro": int(row.get("AUDI_ID_REGISTRO", 0) or 0) if row.get("AUDI_ID_REGISTRO") is not None else None,
                    "auditoriaSequencia": int(row.get("AUDI_AUDITORIA", 0) or 0) if row.get("AUDI_AUDITORIA") is not None else None,
                    "campo": row.get("AUDI_CAMPO") or "",
                    "campoDesc": row.get("AUDI_CAMPO_DESC"),
                    "valorAntigo": row.get("AUDI_VALOR_ANTIGO"),
                    "valorNovo": row.get("AUDI_VALOR_NOVO"),
                }
                for row in campos_alterados_rows
            ],
        }