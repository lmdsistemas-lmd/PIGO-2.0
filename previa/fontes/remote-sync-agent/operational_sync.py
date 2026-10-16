"""Explicit local mapping of operational ERP tables. No guessed financial values."""
import json
import re
from pathlib import Path

CONTRACTS = {
    "TB_FORNECEDOR": ("FOR_PESSOA FOR_EMPRESA", "FOR_PESSOA FOR_EMPRESA"),
    "TB_PROD_DEPARTAMENTO": ("PDEP_ID", "PDEP_ID PDEP_DESCRICAO PDEP_STATUS"),
    "TB_PROD_SUBGRUPO": ("PSGR_ID", "PSGR_ID PSGR_EMPRESA PSGR_DESCRICAO PSGR_GRUPO PSGR_STATUS"),
    "TB_PLANO_CONTA": ("PLC_ID", "PLC_ID PLC_EMPRESA PLC_CODIGO PLC_DESCRICAO PLC_CONTA_PAI PLC_TIPO PLC_DRE PLC_STATUS"),
    "TB_FECHAMENTO_CAIXA_FORMA": ("FCF_ID FCF_EMPRESA FCF_FECHAMENTO", "FCF_ID FCF_EMPRESA FCF_FECHAMENTO FCF_NOME FCF_ENTRADAS FCF_SAIDAS FCF_CONFERENCIA"),
    "TB_PIGO_CAIXA_MOVIMENTO": ("FCI_ID FCI_EMPRESA FCI_FECHAMENTO", "FCI_ID FCI_EMPRESA FCI_FECHAMENTO FCI_TIPO FCI_DATA FCI_DESCRICAO FCI_QUANTIDADE FCI_VALOR FCI_DOCUMENTO FCI_USUARIO"),
    "TB_CAIXA_SANGRIA": ("SAN_ID SAN_EMPRESA", "SAN_ID SAN_EMPRESA SAN_DT_MOVIMENTO SAN_CAIXA SAN_OPERADOR SAN_DESCRICAO SAN_VALOR SAN_STATUS"),
    "TB_CHEQUE_EMITIDO": ("CHQ_ID CHQ_EMPRESA", "CHQ_ID CHQ_EMPRESA CHQ_NUMERO CHQ_FORNECEDOR CHQ_PESSOA CHQ_NOMINAL CHQ_CONTA CHQ_DT_EMISSAO CHQ_DT_VENCIMENTO CHQ_VALOR CHQ_STATUS"),
}


# Confirmed by the schema exported from IZABELLA. Keep the public mirror
# vocabulary stable; no status codes, balances or movement types are inferred.
CONFIRMED_MAPPINGS = {
    "TB_PROD_SUBGRUPO": {"table": "TB_PROD_SUB_GRUPO", "fields": {}},
    "TB_PLANO_CONTA": {"table": "TB_PLANO_CONTA", "fields": {"PLC_CONTA_PAI": "PLC_PAI", "PLC_TIPO": "PLC_TIPO_CONTA"}},
    "TB_CHEQUE_EMITIDO": {"table": "TB_CHEQUE_EMITIDO", "fields": {
        "CHQ_ID": "CHE_ID", "CHQ_EMPRESA": "CHE_EMPRESA", "CHQ_NUMERO": "CHE_NUMERO_CHEQUE",
        "CHQ_PESSOA": "CHE_PESSOA", "CHQ_NOMINAL": "CHE_NOMINAL", "CHQ_CONTA": "CHE_CONTA",
        "CHQ_DT_EMISSAO": "CHE_DT_EMISSAO", "CHQ_DT_VENCIMENTO": "CHE_DT_VENCIMENTO",
        "CHQ_VALOR": "CHE_VALOR_CHEQUE", "CHQ_STATUS": "CHE_STATUS",
    }},
}


def fetch_operational(conn, schema, mapping_file, execute_select):
    mappings = json.loads(Path(mapping_file).read_text(encoding="utf-8")) if mapping_file and Path(mapping_file).exists() else {}
    if set(mappings) - set(CONTRACTS):
        raise ValueError("Tabela operacional fora do contrato.")
    for canonical, (required, fields) in CONTRACTS.items():
        mapping = mappings.get(canonical)
        if mapping is None:
            confirmed = CONFIRMED_MAPPINGS.get(canonical, {})
            table = canonical if schema.has_table(canonical) else confirmed.get("table", canonical)
            aliases = {key: value for key, value in confirmed.get("fields", {}).items()
                       if not schema.has_column(table, key) and schema.has_column(table, value)}
            mapping = {"table": table, "fields": aliases}
        table = mapping.get("table", canonical)
        aliases = mapping.get("fields", {})
        if set(aliases) - set(fields.split()):
            raise ValueError("Campo operacional fora do contrato.")
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{0,62}", identifier) for identifier in [table, *aliases.values()]):
            raise ValueError("Identificador operacional inválido.")
        if not schema.has_table(table):
            continue
        available = {field: aliases.get(field, field) for field in fields.split() if schema.has_column(table, aliases.get(field, field))}
        if not set(required.split()) <= set(available):
            continue
        sql = "SELECT " + ", ".join(f"{actual} AS {field}" for field, actual in available.items()) + f" FROM {table}"
        yield canonical, execute_select(conn, sql, [], table)
