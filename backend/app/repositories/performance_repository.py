from sqlalchemy import text
from sqlalchemy.orm import Session


class PerformanceRepository:
    def __init__(self, erp_db: Session):
        self.erp_db = erp_db

    def buscar_resumo(self, where_sql: str, params: dict):
        query = text(f"""
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
        """)
        return self.erp_db.execute(query, params).fetchone()

    def buscar_acoes_por_dia(self, where_sql: str, params: dict):
        query = text(f"""
            SELECT
                CAST(a.AUD_DT_LANCAMENTO AS DATE) AS data_ref,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY CAST(a.AUD_DT_LANCAMENTO AS DATE)
            ORDER BY CAST(a.AUD_DT_LANCAMENTO AS DATE)
        """)
        return self.erp_db.execute(query, params).fetchall()

    def buscar_acoes_por_horario(self, where_sql: str, params: dict):
        query = text(f"""
            SELECT
                EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP)) AS hora_ref,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP))
            ORDER BY EXTRACT(HOUR FROM CAST(a.AUD_DT_LANCAMENTO AS TIMESTAMP))
        """)
        return self.erp_db.execute(query, params).fetchall()

    def buscar_tabela_mais_movimentada(self, where_sql: str, params: dict):
        query = text(f"""
            SELECT FIRST 1
                COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '-') AS tabela_desc,
                COUNT(*) AS total
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            GROUP BY COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '-')
            ORDER BY COUNT(*) DESC
        """)
        return self.erp_db.execute(query, params).fetchone()

    def buscar_resumo_por_funcionario(self, where_sql: str, params: dict):
        query = text(f"""
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
        """)
        return self.erp_db.execute(query, params).fetchall()

    def buscar_usuarios_filtro(self, where_sql: str, params: dict):
        query = text(f"""
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
        """)
        return self.erp_db.execute(query, params).fetchall()

    def buscar_tabelas_filtro(self, where_sql: str, params: dict):
        query = text(f"""
            SELECT DISTINCT
                COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '') AS tabela
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            ORDER BY 1
        """)
        return self.erp_db.execute(query, params).fetchall()

    def buscar_registros(self, where_sql: str, params: dict):
        query = text(f"""
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
                    WHEN a.AUD_ACAO = 'I' THEN 'Inclusão'
                    WHEN a.AUD_ACAO = 'A' THEN 'Alteração'
                    WHEN a.AUD_ACAO = 'E' THEN 'Exclusão'
                    WHEN a.AUD_ACAO = 'C' THEN 'Cancelamento'
                    ELSE COALESCE(TRIM(a.AUD_ACAO), '')
                END AS acao
            FROM TB_AUDITORIA a
            LEFT JOIN TB_USUARIO u
              ON u.USU_ID = a.AUD_USUARIO
            WHERE {where_sql}
            ORDER BY a.AUD_DT_LANCAMENTO DESC
        """)
        return self.erp_db.execute(query, params).fetchall()