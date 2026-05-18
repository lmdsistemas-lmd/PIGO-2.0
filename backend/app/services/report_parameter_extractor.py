# app/services/report_parameter_extractor.py

import re
from collections import OrderedDict
from typing import Iterable, List

# Captura :PARAM, mas evita pegar ::CAST de outros bancos
PARAM_REGEX = re.compile(r'(?<!:):([A-Za-z_][A-Za-z0-9_]*)')


def strip_sql_comments(sql: str) -> str:
    """
    Remove comentários SQL simples e de bloco.
    """
    if not sql:
        return ""

    # comentário de linha
    sql = re.sub(r'--.*?(\n|$)', ' ', sql)
    # comentário de bloco
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    return sql


def extract_sql_params(sql: str) -> List[str]:
    """
    Extrai parâmetros :PARAM de um SQL.
    Retorna nomes em UPPERCASE, sem duplicar.
    """
    if not sql:
        return []

    clean_sql = strip_sql_comments(sql)
    matches = PARAM_REGEX.findall(clean_sql)

    unique = OrderedDict()
    for match in matches:
        unique[match.upper()] = True

    return list(unique.keys())


def extract_params_from_queries(queries: Iterable[str]) -> List[str]:
    """
    Extrai todos os parâmetros de uma lista de SQLs.
    Mantém ordem e remove duplicados.
    """
    unique = OrderedDict()

    for sql in queries:
        for param in extract_sql_params(sql):
            unique[param] = True

    return list(unique.keys())