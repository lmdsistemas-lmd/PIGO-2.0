from app.services.erp_query_service import ERPQueryService


class PerformanceRepository:
    def __init__(self, erp_db=None):
        self.erp = ERPQueryService()

    def _fetch_all(self, sql: str, params: dict):
        return self.erp.fetch_all(sql, params)

    def buscar_resumo(self, where_sql: str, params: dict):
        sql = f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN a.AUD_ACAO = 'I' THEN 1 ELSE 0 END) AS inclusoes,
                SUM(CASE WHEN a.AUD_ACAO = 'A' THEN 1 ELSE 0 END) AS alteracoes,
                SUM(CASE WHEN a.AUD_ACAO = 'E' THEN 1 ELSE 0 END) AS exclusoes,
                SUM(CASE WHEN a.AUD_ACAO = 'C' THEN 1 ELSE 0 END) AS cancelamentos
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
        """
        row = self.erp.fetch_one(sql, params)
        if not row:
            return None
        return (
            row.get("TOTAL"),
            row.get("INCLUSOES"),
            row.get("ALTERACOES"),
            row.get("EXCLUSOES"),
            row.get("CANCELAMENTOS"),
        )

    def buscar_acoes_por_dia(self, where_sql: str, params: dict):
        sql = f"""
            SELECT
                CAST(a.AUD_DT_LANCAMENTO AS DATE) AS data_ref,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY CAST(a.AUD_DT_LANCAMENTO AS DATE)
            ORDER BY CAST(a.AUD_DT_LANCAMENTO AS DATE)
        """
        return [(row.get("DATA_REF"), row.get("TOTAL")) for row in self._fetch_all(sql, params)]

    def buscar_acoes_por_horario(self, where_sql: str, params: dict):
        sql = f"""
            SELECT
                EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP)) AS hora_ref,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP))
            ORDER BY EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP))
        """
        return [(row.get("HORA_REF"), row.get("TOTAL")) for row in self._fetch_all(sql, params)]

    def buscar_tabela_mais_movimentada(self, where_sql: str, params: dict):
        sql = f"""
            SELECT FIRST 1
                COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '-') AS tabela_desc,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '-')
            ORDER BY COUNT(*) DESC
        """
        row = self.erp.fetch_one(sql, params)
        if not row:
            return None
        return (row.get("TABELA_DESC"), row.get("TOTAL"))

    def buscar_resumo_por_funcionario(self, where_sql: str, params: dict):
        sql = f"""
            SELECT
                COALESCE(TRIM(u.USU_NOME), 'Sem nome') AS funcionario,
                COALESCE(TRIM(u.USU_LOGIN), '') AS usuario_login,
                COUNT(*) AS total,
                SUM(CASE WHEN a.AUD_ACAO = 'I' THEN 1 ELSE 0 END) AS inclusoes,
                SUM(CASE WHEN a.AUD_ACAO = 'A' THEN 1 ELSE 0 END) AS alteracoes,
                SUM(CASE WHEN a.AUD_ACAO = 'E' THEN 1 ELSE 0 END) AS exclusoes,
                SUM(CASE WHEN a.AUD_ACAO = 'C' THEN 1 ELSE 0 END) AS cancelamentos
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY
                COALESCE(TRIM(u.USU_NOME), 'Sem nome'),
                COALESCE(TRIM(u.USU_LOGIN), '')
            ORDER BY COUNT(*) DESC
        """
        return [
            (
                row.get("FUNCIONARIO"),
                row.get("USUARIO_LOGIN"),
                row.get("TOTAL"),
                row.get("INCLUSOES"),
                row.get("ALTERACOES"),
                row.get("EXCLUSOES"),
                row.get("CANCELAMENTOS"),
            )
            for row in self._fetch_all(sql, params)
        ]

    def buscar_usuarios_filtro(self, where_sql: str, params: dict):
        sql = f"""
            SELECT DISTINCT
                COALESCE(
                    TRIM(u.USU_NOME) || ' (' || TRIM(u.USU_LOGIN) || ')',
                    TRIM(u.USU_LOGIN),
                    CAST(a.AUD_USUARIO AS VARCHAR(20))
                ) AS usuario
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            ORDER BY 1
        """
        return [(row.get("USUARIO"),) for row in self._fetch_all(sql, params)]

    def buscar_tabelas_filtro(self, where_sql: str, params: dict):
        sql = f"""
            SELECT DISTINCT
                COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '') AS tabela
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            ORDER BY 1
        """
        return [(row.get("TABELA"),) for row in self._fetch_all(sql, params)]

    def buscar_registros(self, where_sql: str, params: dict):
        sql = f"""
            SELECT
                COALESCE(
                    TRIM(u.USU_NOME) || ' (' || TRIM(u.USU_LOGIN) || ')',
                    TRIM(u.USU_LOGIN),
                    CAST(a.AUD_USUARIO AS VARCHAR(20))
                ) AS usuario,
                COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '') AS tabela_desc,
                COALESCE(TRIM(a.AUD_TABELA), '') AS tabela,
                a.AUD_ID_REGISTRO AS id_registro,
                COALESCE(TRIM(a.AUD_DESC_REGISTRO), '') AS descricao_registro,
                a.AUD_DT_LANCAMENTO AS data_lancamento,
                a.AUD_DT_ACAO AS data_acao,
                CASE
                    WHEN a.AUD_ACAO = 'I' THEN 'Inclusao'
                    WHEN a.AUD_ACAO = 'A' THEN 'Alteracao'
                    WHEN a.AUD_ACAO = 'E' THEN 'Exclusao'
                    WHEN a.AUD_ACAO = 'C' THEN 'Cancelamento'
                    ELSE COALESCE(TRIM(a.AUD_ACAO), '')
                END AS acao
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            ORDER BY a.AUD_DT_LANCAMENTO DESC
        """
        return [
            (
                row.get("USUARIO"),
                row.get("TABELA_DESC"),
                row.get("TABELA"),
                row.get("ID_REGISTRO"),
                row.get("DESCRICAO_REGISTRO"),
                row.get("DATA_LANCAMENTO"),
                row.get("DATA_ACAO"),
                row.get("ACAO"),
            )
            for row in self._fetch_all(sql, params)
        ]
