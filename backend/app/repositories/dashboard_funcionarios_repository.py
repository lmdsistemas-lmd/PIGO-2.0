from __future__ import annotations

from app.repositories.base_repository import BaseRepository


class DashboardFuncionariosRepository(BaseRepository):
    def _vendedores_com_usuario_filter(self) -> str:
        return """
            AND COALESCE(P.PES_VENDEDOR, 'N') = 'S'
            AND EXISTS (
                SELECT 1
                FROM TB_USUARIO U
                WHERE U.USU_VENDEDOR = C.COL_PESSOA
            )
        """

    def get_total_funcionarios(self, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE 1 = 1
              {empresa_sql}
              {vendedores_sql}
        """

        return int(self._scalar(sql, empresa_params))

    def get_total_ativos(self, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE COALESCE(C.COL_STATUS, '') NOT IN ('AFASTADO', 'INATIVO', 'DESLIGADO')
              {empresa_sql}
              {vendedores_sql}
        """

        return int(self._scalar(sql, empresa_params))

    def get_total_afastados(self, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE COALESCE(C.COL_STATUS, '') IN ('AFASTADO', 'INATIVO', 'DESLIGADO')
              {empresa_sql}
              {vendedores_sql}
        """

        return int(self._scalar(sql, empresa_params))

    def get_total_vendedores(self, empresa_id: int | None) -> int:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT COUNT(*) AS TOTAL
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE 1 = 1
              {empresa_sql}
              {vendedores_sql}
        """

        return int(self._scalar(sql, empresa_params))

    def get_media_salarial(self, empresa_id: int | None) -> float:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT COALESCE(
                AVG(CAST(COALESCE(C.COL_SALARIO_VALOR, C.COL_SALARIO, 0) AS NUMERIC(18,2))),
                0
            ) AS TOTAL
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE 1 = 1
              {empresa_sql}
              {vendedores_sql}
        """

        return float(self._scalar(sql, empresa_params))

    def get_distribuicao_funcoes(self, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT
                COALESCE(NULLIF(TRIM(C.COL_FUNCAO), ''), 'Nao informada') AS FUNCAO,
                COUNT(*) AS QUANTIDADE
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE 1 = 1
              {empresa_sql}
              {vendedores_sql}
            GROUP BY COALESCE(NULLIF(TRIM(C.COL_FUNCAO), ''), 'Nao informada')
            ORDER BY QUANTIDADE DESC
            ROWS 20
        """

        return self._fetch_all(sql, empresa_params)

    def get_funcionarios_erp(self, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("C.COL_EMPRESA", empresa_id)
        vendedores_sql = self._vendedores_com_usuario_filter()

        sql = f"""
            SELECT
                C.COL_PESSOA,
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME) AS NOME,
                C.COL_FUNCAO,
                C.COL_STATUS,
                CAST(COALESCE(C.COL_SALARIO_VALOR, C.COL_SALARIO, 0) AS NUMERIC(18,2)) AS SALARIO,
                C.COL_DATA_ADMISSAO,
                C.COL_DATA_AFASTAMENTO,
                P.PES_EMAIL,
                P.PES_TELEFONE,
                P.PES_CELULAR,
                COALESCE(P.PES_VENDEDOR, 'N') AS PES_VENDEDOR
            FROM TB_COLABORADOR C
            INNER JOIN TB_PESSOA P
                ON P.PES_ID = C.COL_PESSOA
            WHERE 1 = 1
              {empresa_sql}
              {vendedores_sql}
            ORDER BY NOME
            ROWS 500
        """

        return self._fetch_all(sql, empresa_params)