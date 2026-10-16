"""Prevent legacy single-position indicators from aggregating unknown stock."""


def stock_requires_consolidation(repository, company):
    company_sql, params = repository._empresa_filter("E.PRDE_EMPRESA", company)
    row = repository._fetch_one(f"""
        SELECT COUNT(*) AS POSICOES
        FROM TB_PRODUTO_ESTOQUE E
        WHERE 1=1 {company_sql}
        GROUP BY E.PRDE_PRODUTO, E.PRDE_EMPRESA
        HAVING COUNT(*) > 1 OR COUNT(E.PRDE_ESTOQUE) <> COUNT(*)
        ROWS 1
    """, params)
    return bool(row)
