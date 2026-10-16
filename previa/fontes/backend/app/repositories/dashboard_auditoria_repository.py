from __future__ import annotations

from app.repositories.base_repository import BaseRepository
from app.services.base_dashboard_service import DateRange


class DashboardAuditoriaRepository(BaseRepository):
    def get_total_acoes(self, date_range: DateRange, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return int(self._scalar(sql, params))

    def get_total_usuarios(self, date_range: DateRange, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT COUNT(DISTINCT A.AUD_USUARIO) AS TOTAL
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return int(self._scalar(sql, params))

    def get_total_tabelas(self, date_range: DateRange, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT COUNT(DISTINCT A.AUD_TABELA) AS TOTAL
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return int(self._scalar(sql, params))

    def get_ultima_acao_data(self, date_range: DateRange, empresa_id: int | None):
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT MAX(A.AUD_DT_ACAO) AS DATA_ULTIMA
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }

        rows = self._fetch_all(sql, params)
        if not rows:
            return None
        return rows[0].get("DATA_ULTIMA")

    def get_ultimas_acoes(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                A.AUD_EMPRESA,
                A.AUD_TABELA,
                A.AUD_ID_REGISTRO,
                A.AUD_SEQUENCIA,
                A.AUD_TABELA_DESC,
                A.AUD_ACAO,
                A.AUD_DT_LANCAMENTO,
                A.AUD_DT_ACAO,
                A.AUD_USUARIO,
                A.AUD_DESC_REGISTRO,
                A.AUD_VENDEDOR
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
            ORDER BY A.AUD_DT_ACAO DESC, A.AUD_SEQUENCIA DESC
            ROWS 50
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._fetch_all(sql, params)

    def get_acoes_por_usuario(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                A.AUD_USUARIO AS USUARIO_ID,
                COALESCE(U.USU_NOME, 'Usuario ' || CAST(A.AUD_USUARIO AS VARCHAR(20))) AS USUARIO_NOME,
                COUNT(*) AS TOTAL_ACOES
            FROM TB_AUDITORIA A
            LEFT JOIN TB_USUARIO U
                ON U.USU_ID = A.AUD_USUARIO
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
            GROUP BY
                A.AUD_USUARIO,
                COALESCE(U.USU_NOME, 'Usuario ' || CAST(A.AUD_USUARIO AS VARCHAR(20)))
            ORDER BY TOTAL_ACOES DESC
            ROWS 15
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._fetch_all(sql, params)

    def get_acoes_por_tabela(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                A.AUD_TABELA,
                A.AUD_TABELA_DESC,
                COUNT(*) AS TOTAL_ACOES
            FROM TB_AUDITORIA A
            WHERE A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
            GROUP BY A.AUD_TABELA, A.AUD_TABELA_DESC
            ORDER BY TOTAL_ACOES DESC
            ROWS 20
        """

        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._fetch_all(sql, params)

    def get_funcionario_contexto(self, colaborador_pessoa: int, empresa_id: int | None) -> dict | None:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                C.COL_EMPRESA,
                C.COL_PESSOA,
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME) AS NOME,
                C.COL_FUNCAO,
                C.COL_STATUS,
                COALESCE(P.PES_VENDEDOR, 'N') AS PES_VENDEDOR,
                U.USU_ID,
                U.USU_NOME
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            LEFT JOIN TB_USUARIO U
                ON U.USU_VENDEDOR = P.PES_ID
            WHERE C.COL_PESSOA = :colaborador_pessoa
              {empresa_sql}
            ROWS 1
        """

        params = {
            "colaborador_pessoa": colaborador_pessoa,
            **empresa_params,
        }

        rows = self._fetch_all(sql, params)
        if not rows:
            return None
        return rows[0]

    def get_ultimas_acoes_funcionario(
        self,
        usuario_id: int,
        date_range: DateRange,
        empresa_id: int | None,
    ) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                A.AUD_EMPRESA,
                A.AUD_TABELA,
                A.AUD_ID_REGISTRO,
                A.AUD_SEQUENCIA,
                A.AUD_TABELA_DESC,
                A.AUD_ACAO,
                A.AUD_DT_LANCAMENTO,
                A.AUD_DT_ACAO,
                A.AUD_USUARIO,
                A.AUD_DESC_REGISTRO,
                A.AUD_VENDEDOR
            FROM TB_AUDITORIA A
            WHERE A.AUD_USUARIO = :usuario_id
              AND A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
            ORDER BY A.AUD_DT_ACAO DESC, A.AUD_SEQUENCIA DESC
            ROWS 50
        """

        params = {
            "usuario_id": usuario_id,
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._fetch_all(sql, params)

    def get_campos_alterados_funcionario(
        self,
        usuario_id: int,
        date_range: DateRange,
        empresa_id: int | None,
    ) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("A.AUD_EMPRESA", empresa_id)

        sql = f"""
            SELECT
                AI.AUDI_EMPRESA,
                AI.AUDI_TABELA,
                AI.AUDI_ID_REGISTRO,
                AI.AUDI_AUDITORIA,
                AI.AUDI_CAMPO,
                AI.AUDI_CAMPO_DESC,
                AI.AUDI_VALOR_ANTIGO,
                AI.AUDI_VALOR_NOVO
            FROM TB_AUDITORIA_ITEM AI
            INNER JOIN TB_AUDITORIA A
                ON A.AUD_EMPRESA = AI.AUDI_EMPRESA
               AND A.AUD_TABELA = AI.AUDI_TABELA
               AND A.AUD_ID_REGISTRO = AI.AUDI_ID_REGISTRO
               AND A.AUD_SEQUENCIA = AI.AUDI_AUDITORIA
            WHERE A.AUD_USUARIO = :usuario_id
              AND A.AUD_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              {empresa_sql}
            ORDER BY A.AUD_DT_ACAO DESC, AI.AUDI_AUDITORIA DESC
            ROWS 100
        """

        params = {
            "usuario_id": usuario_id,
            "start_date": date_range.start,
            "end_date": date_range.end,
            **empresa_params,
        }
        return self._fetch_all(sql, params)