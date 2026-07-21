import json
import hashlib
import logging
import locale
import os
import random
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

# Compatibilidade do fdb 2.0.2 com Python 3.13, que removeu locale.resetlocale.
if not hasattr(locale, "resetlocale"):
    def _resetlocale(category=locale.LC_ALL):
        return locale.setlocale(category, "")

    locale.resetlocale = _resetlocale

import fdb
import requests
import schedule
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

AGENT_VERSION = "2026.07.02-license-control"
AGENT_FILE = Path(__file__).resolve()
AGENT_DIR = AGENT_FILE.parent
ENV_FILE = AGENT_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)

FB_HOST = os.getenv("FB_HOST", "127.0.0.1")
FB_PORT = int(os.getenv("FB_PORT", "3050"))
FB_DATABASE = os.getenv("FB_DATABASE")
FB_USER = os.getenv("FB_USER")
FB_PASS = os.getenv("FB_PASS")
FB_CLIENT_PATH = os.getenv("FB_CLIENT_PATH")

API_BASE_URL = os.getenv("API_BASE_URL")
API_TOKEN = os.getenv("API_TOKEN")
COMPANY_CNPJ = os.getenv("COMPANY_CNPJ")
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_MINUTES", "5"))
DIAGNOSTIC_FILE = os.getenv("SCHEMA_DIAGNOSTIC_FILE", "schema_diagnostics.json")
SEND_SUCCESS = "success"
SEND_RETRYABLE_FAILURE = "retryable_failure"
SEND_PERMANENT_FAILURE = "permanent_failure"


def mask_token(token):
    value = str(token or "").strip()
    if not value:
        return "(nao configurado)"
    return "(configurado)"


def mask_cnpj(cnpj):
    digits = "".join(char for char in str(cnpj or "") if char.isdigit())
    if len(digits) < 4:
        return "(nao configurado)"
    return f"{digits[:2]}********{digits[-2:]}"


def remote_endpoint(path):
    return f"{str(API_BASE_URL or '').rstrip('/')}/{path.lstrip('/')}"


def sanitized_remote_context():
    parsed = urlsplit(str(API_BASE_URL or ""))
    return {
        "source": str(ENV_FILE),
        "protocol": parsed.scheme or "(ausente)",
        "host": parsed.hostname or "(ausente)",
        "port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "base_path": parsed.path or "/",
        "sync_endpoint": urlsplit(remote_endpoint("sync")).path,
    }


def log_startup_context():
    logger.info("[BOOT] Agente P.I.G.O versao=%s", AGENT_VERSION)
    logger.info("[BOOT] agent.py=%s", AGENT_FILE)
    logger.info("[BOOT] .env carregado=%s | existe=%s", ENV_FILE, ENV_FILE.exists())
    logger.info("[BOOT] Python=%s", sys.executable)
    context = sanitized_remote_context()
    logger.info(
        "[BOOT] remote source=%s protocol=%s host=%s port=%s base_path=%s endpoint=%s",
        context["source"], context["protocol"], context["host"], context["port"],
        context["base_path"], context["sync_endpoint"],
    )
    logger.info("[BOOT] COMPANY_CNPJ=%s", mask_cnpj(COMPANY_CNPJ))
    logger.info("[BOOT] API_TOKEN=%s", mask_token(API_TOKEN))
    logger.info(
        "[BOOT] FB_HOST=%s | FB_PORT=%s | FB_DATABASE=%s | client_configured=%s",
        FB_HOST, FB_PORT, Path(FB_DATABASE).name if FB_DATABASE else "(nao configurado)", bool(FB_CLIENT_PATH),
    )


_fb_client_loaded = False


def require_env():
    missing = [
        name
        for name, value in {
            "FB_DATABASE": FB_DATABASE,
            "FB_USER": FB_USER,
            "FB_PASS": FB_PASS,
            "API_BASE_URL": API_BASE_URL,
            "API_TOKEN": API_TOKEN,
            "COMPANY_CNPJ": COMPANY_CNPJ,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Variaveis obrigatorias ausentes: {', '.join(missing)}")


def get_db_connection():
    global _fb_client_loaded
    require_env()
    if FB_CLIENT_PATH and not _fb_client_loaded:
        fdb.load_api(FB_CLIENT_PATH)
        _fb_client_loaded = True
        logger.info("DLL do Firebird carregada.")
    return fdb.connect(
        host=FB_HOST,
        port=FB_PORT,
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASS,
        charset="WIN1252",
    )


def normalize_identifier(value):
    return str(value or "").strip().upper()


def to_json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class FirebirdSchema:
    def __init__(self, conn):
        self.conn = conn
        self.tables = set()
        self.columns = {}
        self.primary_keys = {}
        self.foreign_keys = {}

    def load(self):
        start = time.perf_counter()
        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT TRIM(RDB$RELATION_NAME)
            FROM RDB$RELATIONS
            WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
              AND RDB$VIEW_BLR IS NULL
            ORDER BY RDB$RELATION_NAME
            """
        )
        self.tables = {normalize_identifier(row[0]) for row in cur.fetchall()}

        cur.execute(
            """
            SELECT
                TRIM(rf.RDB$RELATION_NAME) AS TABLE_NAME,
                TRIM(rf.RDB$FIELD_NAME) AS FIELD_NAME
            FROM RDB$RELATION_FIELDS rf
            JOIN RDB$RELATIONS r
              ON r.RDB$RELATION_NAME = rf.RDB$RELATION_NAME
            WHERE COALESCE(r.RDB$SYSTEM_FLAG, 0) = 0
            ORDER BY rf.RDB$RELATION_NAME, rf.RDB$FIELD_POSITION
            """
        )
        for table_name, field_name in cur.fetchall():
            table = normalize_identifier(table_name)
            field = normalize_identifier(field_name)
            self.columns.setdefault(table, []).append(field)

        cur.execute(
            """
            SELECT
                TRIM(rc.RDB$RELATION_NAME) AS TABLE_NAME,
                TRIM(s.RDB$FIELD_NAME) AS FIELD_NAME
            FROM RDB$RELATION_CONSTRAINTS rc
            JOIN RDB$INDEX_SEGMENTS s
              ON s.RDB$INDEX_NAME = rc.RDB$INDEX_NAME
            WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY rc.RDB$RELATION_NAME, s.RDB$FIELD_POSITION
            """
        )
        for table_name, field_name in cur.fetchall():
            self.primary_keys.setdefault(normalize_identifier(table_name), []).append(normalize_identifier(field_name))

        cur.execute(
            """
            SELECT
                TRIM(rc.RDB$RELATION_NAME) AS TABLE_NAME,
                TRIM(seg.RDB$FIELD_NAME) AS FIELD_NAME,
                TRIM(refc.RDB$RELATION_NAME) AS REF_TABLE,
                TRIM(refseg.RDB$FIELD_NAME) AS REF_FIELD
            FROM RDB$RELATION_CONSTRAINTS rc
            JOIN RDB$REF_CONSTRAINTS refs
              ON refs.RDB$CONSTRAINT_NAME = rc.RDB$CONSTRAINT_NAME
            JOIN RDB$RELATION_CONSTRAINTS refc
              ON refc.RDB$CONSTRAINT_NAME = refs.RDB$CONST_NAME_UQ
            JOIN RDB$INDEX_SEGMENTS seg
              ON seg.RDB$INDEX_NAME = rc.RDB$INDEX_NAME
            JOIN RDB$INDEX_SEGMENTS refseg
              ON refseg.RDB$INDEX_NAME = refc.RDB$INDEX_NAME
             AND refseg.RDB$FIELD_POSITION = seg.RDB$FIELD_POSITION
            WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'
            ORDER BY rc.RDB$RELATION_NAME, rc.RDB$CONSTRAINT_NAME, seg.RDB$FIELD_POSITION
            """
        )
        for table_name, field_name, ref_table, ref_field in cur.fetchall():
            table = normalize_identifier(table_name)
            self.foreign_keys.setdefault(table, []).append(
                {
                    "field": normalize_identifier(field_name),
                    "ref_table": normalize_identifier(ref_table),
                    "ref_field": normalize_identifier(ref_field),
                }
            )

        elapsed = time.perf_counter() - start
        logger.info("[DIAGNOSTICO] Schema Firebird carregado: %s tabelas em %.3fs", len(self.tables), elapsed)
        return self

    def has_table(self, table_name):
        return normalize_identifier(table_name) in self.tables

    def table_columns(self, table_name):
        return self.columns.get(normalize_identifier(table_name), [])

    def has_column(self, table_name, column_name):
        return normalize_identifier(column_name) in self.table_columns(table_name)

    def first_table(self, candidates):
        for table in candidates:
            if self.has_table(table):
                return normalize_identifier(table)
        return None

    def first_column(self, table_name, candidates):
        table_columns = set(self.table_columns(table_name))
        for column in candidates:
            normalized = normalize_identifier(column)
            if normalized in table_columns:
                return normalized
        return None

    def write_diagnostics(self, used_tables):
        payload = {
            "generated_at": datetime.now().isoformat(),
            "tables": sorted(self.tables),
            "used_tables": {
                table: {
                    "columns": self.table_columns(table),
                    "primary_keys": self.primary_keys.get(normalize_identifier(table), []),
                    "foreign_keys": self.foreign_keys.get(normalize_identifier(table), []),
                }
                for table in sorted({normalize_identifier(t) for t in used_tables if t})
            },
            "primary_keys": self.primary_keys,
            "foreign_keys": self.foreign_keys,
        }
        with open(DIAGNOSTIC_FILE, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        logger.info("[DIAGNOSTICO] Arquivo gerado: %s", DIAGNOSTIC_FILE)


def execute_select(conn, sql, params=None, table_name=None):
    start = time.perf_counter()
    query_id = hashlib.sha256(" ".join(sql.split()).encode()).hexdigest()[:12]
    logger.info("[SQL] Tabela=%s | query_id=%s", table_name or "-", query_id)
    cur = conn.cursor()
    try:
        cur.execute(sql, params or [])
        columns = [normalize_identifier(col[0]) for col in cur.description]
        rows = []
        for row in cur.fetchall():
            rows.append({columns[index]: to_json_value(value) for index, value in enumerate(row)})
        elapsed = time.perf_counter() - start
        logger.info("[SQL] Tabela=%s | Registros=%s | Tempo=%.3fs", table_name or "-", len(rows), elapsed)
        return rows
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("[SQL] Erro em tabela=%s apos %.3fs", table_name or "-", elapsed)
        raise


def send_to_dashboard(data_type, content):
    if not COMPANY_CNPJ or not API_TOKEN:
        logger.error("CNPJ ou API_TOKEN nao configurados")
        return SEND_PERMANENT_FAILURE

    payload = {
        "cnpj": COMPANY_CNPJ,
        "type": data_type,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    url = remote_endpoint("sync")
    record_count = len(content) if isinstance(content, list) else 0
    payload_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:12]

    for attempt, base_delay in enumerate((0, 5, 15), start=1):
        if base_delay:
            time.sleep(base_delay + random.uniform(0, 1.5))
        start = time.perf_counter()
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=(10, 300))
            elapsed = time.perf_counter() - start
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning(
                "[API] falha transitória type=%s attempt=%s error=%s",
                data_type, attempt, type(exc).__name__,
            )
            continue
        except requests.RequestException as exc:
            logger.error("[API] falha permanente type=%s error=%s", data_type, type(exc).__name__)
            return SEND_PERMANENT_FAILURE

        if response.status_code == 200:
            try:
                confirmation = response.json()
            except ValueError:
                logger.error("[API] confirmação inválida type=%s: resposta não JSON", data_type)
                return SEND_PERMANENT_FAILURE

            if (
                confirmation.get("success") is True
                and confirmation.get("tenant_id")
                and int(confirmation.get("received", -1)) == record_count
            ):
                logger.info(
                    "[API] confirmado type=%s records=%s bytes=%s hash=%s elapsed=%.3fs",
                    data_type, record_count, payload_bytes, payload_hash, elapsed,
                )
                return SEND_SUCCESS
            logger.error("[API] confirmação rejeitada type=%s HTTP=200", data_type)
            return SEND_PERMANENT_FAILURE

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            logger.warning(
                "[API] falha transitória type=%s attempt=%s status=%s",
                data_type, attempt, response.status_code,
            )
            continue

        logger.error(
            "[API] falha permanente type=%s status=%s response_bytes=%s",
            data_type, response.status_code, len(response.content),
        )
        return SEND_PERMANENT_FAILURE

    return SEND_RETRYABLE_FAILURE


def diagnose_remote():
    require_env()
    public_health = remote_endpoint("health")
    auth_health = remote_endpoint("sync/health")
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    logger.info("[DIAGNOSTICO] iniciando conectividade remota")
    try:
        response = requests.get(public_health, timeout=(10, 20))
        payload = response.json()
        if response.status_code != 200 or payload.get("status") != "ok":
            logger.error("[DIAGNOSTICO] health público inválido status=%s", response.status_code)
            return False

        response = requests.get(
            auth_health,
            params={"cnpj": COMPANY_CNPJ},
            headers=headers,
            timeout=(10, 20),
        )
        if response.status_code != 200:
            logger.error("[DIAGNOSTICO] autenticação falhou status=%s", response.status_code)
            return False
        payload = response.json()
        logger.info(
            "[DIAGNOSTICO] remoto disponível auth=%s tenant_resolved=%s",
            payload.get("authenticated") is True,
            bool(payload.get("tenant_id")),
        )
        return payload.get("authenticated") is True and bool(payload.get("tenant_id"))
    except (requests.RequestException, ValueError) as exc:
        logger.error("[DIAGNOSTICO] falha type=%s", type(exc).__name__)
        return False


GENERIC_TABLES = [
    {"table": "TB_EMPRESA", "columns": ["EMP_ID", "EMP_FANTASIA", "EMP_RAZAO_SOCIAL", "EMP_CNPJ"]},
    {"table": "TB_PEDIDO_VENDA", "columns": ["PEV_ID", "PEV_EMPRESA", "PEV_CLIENTE", "PEV_VENDEDOR", "PEV_DT_EMISSAO", "PEV_DT_FATURAMENTO", "PEV_DT_LANCAMENTO", "PEV_VALOR_TOTAL", "PEV_STATUS"], "date_column": "PEV_DT_LANCAMENTO", "filter_first_run": True},
    {"table": "TB_PEDIDO_VENDA_ITEM", "columns": ["PEVI_ID", "PEVI_PEDIDO_VENDA", "PEVI_EMPRESA", "PEVI_PRODUTO", "PEVI_QUANTIDADE", "PEVI_VALOR_UNITARIO", "PEVI_VALOR_CUSTO_UNITARIO", "PEVI_VALOR_TOTAL"], "where": "PEVI_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= ?)"},
    {"table": "TB_PESSOA", "columns": ["PES_ID", "PES_RSOCIAL_NOME", "PES_FANTASIA_APELIDO", "PES_CIDADE", "PES_DT_CADASTRO", "PES_EMAIL", "PES_TELEFONE", "PES_CELULAR", "PES_VENDEDOR"], "date_column": "PES_DT_CADASTRO", "filter_first_run": False},
    {"table": "TB_CLIENTE", "columns": ["CLI_PESSOA", "CLI_EMPRESA"]},
    {"table": "TB_VENDEDOR", "columns": ["VDR_PESSOA"]},
    {"table": "TB_CIDADE", "columns": ["CID_ID", "CID_NOME"]},
    {"table": "TB_PRODUTO", "columns": ["PRD_ID", "PRD_EMPRESA", "PRD_DESCRICAO", "PRD_GRUPO", "PRD_MARCA", "PRD_STATUS", "PRD_ESTOQUE_MINIMO", "PRD_PRECO_VENDA", "PRD_PRECO_CUSTO"]},
    {"table": "TB_USUARIO", "columns": ["USU_ID", "USU_LOGIN", "USU_NOME", "USU_SENHA", "USU_ADMINISTRADOR"]},
    {"table": "TB_PRODUTO_ESTOQUE", "columns": ["PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_ESTOQUE"]},
    {"table": "TB_PROD_GRUPO", "columns": ["PGRU_ID", "PGRU_DESCRICAO"]},
    {"table": "TB_PROD_MARCA", "columns": ["PMAR_ID", "PMAR_DESCRICAO"]},
    {"table": "TB_ESPECIE_MOEDA", "columns": ["ESP_ID", "ESP_DESCRICAO"]},
    {"table": "TB_PEDIDO_VENDA_FIN", "columns": ["PEVF_PEDIDO_VENDA", "PEVF_ID", "PEVF_EMPRESA", "PEVF_ESPECIE_MOEDA", "PEVF_VALOR"], "where": "PEVF_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= ?)"},
    {"table": "TB_COLABORADOR", "columns": ["COL_PESSOA", "COL_EMPRESA", "COL_CARGO", "COL_STATUS"]},
    {"table": "TB_AUDITORIA", "columns": ["AUD_EMPRESA", "AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA", "AUD_ACAO", "AUD_DT_LANCAMENTO", "AUD_DT_ACAO", "AUD_USUARIO", "AUD_TABELA_DESC", "AUD_DESC_REGISTRO"], "date_column": "AUD_DT_LANCAMENTO", "filter_first_run": True},
]


FINANCIAL_MAPPINGS = {
    "TB_RECEBIMENTO": {
        "table_candidates": ["TB_RECEBIMENTO", "TB_CONTAS_RECEBER", "TB_CONTA_RECEBER", "TB_TITULO_RECEBER", "TB_RECEBER"],
        "fields": {
            "REC_ID": ["REC_ID", "CR_ID", "CRE_ID", "CTR_ID", "TIT_ID", "ID"],
            "REC_EMPRESA": ["REC_EMPRESA", "CR_EMPRESA", "CRE_EMPRESA", "CTR_EMPRESA", "EMPRESA", "ID_EMPRESA"],
            "REC_PESSOA": ["REC_PESSOA", "CR_PESSOA", "CRE_PESSOA", "CTR_PESSOA", "PES_ID", "CLIENTE", "ID_PESSOA"],
            "REC_DT_EMISSAO": ["REC_DT_EMISSAO", "CR_DT_EMISSAO", "CRE_DT_EMISSAO", "CTR_DT_EMISSAO", "DATA_EMISSAO", "DT_EMISSAO"],
            "REC_DT_VENCIMENTO": ["REC_DT_VENCIMENTO", "CR_DT_VENCIMENTO", "CRE_DT_VENCIMENTO", "CTR_DT_VENCIMENTO", "DATA_VENCIMENTO", "DT_VENCIMENTO"],
            "REC_VALOR": ["REC_VALOR", "CR_VALOR", "CRE_VALOR", "CTR_VALOR", "VALOR", "VALOR_TOTAL", "VALOR_DOCUMENTO"],
            "REC_STATUS": ["REC_STATUS", "CR_STATUS", "CRE_STATUS", "CTR_STATUS", "STATUS"],
            "REC_ABERTO": ["REC_ABERTO", "CR_ABERTO", "CRE_ABERTO", "CTR_ABERTO", "ABERTO"],
        },
        "date_filter": "REC_DT_EMISSAO",
    },
    "TB_PAGAMENTO": {
        "table_candidates": ["TB_PAGAMENTO", "TB_CONTAS_PAGAR", "TB_CONTA_PAGAR", "TB_TITULO_PAGAR", "TB_PAGAR"],
        "fields": {
            "PAG_ID": ["PAG_ID", "CP_ID", "CPA_ID", "CTP_ID", "TIT_ID", "ID"],
            "PAG_EMPRESA": ["PAG_EMPRESA", "CP_EMPRESA", "CPA_EMPRESA", "CTP_EMPRESA", "EMPRESA", "ID_EMPRESA"],
            "PAG_PESSOA": ["PAG_PESSOA", "CP_PESSOA", "CPA_PESSOA", "CTP_PESSOA", "PES_ID", "FORNECEDOR", "ID_PESSOA"],
            "PAG_DT_VENCIMENTO": ["PAG_DT_VENCIMENTO", "CP_DT_VENCIMENTO", "CPA_DT_VENCIMENTO", "CTP_DT_VENCIMENTO", "DATA_VENCIMENTO", "DT_VENCIMENTO"],
            "PAG_VALOR": ["PAG_VALOR", "CP_VALOR", "CPA_VALOR", "CTP_VALOR", "VALOR", "VALOR_TOTAL", "VALOR_DOCUMENTO"],
            "PAG_STATUS": ["PAG_STATUS", "CP_STATUS", "CPA_STATUS", "CTP_STATUS", "STATUS"],
            "PAG_ABERTO": ["PAG_ABERTO", "CP_ABERTO", "CPA_ABERTO", "CTP_ABERTO", "ABERTO"],
        },
        "date_filter": "PAG_DT_VENCIMENTO",
    },
}


FINANCIAL_RELATED_TABLES = {
    "pessoas": ["TB_PESSOA"],
    "contas": ["TB_CONTA", "TB_CONTAS", "TB_ESPECIE_MOEDA", "TB_CONTA_CORRENTE"],
    "plano_contas": ["TB_PLANO_CONTA", "TB_PLANO_CONTAS", "TB_PLANO_CONTA_FINANCEIRO", "TB_CENTRO_CUSTO"],
    "borderos": ["TB_BORDERO", "TB_BORDEROS", "TB_BORDERO_RECEBIMENTO", "TB_BORDERO_PAGAMENTO"],
    "movimentos_financeiros": ["TB_MOVIMENTO_FINANCEIRO", "TB_MOV_FINANCEIRO", "TB_FIN_MOVIMENTO", "TB_CAIXA_MOVIMENTO"],
}


def resolve_financial_mapping(schema, canonical_table):
    mapping = FINANCIAL_MAPPINGS[canonical_table]
    actual_table = schema.first_table(mapping["table_candidates"])
    if not actual_table:
        logger.error(
            "[FINANCEIRO] Nenhuma tabela equivalente encontrada para %s. Candidatas: %s",
            canonical_table,
            ", ".join(mapping["table_candidates"]),
        )
        return None

    if actual_table != canonical_table:
        logger.warning("[FINANCEIRO] %s nao encontrada/nao usada; equivalente selecionada: %s", canonical_table, actual_table)
    else:
        logger.info("[FINANCEIRO] Tabela utilizada: %s", actual_table)

    field_map = {}
    missing = []
    for canonical_field, candidates in mapping["fields"].items():
        actual_field = schema.first_column(actual_table, candidates)
        if actual_field:
            field_map[canonical_field] = actual_field
        else:
            missing.append(canonical_field)

    required = [field for field in mapping["fields"] if field.endswith("_ID") or field.endswith("_VALOR")]
    missing_required = [field for field in required if field not in field_map]
    if missing_required:
        logger.error("[FINANCEIRO] Campos obrigatorios ausentes em %s: %s", actual_table, ", ".join(missing_required))
        return None

    if missing:
        logger.warning("[FINANCEIRO] Campos opcionais ausentes em %s: %s", actual_table, ", ".join(missing))

    return {"actual_table": actual_table, "field_map": field_map, "canonical_table": canonical_table}


def fetch_generic_table(conn, schema, spec, data_corte, is_first_run):
    table_name = spec["table"]
    columns = spec["columns"]
    if not schema.has_table(table_name):
        logger.warning("[SYNC] Tabela ignorada porque nao existe no ERP: %s", table_name)
        return []

    available_columns = [column for column in columns if schema.has_column(table_name, column)]
    missing_columns = [column for column in columns if column not in available_columns]
    if missing_columns:
        logger.warning("[SYNC] %s sem campos: %s", table_name, ", ".join(missing_columns))

    if not available_columns:
        logger.warning("[SYNC] Tabela %s ignorada sem colunas compativeis", table_name)
        return []

    sql = f"SELECT {', '.join(available_columns)} FROM {table_name}"
    params = []
    if spec.get("where"):
        sql += f" WHERE {spec['where']}"
        params.append(data_corte)
    else:
        date_filter_column = spec.get("date_column")
        should_filter = date_filter_column and (not is_first_run or spec.get("filter_first_run"))
        if should_filter and schema.has_column(table_name, date_filter_column):
            sql += f" WHERE {date_filter_column} >= ?"
            params.append(data_corte)

    return execute_select(conn, sql, params, table_name)


def fetch_financial_table(conn, schema, canonical_table, data_corte, is_first_run):
    resolved = resolve_financial_mapping(schema, canonical_table)
    if not resolved:
        return []

    actual_table = resolved["actual_table"]
    field_map = resolved["field_map"]
    mapping = FINANCIAL_MAPPINGS[canonical_table]

    select_parts = []
    for canonical_field in mapping["fields"]:
        actual_field = field_map.get(canonical_field)
        if actual_field:
            select_parts.append(f"{actual_field} AS {canonical_field}")
        else:
            select_parts.append(f"NULL AS {canonical_field}")

    sql = f"SELECT {', '.join(select_parts)} FROM {actual_table}"
    params = []
    canonical_date = mapping["date_filter"]
    actual_date = field_map.get(canonical_date)
    if actual_date:
        sql += f" WHERE {actual_date} >= ?"
        params.append(data_corte)

    return execute_select(conn, sql, params, actual_table)


def run_schema_diagnostics(conn, schema, used_tables):
    logger.info("[DIAGNOSTICO] Listando tabelas, campos, PKs e FKs do Firebird")
    for table in sorted(used_tables):
        if not table:
            continue
        logger.info(
            "[DIAGNOSTICO] %s | Campos=%s | PK=%s | FK=%s",
            table,
            ", ".join(schema.table_columns(table)),
            ", ".join(schema.primary_keys.get(table, [])),
            json.dumps(schema.foreign_keys.get(table, []), ensure_ascii=False),
        )
    schema.write_diagnostics(used_tables)


def run_sync():
    logger.info("=== Iniciando sincronismo P.I.G.O ===")
    state_file = "sync_state.json"
    is_first_run = not os.path.exists(state_file)
    data_corte = "2025-01-01" if is_first_run else (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    logger.info("Modo=%s | Data corte=%s", "CARGA_HISTORICA" if is_first_run else "INCREMENTAL", data_corte)

    conn = None
    success_all = True
    permanent_failure = False
    try:
        conn = get_db_connection()
        schema = FirebirdSchema(conn).load()

        resolved_financial_tables = []
        for canonical_table in FINANCIAL_MAPPINGS:
            resolved = resolve_financial_mapping(schema, canonical_table)
            if resolved:
                resolved_financial_tables.append(resolved["actual_table"])

        related_tables = []
        for label, candidates in FINANCIAL_RELATED_TABLES.items():
            related = schema.first_table(candidates)
            if related:
                related_tables.append(related)
                logger.info("[DIAGNOSTICO] Tabela relacionada '%s' encontrada: %s", label, related)
            else:
                logger.warning("[DIAGNOSTICO] Nenhuma tabela relacionada encontrada para '%s'. Candidatas: %s", label, ", ".join(candidates))

        used_tables = [spec["table"] for spec in GENERIC_TABLES if schema.has_table(spec["table"])] + resolved_financial_tables + related_tables
        run_schema_diagnostics(conn, schema, used_tables)

        for spec in GENERIC_TABLES:
            table_name = spec["table"]
            if table_name in FINANCIAL_MAPPINGS:
                continue
            rows = fetch_generic_table(conn, schema, spec, data_corte, is_first_run)
            if rows:
                send_result = send_to_dashboard(table_name, rows)
                if send_result != SEND_SUCCESS:
                    success_all = False
                    permanent_failure = send_result == SEND_PERMANENT_FAILURE
                    if permanent_failure:
                        logger.error("[SYNC] ciclo interrompido por falha permanente")
                        break
            elif not rows:
                logger.info("[SYNC] %s sem dados para envio", table_name)

        for canonical_table in (() if permanent_failure else FINANCIAL_MAPPINGS):
            rows = fetch_financial_table(conn, schema, canonical_table, data_corte, is_first_run)
            if rows:
                send_result = send_to_dashboard(canonical_table, rows)
                if send_result != SEND_SUCCESS:
                    success_all = False
                    permanent_failure = send_result == SEND_PERMANENT_FAILURE
                    if permanent_failure:
                        logger.error("[SYNC] ciclo interrompido por falha permanente")
                        break
            elif not rows:
                logger.info("[FINANCEIRO] %s sem dados para envio", canonical_table)

        if success_all and is_first_run:
            with open(state_file, "w", encoding="utf-8") as file:
                json.dump({"last_full_sync": datetime.now().isoformat(), "initial_load_complete": True}, file)
            logger.info("Carga historica finalizada e registrada.")

    except Exception:
        success_all = False
        logger.exception("Erro geral no sincronismo")
    finally:
        if conn:
            conn.close()

    logger.info("=== Ciclo finalizado | sucesso=%s ===", success_all)
    return success_all


def start_agent():
    logger.info("AGENTE P.I.G.O ATIVO")
    log_startup_context()

    def run_when_available():
        if diagnose_remote():
            return run_sync()
        logger.error("Diagnóstico remoto falhou; coleta pesada adiada para o próximo ciclo.")
        return False

    run_when_available()
    schedule.every(SYNC_INTERVAL).minutes.do(run_when_available)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        log_startup_context()
        raise SystemExit(0 if diagnose_remote() else 1)
    start_agent()
