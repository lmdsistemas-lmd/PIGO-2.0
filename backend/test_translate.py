
import re

def quote_and_upper(match):
    return f'"{match.group(1).upper()}"'

def _translate_sql(sql: str) -> str:
    # 1. FIRST n -> LIMIT n
    match_first = re.search(r"FIRST\s+(\d+)", sql, re.IGNORECASE)
    if match_first:
        limit_val = match_first.group(1)
        sql = re.sub(r"FIRST\s+\d+", "", sql, flags=re.IGNORECASE)
        sql += f" LIMIT {limit_val}"

    # 2. ROWS n TO m -> LIMIT (m-n+1) OFFSET (n-1)
    match_rows = re.search(r"ROWS\s+(\d+)\s+TO\s+(\d+)", sql, re.IGNORECASE)
    if match_rows:
        start = int(match_rows.group(1))
        end = int(match_rows.group(2))
        limit = end - start + 1
        offset = start - 1
        sql = re.sub(r"ROWS\s+\d+\s+TO\s+\d+", "", sql, flags=re.IGNORECASE)
        sql += f" LIMIT {limit} OFFSET {offset}"
    
    # 3.1. Envolve tabelas em aspas (tudo que começa com TB_)
    sql = re.sub(r'\b(TB_[A-Z0-9_]+)\b', r'"\1"', sql, flags=re.IGNORECASE)
    
    # 3.2. Envolve colunas do padrão do ERP em aspas
    sql = re.sub(r'\b((?:PEV|PEVI|REC|RECI|PAG|PAGI|PRD|PRDE|PES|EMP|CID|AUD|USU)_[A-Za-z0-9_]+)\b', quote_and_upper, sql, flags=re.IGNORECASE)

    # 3.3. Converte DATEADD
    sql = re.sub(
        r'DATEADD\s*\(\s*(-?\d+)\s+(DAY|MONTH|YEAR)S?\s+TO\s+CURRENT_DATE\s*\)',
        r"CURRENT_DATE + INTERVAL '\1 \2'",
        sql,
        flags=re.IGNORECASE
    )

    # 3.4. Converte SELECT FIRST n
    limit_match = re.search(r'SELECT\s+FIRST\s+(\d+)', sql, flags=re.IGNORECASE)
    if limit_match:
        limit_val = limit_match.group(1)
        sql = re.sub(r'SELECT\s+FIRST\s+\d+', 'SELECT', sql, flags=re.IGNORECASE)
        sql = sql.strip()
        if sql.endswith(';'):
            sql = sql[:-1] + f" LIMIT {limit_val};"
        else:
            sql += f" LIMIT {limit_val}"

    return sql

test_queries = [
    """
    SELECT SUM(PV.PEV_VALOR_TOTAL) AS TOTAL
    FROM TB_PEDIDO_VENDA PV
    WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
      AND PV.PEV_STATUS <> 'C'
    """,
    """
    SELECT FIRST 10
        PR.PRD_DESCRICAO AS PRODUTO,
        SUM(I.pevi_quantidade) AS QUANTIDADE
    FROM TB_PEDIDO_VENDA_ITEM I
    INNER JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA
    INNER JOIN TB_PRODUTO PR ON PR.PRD_ID = I.PEVI_PRODUTO
    GROUP BY 1
    ORDER BY 2 DESC
    """
]

for q in test_queries:
    print(f"ORIGINAL:\n{q}")
    print(f"TRANSLATED:\n{_translate_sql(q)}")
    print("-" * 40)
