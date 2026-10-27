import json
import hashlib
import logging
import locale
import os
import random
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

# O Python embutido usa pythonXY._pth e pode não adicionar a pasta do script
# ao sys.path quando agent.py é executado diretamente.
_AGENT_BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENT_BOOTSTRAP_DIR not in sys.path:
    sys.path.insert(0, _AGENT_BOOTSTRAP_DIR)

# Compatibilidade do fdb 2.0.2 com Python 3.13, que removeu locale.resetlocale.
if not hasattr(locale, "resetlocale"):
    def _resetlocale(category=locale.LC_ALL):
        return locale.setlocale(category, "")

    locale.resetlocale = _resetlocale

import requests
import schedule
from dotenv import load_dotenv
from credential_store import CredentialStore, CredentialStoreError
from firebird_provider import create_provider
from resolved_config import ResolvedAgentConfig
from owner import AgentOwner, NamedPipeServer, RequestAuthenticator, PROTOCOL_VERSION, PIPE_NAME
from writeback import poll_commands
from operational_sync import fetch_operational, operational_plans
from sync_engine import TablePlan, SyncEngine, Progress, SyncPaused, canonical

PROGRAM_DATA = Path(os.getenv("PROGRAMDATA", "C:/ProgramData"))
DATA_DIR = Path(os.getenv("PIGO_REMOTE_SYNC_DATA_DIR", PROGRAM_DATA / "PIGO Remote Sync"))
CONFIG_FILE = DATA_DIR / "config.json"
CREDENTIAL_FILE = DATA_DIR / "credentials.dat"
INSTALLATION_FILE = DATA_DIR / "installation.json"
LEGACY_CREDENTIAL_FILE = PROGRAM_DATA / "PIGO Agent" / "credentials.json"
if not CONFIG_FILE.exists() and not CREDENTIAL_FILE.exists() and LEGACY_CREDENTIAL_FILE.exists():
    CREDENTIAL_FILE = LEGACY_CREDENTIAL_FILE
    INSTALLATION_FILE = LEGACY_CREDENTIAL_FILE.parent / "installation.json"
LOG_DIR = DATA_DIR / "logs"
DIAGNOSTIC_DIR = DATA_DIR / "diagnostics"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

AGENT_VERSION = "2026.10.27-r2-erp-barcode-schema-sync-v2-writeback-off"
AGENT_FILE = Path(__file__).resolve()
AGENT_DIR = AGENT_FILE.parent
ENV_FILE = AGENT_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=False)

DIAGNOSTIC_FILE = os.getenv("SCHEMA_DIAGNOSTIC_FILE", "schema_diagnostics.json")
SEND_SUCCESS = "success"
SEND_RETRYABLE_FAILURE = "retryable_failure"
SEND_PERMANENT_FAILURE = "permanent_failure"
CREDENTIAL_STORE = CredentialStore(CREDENTIAL_FILE, INSTALLATION_FILE)
SYNC_PROGRESS_CALLBACK = None
SYNC_PAUSE_CALLBACK = None
REMOTE_SYNC_PROTOCOL = None
REMOTE_SYNC_TENANT_ID = None
_BATCH_HTTP = requests.Session()
CONFIG = ResolvedAgentConfig.resolve(CONFIG_FILE, ENV_FILE, CREDENTIAL_STORE)
DESKTOP_CONFIG = CONFIG.mode == "desktop"
FB_HOST, FB_PORT, FB_DATABASE = CONFIG.firebird_host, CONFIG.firebird_port, CONFIG.firebird_database
FB_USER, FB_PASS = CONFIG.firebird_user, CONFIG.firebird_password
FB_CLIENT_PATH, FB_CHARSET, FB_DRIVER = CONFIG.firebird_client_path, CONFIG.firebird_charset, CONFIG.firebird_driver
API_BASE_URL, COMPANY_CNPJ = CONFIG.api_base_url, CONFIG.company_cnpj
LICENSE_API_KEY, SYNC_INTERVAL = CONFIG.license_api_key, CONFIG.sync_interval_minutes
API_TOKEN = os.getenv("API_TOKEN") if CONFIG.mode == "legacy" else None


def active_api_token():
    return API_TOKEN or CONFIG.remote_sync_token


def remote_sync_headers():
    headers = {"Authorization": f"Bearer {active_api_token()}"}
    if not API_TOKEN:
        headers["X-Installation-Id"] = CREDENTIAL_STORE.installation_id()
    return headers


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
        "source": str(CONFIG_FILE if DESKTOP_CONFIG else ENV_FILE),
        "protocol": parsed.scheme or "(ausente)",
        "host": parsed.hostname or "(ausente)",
        "port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "base_path": parsed.path or "/",
        "sync_endpoint": urlsplit(remote_endpoint("sync")).path,
    }


def sanitized_api_error(response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    if isinstance(body.get("detail"), dict):
        body = body["detail"]
    return {
        "code": str(body.get("code") or "HTTP_ERROR"),
        "message": str(body.get("message") or "Requisicao recusada pelo servidor."),
        "request_id": str(
            body.get("request_id")
            or response.headers.get("X-Trace-Id")
            or "(ausente)"
        ),
    }


def log_startup_context():
    logger.info("[BOOT] Agente P.I.G.O versao=%s", AGENT_VERSION)
    logger.info("[BOOT] agent.py=%s", AGENT_FILE)
    logger.info("[CONFIG] configuration_mode=%s", CONFIG.mode)
    logger.info("[CONFIG] data_dir=%s", DATA_DIR)
    logger.info("[CONFIG] configuration_source=%s", CONFIG_FILE if DESKTOP_CONFIG else ENV_FILE)
    logger.info("[CONFIG] config_found=%s", CONFIG_FILE.exists())
    logger.info("[CREDENTIALS] store_found=%s", CREDENTIAL_FILE.exists())
    logger.info("[CREDENTIALS] license_key_present=%s", bool(LICENSE_API_KEY))
    logger.info("[CREDENTIALS] remote_sync_token_present=%s", bool(active_api_token()))
    logger.info("[CREDENTIALS] firebird_password_present=%s", bool(CONFIG.firebird_password))
    logger.info("[CONFIG] firebird_host_present=%s", bool(CONFIG.firebird_host))
    logger.info("[CONFIG] firebird_database_present=%s", bool(CONFIG.firebird_database))
    logger.info("[FIREBIRD] runtime=%s", CONFIG.runtime_architecture or ("x64" if sys.maxsize > 2**32 else "x86"))
    logger.info("[BOOT] Python=%s", sys.executable)
    context = sanitized_remote_context()
    logger.info(
        "[BOOT] remote source=%s protocol=%s host=%s port=%s base_path=%s endpoint=%s",
        context["source"], context["protocol"], context["host"], context["port"],
        context["base_path"], context["sync_endpoint"],
    )


def log_process_identity(start_reason, owner=None):
    identity = owner.process_identity() if owner else {
        "pid": os.getpid(), "instance_id": uuid.uuid4().hex[:8],
        "session_id": str(uuid.uuid4()), "mode": "command",
        "start_reason": start_reason, "service_mode": False,
        "owner_type": "none", "loop_id": "none",
    }
    logger.info("[PROCESS] PID=%s INSTANCE_ID=%s SESSION_ID=%s MODE=%s START_REASON=%s SERVICE_MODE=%s OWNER_TYPE=%s LOOP_ID=%s",identity["pid"],identity["instance_id"],identity["session_id"],identity["mode"],identity["start_reason"],identity["service_mode"],identity["owner_type"],identity["loop_id"])
    logger.info("[BOOT] COMPANY_CNPJ=%s", mask_cnpj(COMPANY_CNPJ))
    token_source = "environment" if API_TOKEN else "credential-store" if active_api_token() else "missing"
    logger.info("[BOOT] remote_sync_token=(%s)", token_source)
    logger.info(
        "[BOOT] FB_HOST=%s | FB_PORT=%s | FB_DATABASE=%s | client_configured=%s",
        FB_HOST, FB_PORT, Path(FB_DATABASE).name if FB_DATABASE else "(nao configurado)", bool(FB_CLIENT_PATH),
    )


_firebird_provider = None


def require_remote_env():
    missing = [
        name
        for name, value in {
            "API_BASE_URL": API_BASE_URL,
            "COMPANY_CNPJ": COMPANY_CNPJ,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Variaveis obrigatorias ausentes: {', '.join(missing)}")


def require_env():
    require_remote_env()
    CONFIG.validate_firebird()


def get_db_connection():
    global _firebird_provider
    require_env()
    if _firebird_provider is None:
        _firebird_provider = create_provider(FB_DRIVER)
        logger.info("[FIREBIRD] provider=%s", _firebird_provider.name)
    return _firebird_provider.connect(CONFIG.firebird_settings())


def test_firebird_connection():
    """Small read-only validation; never starts a synchronization cycle."""
    conn = None
    result = {"success": False, "provider": FB_DRIVER, "steps": []}
    def step(name, ok, detail=""):
        result["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
    try:
        conn = get_db_connection()
        step("connect", True, "Conexao estabelecida")
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM RDB$DATABASE")
        step("select", cur.fetchone()[0] == 1, "SELECT simples")
        version = "desconhecida"
        try:
            cur.execute("SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION') FROM RDB$DATABASE")
            version = str(cur.fetchone()[0]).strip()
        except Exception:
            version = str(getattr(conn, "engine_version", "desconhecida"))
        step("server-version", bool(version), version)
        cur.execute("SELECT COUNT(*) FROM RDB$RELATIONS WHERE TRIM(RDB$RELATION_NAME) = 'TB_EMPRESA'")
        has_company = int(cur.fetchone()[0]) > 0
        step("tb-empresa", has_company, "Tabela encontrada" if has_company else "Tabela ausente")
        if has_company:
            cur.execute("SELECT FIRST 1 * FROM TB_EMPRESA")
            cur.fetchone()
            step("tb-empresa-read", True, "Leitura concluida")
        result["success"] = all(item["ok"] for item in result["steps"])
    except Exception as exc:
        # Type and stage are useful; messages from drivers may echo paths/users.
        step("connection", False, type(exc).__name__)
        result["error_type"] = type(exc).__name__
    finally:
        if conn:
            conn.close()
            step("close", True, "Conexao encerrada")
    return result


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
            "columns": self.columns,
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
        target = Path(DIAGNOSTIC_FILE)
        if not target.is_absolute():
            target = DIAGNOSTIC_DIR / target
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        logger.info("[DIAGNOSTICO] Arquivo gerado: %s", target)
        return str(target)


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
    token = active_api_token()
    if not COMPANY_CNPJ or not token:
        logger.error("CNPJ ou credencial Remote Sync nao configurados")
        return SEND_PERMANENT_FAILURE

    payload = {
        "cnpj": COMPANY_CNPJ,
        "type": data_type,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    headers = {**remote_sync_headers(), "Content-Type": "application/json"}

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
            "[API] falha permanente type=%s status=%s code=%s message=%s "
            "request_id=%s response_bytes=%s",
            data_type,
            response.status_code,
            sanitized_api_error(response)["code"],
            sanitized_api_error(response)["message"],
            sanitized_api_error(response)["request_id"],
            len(response.content),
        )
        return SEND_PERMANENT_FAILURE

    return SEND_RETRYABLE_FAILURE


def _diagnose_remote_legacy():
    require_remote_env()
    token = active_api_token()
    if not token:
        logger.error("[DIAGNOSTICO] agente ainda nao ativado")
        return False
    public_health = remote_endpoint("health")
    auth_health = remote_endpoint("sync/health")
    headers = remote_sync_headers()
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
            error = sanitized_api_error(response)
            logger.error(
                "[DIAGNOSTICO] autenticação falhou status=%s code=%s message=%s request_id=%s",
                response.status_code,
                error["code"],
                error["message"],
                error["request_id"],
            )
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


def diagnose_remote_result():
    global REMOTE_SYNC_PROTOCOL, REMOTE_SYNC_TENANT_ID
    REMOTE_SYNC_PROTOCOL = None
    REMOTE_SYNC_TENANT_ID = None
    try:
        require_remote_env()
    except RuntimeError:
        return {"success": False, "authenticated": False, "tenant_resolved": False, "code": "REMOTE_CONFIG_INVALID", "retryable": False}
    if not active_api_token():
        return {"success": False, "authenticated": False, "tenant_resolved": False, "code": "REMOTE_TOKEN_MISSING", "retryable": False}
    try:
        public = requests.get(remote_endpoint("health"), timeout=(10, 20))
        public_payload = public.json()
        if public.status_code != 200 or public_payload.get("status") != "ok":
            return {"success": False, "authenticated": False, "tenant_resolved": False, "code": "PUBLIC_HEALTH_UNAVAILABLE", "http_status": public.status_code, "retryable": True}
        response = requests.get(
            remote_endpoint("sync/health"),
            params={"cnpj": COMPANY_CNPJ},
            headers=remote_sync_headers(),
            timeout=(10, 20),
        )
        if response.status_code != 200:
            error = sanitized_api_error(response)
            logger.error("[DIAGNOSTICO] autenticacao falhou status=%s code=%s request_id=%s", response.status_code, error["code"], error["request_id"])
            return {"success": False, "authenticated": False, "tenant_resolved": False, "code": error["code"], "http_status": response.status_code, "retryable": response.status_code >= 500}
        payload = response.json()
        REMOTE_SYNC_PROTOCOL = payload.get("protocol_version", 1)
        REMOTE_SYNC_TENANT_ID = payload.get("tenant_id")
        authenticated = payload.get("authenticated") is True
        tenant_resolved = bool(payload.get("tenant_id") or payload.get("tenant_resolved"))
        logger.info("[DIAGNOSTICO] remoto disponivel auth=%s tenant_resolved=%s", authenticated, tenant_resolved)
        return {"success": authenticated and tenant_resolved, "authenticated": authenticated, "tenant_resolved": tenant_resolved, "code": "REMOTE_TOKEN_VALID" if authenticated and tenant_resolved else "REMOTE_TOKEN_INVALID", "http_status": response.status_code, "retryable": False}
    except requests.Timeout as exc:
        logger.error("[DIAGNOSTICO] falha type=%s", type(exc).__name__)
        return {"success": False, "authenticated": False, "tenant_resolved": False, "code": "REMOTE_HEALTH_TIMEOUT", "retryable": True}
    except (requests.RequestException, ValueError) as exc:
        logger.error("[DIAGNOSTICO] falha type=%s", type(exc).__name__)
        return {"success": False, "authenticated": False, "tenant_resolved": False, "code": "REMOTE_HEALTH_UNAVAILABLE", "retryable": True}


def diagnose_remote():
    return diagnose_remote_result()["success"]


def activate_remote(reactivate=False):
    try:
        require_remote_env()
        logger.info("[ACTIVATION] command_started=true")
        if not LICENSE_API_KEY:
            logger.error("[ACTIVATION] api_code=LICENSE_KEY_MISSING")
            return {"success": False, "code": "LICENSE_KEY_MISSING", "message": "Chave de licença não configurada."}
        payload = {
            "license_api_key": LICENSE_API_KEY,
            "company_cnpj": COMPANY_CNPJ,
            "installation_id": CREDENTIAL_STORE.installation_id(),
            "machine_name": socket.gethostname(),
            "machine_fingerprint": CREDENTIAL_STORE.machine_fingerprint(),
            "agent_version": AGENT_VERSION,
            "reactivate": reactivate,
        }
        response = requests.post(remote_endpoint("agent/activate"), json=payload, timeout=(10, 30))
        logger.info("[ACTIVATION] api_status=%s", response.status_code)
        if response.status_code != 200:
            error = sanitized_api_error(response)
            logger.info("[ACTIVATION] api_code=%s", error["code"])
            logger.info("[ACTIVATION] token_received=false")
            logger.info("[ACTIVATION] token_saved=false")
            logger.error(
                "[ATIVACAO] recusada status=%s code=%s message=%s request_id=%s",
                response.status_code, error["code"], error["message"], error["request_id"],
            )
            return {"success": False, "code": error["code"], "message": error["message"], "api_status": response.status_code}
        body = response.json()
        token = body.get("remote_sync_token")
        logger.info("[ACTIVATION] api_code=%s", body.get("code") or "AGENT_ACTIVATED")
        logger.info("[ACTIVATION] token_received=%s", str(bool(token)).lower())
        if body.get("success") is not True or not token:
            logger.info("[ACTIVATION] token_saved=false")
            logger.error("[ATIVACAO] resposta de confirmacao invalida")
            return {"success": False, "code": "ACTIVATION_RESPONSE_INVALID", "message": "A resposta de ativação não contém uma credencial válida.", "api_status": response.status_code}
        CREDENTIAL_STORE.save_token(token)
        token_saved = CREDENTIAL_STORE.has_token()
        logger.info("[ACTIVATION] token_saved=%s", str(token_saved).lower())
        logger.info("[CREDENTIALS] remote_sync_token_present=%s", str(token_saved).lower())
        logger.info(
            "[ATIVACAO] concluida code=%s request_id=%s",
            body.get("code"), body.get("request_id"),
        )
        return {"success": token_saved, "code": body.get("code") or "AGENT_ACTIVATED", "message": "Ativação concluída.", "api_status": response.status_code, "token_received": True, "token_saved": token_saved}
    except requests.Timeout:
        logger.error("[ATIVACAO] falha type=ReadTimeout")
        logger.info("[ACTIVATION] token_saved=false")
        return {"success": False, "code": "ACTIVATION_REMOTE_TIMEOUT", "message": "O servidor demorou para responder à ativação.", "retryable": True}
    except (requests.RequestException, ValueError, CredentialStoreError, RuntimeError) as exc:
        logger.error("[ATIVACAO] falha type=%s", type(exc).__name__)
        logger.info("[ACTIVATION] token_saved=false")
        return {"success": False, "code": type(exc).__name__.upper(), "message": "Não foi possível concluir a ativação remota."}


GENERIC_TABLES = [
    {"table": "TB_EMPRESA", "columns": ["EMP_ID", "EMP_FANTASIA", "EMP_RAZAO_SOCIAL", "EMP_CNPJ"]},
    {"table": "TB_PEDIDO_VENDA", "columns": ["PEV_ID", "PEV_EMPRESA", "PEV_CLIENTE", "PEV_VENDEDOR", "PEV_DT_EMISSAO", "PEV_DT_FATURAMENTO", "PEV_DT_LANCAMENTO", "PEV_VALOR_TOTAL", "PEV_STATUS", "PEV_FECHAMENTO", "PEV_DT_CANCELAMENTO", "PEV_DESCRICAO_CANCELAMENTO"], "date_column": "PEV_DT_LANCAMENTO", "filter_first_run": True},
    {
        "table": "TB_PEDIDO_VENDA_ITEM",
        "columns": [
            "PEVI_EMPRESA", "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA",
            "PEVI_PRODUTO", "PEVI_DESCRICAO", "PEVI_QUANTIDADE", "PEVI_UN_VENDA",
            "PEVI_VALOR_UNITARIO", "PEVI_VALOR_CUSTO_UNITARIO",
            "PEVI_VALOR_DESCONTO", "PEVI_VALOR_TOTAL",
            "PEVI_VALOR_ACRESCIMO", "PEVI_VALOR_FRETE",
            "PEVI_DT_LANCAMENTO",
        ],
        "required_columns": ["PEVI_EMPRESA", "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA"],
        "where": "PEVI_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= ?)",
    },
    {"table": "TB_PESSOA", "columns": ["PES_ID", "PES_RSOCIAL_NOME", "PES_FANTASIA_APELIDO", "PES_CIDADE", "PES_DT_CADASTRO", "PES_EMAIL", "PES_TELEFONE", "PES_CELULAR", "PES_VENDEDOR", "PES_CNPJ_CPF", "PES_STATUS"]},
    {"table": "TB_CLIENTE", "columns": ["CLI_PESSOA", "CLI_EMPRESA", "CLI_STATUS", "CLI_DT_CADASTRO"]},
    {"table": "TB_VENDEDOR", "columns": ["VDR_PESSOA"]},
    {
        "table": "TB_CIDADE",
        "columns": ["CID_ID", "CID_NOME", "CID_CODIGO_MUNICIPIO"],
    },
    {"table": "TB_PRODUTO", "columns": ["PRD_ID", "PRD_EMPRESA", "PRD_DESCRICAO", "PRD_GRUPO", "PRD_MARCA", "PRD_STATUS", "PRD_ESTOQUE_MINIMO", "PRD_PRECO_VENDA", "PRD_PRECO_CUSTO", "PRD_CODIGO_BARRAS", "PRD_REFERENCIA", "PRD_DEPARTAMENTO", "PRD_SUBGRUPO"]},
    {"table": "TB_USUARIO", "columns": ["USU_ID", "USU_LOGIN", "USU_NOME", "USU_STATUS", "USU_SENHA", "USU_ADMINISTRADOR", "USU_VENDEDOR"]},
    {"table": "TB_PRODUTO_ESTOQUE", "columns": ["PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_LOCAL", "PRDE_VARIACAO", "PRDE_ESTOQUE"], "required_columns": ["PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_LOCAL", "PRDE_VARIACAO"]},
    {"table": "TB_PROD_CODIGO_BARRAS", "columns": ["PRDC_EMPRESA", "PRDC_PRODUTO", "PRDC_COD_BARRAS", "PRDC_SEQUENCIA", "PRDC_PRINCIPAL", "PRDC_CONVERSAO"], "required_columns": ["PRDC_PRODUTO", "PRDC_COD_BARRAS"]},
    {"table": "TB_PRODUTO_PRECO", "columns": ["PRDP_EMPRESA", "PRDP_PRODUTO", "PRDP_PRECO_VENDA", "PRDP_PRECO_COMPRA", "PRDP_CUSTO_AQUISICAO", "PRDP_CUSTO_CONTABIL", "PRDP_CUSTO_TOTAL"], "required_columns": ["PRDP_EMPRESA", "PRDP_PRODUTO"]},
    {"table": "TB_PROD_GRUPO", "columns": ["PGRU_ID", "PGRU_EMPRESA", "PGRU_DESCRICAO", "PGRU_STATUS"]},
    {"table": "TB_PROD_MARCA", "columns": ["PMAR_ID", "PMAR_EMPRESA", "PMAR_DESCRICAO", "PMAR_STATUS"]},
    {
        "table": "TB_ESPECIE_MOEDA",
        "columns": [
            "ESP_ID", "ESP_SIGLA", "ESP_DESCRICAO", "ESP_STATUS",
            "ESP_MOVIMENTAR", "ESP_SEQUENCIA", "ESP_EMPRESA",
        ],
    },
    {
        "table": "TB_PEDIDO_VENDA_FIN",
        "columns": [
            "PEVF_EMPRESA", "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA",
            "PEVF_ESPECIE_MOEDA", "PEVF_VALOR", "PEVF_TROCO",
            "PEVF_VALOR_VENDA", "PEVF_DT_EMISSAO", "PEVF_DT_VECTO",
            "PEVF_USUARIO", "PEVF_DT_LANCAMENTO", "PEVF_MOVIMENTAR",
            "PEVF_CAIXA", "PEVF_FECHAMENTO",
        ],
        "required_columns": ["PEVF_EMPRESA", "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA"],
        "where": "PEVF_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= ?)",
    },
    {"table": "TB_COLABORADOR", "columns": ["COL_PESSOA", "COL_EMPRESA", "COL_CARGO", "COL_FUNCAO", "COL_STATUS", "COL_SALARIO_VALOR", "COL_DATA_ADMISSAO", "COL_DATA_AFASTAMENTO"]},
    {"table": "TB_AUDITORIA", "columns": ["AUD_EMPRESA", "AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA", "AUD_ACAO", "AUD_DT_LANCAMENTO", "AUD_DT_ACAO", "AUD_USUARIO", "AUD_VENDEDOR", "AUD_TABELA_DESC", "AUD_DESC_REGISTRO"], "date_column": "AUD_DT_LANCAMENTO", "filter_first_run": True},
    {
        "table": "TB_FECHAMENTO_CAIXA",
        "columns": [
            "FCX_EMPRESA", "FCX_ID", "FCX_STATUS", "FCX_CAIXA",
            "FCX_CAIXA_DESTINO", "FCX_USU_ABERTURA", "FCX_USU_FECHAMENTO",
            "FCX_USU_CONFERENCIA", "FCX_DT_ABERTURA", "FCX_DT_FECHAMENTO",
            "FCX_DT_LANCAMENTO", "FCX_DT_CONFERENCIA", "FCX_TURNO",
            "FCX_VALOR_TOTAL", "FCX_VALOR_CAIXA", "FCX_VALOR_DIFERENCA",
            "FCX_VALOR_VENDA", "FCX_QTDE_VENDA", "FCX_VALOR_DESCONTO",
            "FCX_QTDE_DESCONTO", "FCX_VALOR_BRINDE", "FCX_QTDE_BRINDE",
            "FCX_VALOR_CANCELADOS", "FCX_QTDE_CANCELADOS",
            "FCX_VALOR_SANGRIA", "FCX_QTDE_SANGRIA", "FCX_VALOR_SUPRIMENTO",
            "FCX_QTDE_SUPRIMENTO", "FCX_VALOR_DEBITO", "FCX_VALOR_CREDITO",
            "FCX_RECEBIMENTO", "FCX_PAGAMENTO", "FCX_VALOR_TROCO",
            "FCX_TROCO_PERDOADO", "FCX_VALOR_PRAZO", "FCX_VALOR_BANC",
            "FCX_ORIGEM", "FCX_VENDEDOR", "FCX_OBSERVACAO",
        ],
        "required_columns": ["FCX_EMPRESA", "FCX_ID"],
        "erp_company_column": "FCX_EMPRESA",
        "where": "(FCX_DT_LANCAMENTO >= ? OR FCX_DT_LANCAMENTO IS NULL OR FCX_DT_FECHAMENTO IS NULL)",
    },
    {
        "table": "TB_FECHAMENTO_CAIXA_ITEM",
        "columns": [
            "FCXI_EMPRESA", "FCXI_FECHAMENTO", "FCXI_SEQUENCIA",
            "FCXI_ESPECIE_MOEDA", "FCXI_VALOR_DEBITO", "FCXI_VALOR_CREDITO",
            "FCXI_VALOR_TOTAL", "FCXI_VALOR_CAIXA", "FCXI_DIFERENCA",
            "FCXI_MOV_CAIXA",
        ],
        "erp_company_column": "FCXI_EMPRESA",
        "required_columns": ["FCXI_EMPRESA", "FCXI_FECHAMENTO", "FCXI_SEQUENCIA"],
        "where": "FCXI_FECHAMENTO IN (SELECT FCX_ID FROM TB_FECHAMENTO_CAIXA WHERE FCX_EMPRESA = FCXI_EMPRESA AND (FCX_DT_LANCAMENTO >= ? OR FCX_DT_LANCAMENTO IS NULL OR FCX_DT_FECHAMENTO IS NULL))",
    },
    {
        "table": "TB_FECHAMENTO_CAIXA_VENDA",
        "columns": [
            "FCXV_EMPRESA", "FCXV_FECHAMENTO", "FCXV_SEQUENCIA",
            "FCXV_ESPECIE_MOEDA", "FCXV_VALOR", "FCXV_ORIGEM",
            "FCXV_VALOR_CAIXA", "FCXV_DIFERENCA",
        ],
        "erp_company_column": "FCXV_EMPRESA",
        "required_columns": ["FCXV_EMPRESA", "FCXV_FECHAMENTO", "FCXV_SEQUENCIA"],
        "where": "FCXV_FECHAMENTO IN (SELECT FCX_ID FROM TB_FECHAMENTO_CAIXA WHERE FCX_EMPRESA = FCXV_EMPRESA AND (FCX_DT_LANCAMENTO >= ? OR FCX_DT_LANCAMENTO IS NULL OR FCX_DT_FECHAMENTO IS NULL))",
    },
    {
        "table": "TB_MOVIMENTO_CAIXA",
        "columns": [
            "MOV_EMPRESA", "MOV_ID", "MOV_CAIXA", "MOV_TIPO", "MOV_DT_EMISSAO",
            "MOV_VALOR", "MOV_USUARIO", "MOV_DT_LANCAMENTO", "MOV_STATUS",
            "MOV_ORIGEM", "MOV_ID_ORIGEM", "MOV_FECHAMENTO", "MOV_HISTORICO",
            "MOV_ESPECIE_MOEDA", "MOV_ITEM_ORIGEM", "MOV_TROCO",
            "MOV_ID_MOVIMENTO",
        ],
        "erp_company_column": "MOV_EMPRESA",
        "required_columns": ["MOV_EMPRESA", "MOV_ID"],
        "where": "(MOV_DT_LANCAMENTO >= ? OR MOV_FECHAMENTO IN (SELECT FCX_ID FROM TB_FECHAMENTO_CAIXA WHERE FCX_EMPRESA = MOV_EMPRESA AND (FCX_DT_LANCAMENTO IS NULL OR FCX_DT_FECHAMENTO IS NULL)))",
    },
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
            "REC_VALOR_ABERTO": ["REC_VALOR_ABERTO"],
            "REC_VALOR_BAIXADO": ["REC_VALOR_BAIXADO"],
            "REC_DT_PAGAMENTO": ["REC_DT_PAGAMENTO"],
            "REC_DOCUMENTO": ["REC_DOCUMENTO"],
            "REC_ESPECIE_MOEDA": ["REC_ESPECIE_MOEDA"],
            "REC_CENTRO_CUSTO": ["REC_CENTRO_CUSTO"],
            "REC_PLANO_CONTAS": ["REC_PLANO_CONTAS"],
            "REC_FECHAMENTO": ["REC_FECHAMENTO"],
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
            "PAG_VALOR_ABERTO": ["PAG_VALOR_ABERTO"],
            "PAG_VALOR_BAIXADO": ["PAG_VALOR_BAIXADO"],
            "PAG_DT_PAGAMENTO": ["PAG_DT_PAGAMENTO"],
            "PAG_DOCUMENTO": ["PAG_DOCUMENTO"],
            "PAG_ESPECIE_MOEDA": ["PAG_ESPECIE_MOEDA"],
            "PAG_CENTRO_CUSTO": ["PAG_CENTRO_CUSTO"],
            "PAG_PLANO_CONTAS": ["PAG_PLANO_CONTAS"],
            "PAG_DT_EMISSAO": ["PAG_DT_EMISSAO"],
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
        if table_name in CASH_REGISTER_TABLE_NAMES:
            logger.warning("[CAIXA] tabela=%s status=SKIPPED reason=TABLE_NOT_FOUND", table_name)
        logger.warning("[SYNC] Tabela ignorada porque nao existe no ERP: %s", table_name)
        return []

    missing_required = [
        column for column in spec.get("required_columns", [])
        if not schema.has_column(table_name, column)
    ]
    if missing_required:
        logger.error(
            "[CAIXA] tabela=%s status=SKIPPED reason=MISSING_REQUIRED_FIELDS fields=%s",
            table_name,
            ",".join(missing_required),
        )
        return []

    available_columns = [column for column in columns if schema.has_column(table_name, column)]
    missing_columns = [column for column in columns if column not in available_columns]
    if missing_columns:
        logger.warning("[SYNC] %s sem campos: %s", table_name, ", ".join(missing_columns))

    if not available_columns:
        logger.warning("[SYNC] Tabela %s ignorada sem colunas compativeis", table_name)
        return []

    select_columns = list(available_columns)
    company_column = spec.get("erp_company_column")
    if company_column:
        if company_column not in available_columns:
            logger.error(
                "[SYNC] %s ignorada: coluna de empresa ERP ausente (%s)",
                table_name,
                company_column,
            )
            return []
        select_columns.append(f"{company_column} AS erp_company_id")

    sql = f"SELECT {', '.join(select_columns)} FROM {table_name}"
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


CASH_REGISTER_TABLE_NAMES = {
    "TB_FECHAMENTO_CAIXA",
    "TB_FECHAMENTO_CAIXA_ITEM",
    "TB_FECHAMENTO_CAIXA_VENDA",
    "TB_MOVIMENTO_CAIXA",
}


def diagnose_cash_register_compatibility(conn, schema):
    specs = {
        spec["table"]: spec
        for spec in GENERIC_TABLES
        if spec["table"] in CASH_REGISTER_TABLE_NAMES
    }
    date_columns = {
        "TB_FECHAMENTO_CAIXA": "FCX_DT_LANCAMENTO",
        "TB_MOVIMENTO_CAIXA": "MOV_DT_LANCAMENTO",
    }
    tables = []
    for table_name in sorted(CASH_REGISTER_TABLE_NAMES):
        spec = specs[table_name]
        found = schema.has_table(table_name)
        missing = [
            column for column in spec.get("required_columns", [])
            if found and not schema.has_column(table_name, column)
        ]
        item = {
            "table": table_name,
            "found": found,
            "compatible": bool(found and not missing),
            "required_fields_ok": bool(found and not missing),
            "missing_required_fields": missing,
            "records": None,
            "first_date": None,
            "last_date": None,
        }
        if item["compatible"]:
            cursor = conn.cursor()
            date_column = date_columns.get(table_name)
            if date_column and schema.has_column(table_name, date_column):
                cursor.execute(
                    f"SELECT COUNT(*), MIN({date_column}), MAX({date_column}) FROM {table_name}"
                )
                count, first_date, last_date = cursor.fetchone()
                item.update(
                    records=int(count),
                    first_date=to_json_value(first_date),
                    last_date=to_json_value(last_date),
                )
            else:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                item["records"] = int(cursor.fetchone()[0])
        logger.info(
            "[CAIXA] diagnostico tabela=%s encontrada=%s compativel=%s "
            "registros=%s primeira_data=%s ultima_data=%s campos_obrigatorios=%s",
            table_name,
            item["found"],
            item["compatible"],
            item["records"],
            item["first_date"],
            item["last_date"],
            "OK" if not missing else ",".join(missing),
        )
        tables.append(item)

    compatible_count = sum(item["compatible"] for item in tables)
    status = (
        "COMPATIBLE" if compatible_count == len(tables)
        else "PARTIALLY_COMPATIBLE" if compatible_count
        else "NOT_AVAILABLE"
    )
    return {"status": status, "tables": tables}


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


class SyncPlans(list):
    def __init__(self):
        super().__init__()
        self.unavailable = []

    def report(self, table, reason):
        self.unavailable.append({"table": table, "reason": reason})
        logger.info("[SYNC_RECURSO] tabela=%s disponivel=false motivo=%s", table, reason)


def build_sync_plans(schema):
    plans = SyncPlans()

    def add_plan(name, source, fields, parent_fields=None):
        try:
            plan = TablePlan(name, source, fields, parent_fields=parent_fields or {})
            ordered_source_keys = schema.primary_keys.get(source, [])
            covered = {plan.fields[key] for key in plan.keys}
            for physical in ordered_source_keys:
                if physical not in covered:
                    canonical_key = next((key for key, actual in plan.fields.items() if actual == physical), None)
                    if canonical_key is None:
                        raise ValueError("chave fisica sem mapeamento: " + physical)
                    plan.keys.append(canonical_key)
            if ordered_source_keys:
                plan.order_keys = [next(key for key, actual in plan.fields.items() if actual == physical)
                                   for physical in ordered_source_keys]
            # Keep compatibility with the already installed v2 receiver. A resource
            # whose identity cannot be represented is reported, not guessed.
            from sync_engine import CONTRACT
            if not set(CONTRACT["TABLE_PK_MAP"][name]) <= set(plan.keys):
                raise ValueError("chave desta variante ainda nao reconhecida pelo receptor")
            if name == "TB_PRODUTO_ESTOQUE" and bool(fields.get("PRDE_LOCAL")) != bool(fields.get("PRDE_VARIACAO")):
                raise ValueError("variante de posicao de estoque ainda nao reconhecida pelo receptor")
            plan.refresh_signature()
            plans.append(plan)
        except ValueError as exc:
            plans.report(name, str(exc))

    for spec in GENERIC_TABLES:
        table = spec["table"]
        if table in FINANCIAL_MAPPINGS:
            continue
        if not schema.has_table(table):
            plans.report(table, "tabela nao disponivel neste ERP")
            continue
        # Optional columns and features vary between ERP installations.
        fields = {field: field for field in spec["columns"] if schema.has_column(table, field)}
        for physical_key in schema.primary_keys.get(table, []):
            fields.setdefault(physical_key, physical_key)
        company = spec.get("erp_company_column")
        if company and company in fields:
            fields["erp_company_id"] = company
        parent_fields = {}
        if table == "TB_PROD_CODIGO_BARRAS" and not schema.has_column(table, "PRDC_EMPRESA"):
            product_keys = schema.primary_keys.get("TB_PRODUTO", [])
            if product_keys == ["PRD_ID"] and schema.has_column("TB_PRODUTO", "PRD_EMPRESA"):
                fields["PRDC_EMPRESA"] = None
                parent_fields["PRDC_EMPRESA"] = {"table": "TB_PRODUTO", "key": "PRD_ID",
                                                 "source_key": "PRDC_PRODUTO", "value": "PRD_EMPRESA"}
        add_plan(table, table, fields, parent_fields)
    for canonical_table, contract in FINANCIAL_MAPPINGS.items():
        resolved = resolve_financial_mapping(schema, canonical_table)
        if resolved:
            add_plan(canonical_table, resolved["actual_table"],
                     {field: resolved["field_map"].get(field) for field in contract["fields"]})
        else:
            plans.report(canonical_table, "recurso financeiro ausente ou sem mapeamento de identidade e valor")
    mapping = CONFIG.operations_map_file or str(DATA_DIR / "operations-map.json")
    try:
        for canonical_table, table, fields in operational_plans(schema, mapping, unavailable=plans.report):
            add_plan(canonical_table, table, fields)
    except (ValueError, OSError) as exc:
        plans.report("RECURSOS_OPERACIONAIS", "mapeamento operacional nao disponivel: " + type(exc).__name__)
    return plans


def send_confirmed_batch(document):
    if not COMPANY_CNPJ or not active_api_token():
        raise RuntimeError("SYNC_CREDENTIAL_MISSING")
    payload = {
        "cnpj": COMPANY_CNPJ, "type": document["table"], "content": document["rows"],
        "timestamp": datetime.now().isoformat(),
        "batch": {"protocol_version": 2, "batch_id": document["batch_id"],
                  "payload_sha256": document["payload_sha256"], "key_columns": document["keys"]},
    }
    # Reuse the durable batch ID even when the server committed but its reply was lost.
    for attempt, delay in enumerate((0, 5, 15), 1):
        if delay:
            time.sleep(delay + random.uniform(0, 1))
        try:
            response = _BATCH_HTTP.post(remote_endpoint("sync"), json=payload,
                                     headers=remote_sync_headers(), timeout=(10, 60))
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning("[SYNC_LOTE] tentativa=%s erro=%s", attempt, type(exc).__name__)
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code in {408, 429, 500, 502, 503, 504}:
            logger.warning("[SYNC_LOTE] tentativa=%s http=%s", attempt, response.status_code)
            continue
        error = sanitized_api_error(response)
        raise RuntimeError("SYNC_HTTP_" + str(response.status_code) + ":" + str(error.get("code") or "REJECTED"))
    raise RuntimeError("SYNC_BATCH_PENDING_RETRY")


def run_sync():
    connection = None
    progress = Progress(DATA_DIR, SYNC_PROGRESS_CALLBACK)
    progress.update(phase="preparing", message="Conferindo servidor e estrutura do Firebird.")
    try:
        if REMOTE_SYNC_PROTOCOL != 2:
            raise RuntimeError("SYNC_SERVER_UPDATE_REQUIRED")
        if not REMOTE_SYNC_TENANT_ID:
            raise RuntimeError("SYNC_REMOTE_IDENTITY_MISSING")
        connection = get_db_connection()
        schema = FirebirdSchema(connection).load()
        plans = build_sync_plans(schema)
        advanced = {}
        if CONFIG_FILE.is_file():
            advanced = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")).get("advanced", {})
        scope = {"database": FB_DATABASE, "host": FB_HOST, "port": FB_PORT,
                 "api": API_BASE_URL.rstrip("/"), "cnpj": COMPANY_CNPJ, "tenant_id": str(REMOTE_SYNC_TENANT_ID)}
        engine = SyncEngine(DATA_DIR, scope, send_confirmed_batch, progress,
                            batch_size=advanced.get("batchSize", 500), should_pause=SYNC_PAUSE_CALLBACK)
        logger.info("[SYNC] iniciando carga paginada; progresso=%s", DATA_DIR / "progresso.html")
        return engine.run(connection, plans)
    except SyncPaused:
        logger.info("[SYNC] pausada entre lotes; retomada preservada")
        return False
    except Exception as exc:
        progress.update(phase="failed", message=type(exc).__name__ + ": " + str(exc)[:160])
        logger.exception("[SYNC] ciclo interrompido; lotes confirmados preservados para retomada")
        return False
    finally:
        if connection:
            connection.close()


@contextmanager
def single_agent_lock():
    """Hold an OS lock for the normal loop; short wizard commands do not use it."""
    lock_path = DATA_DIR / "agent.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    try:
        handle.seek(0)
        previous_pid_text = handle.read().decode(errors="ignore").strip()
        previous_pid = int(previous_pid_text) if previous_pid_text.isdigit() else None
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc: raise RuntimeError(f"OWNER_LOCKED_BY_ACTIVE_PROCESS:{previous_pid or 'unknown'}") from exc
        else:
            import fcntl
            try: fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc: raise RuntimeError("Outra instancia do agente ja esta ativa.") from exc
        if previous_pid and previous_pid != os.getpid():
            # A aquisição do lock de SO acima prova que nenhum processo ainda
            # mantém este arquivo bloqueado. O PID gravado é apenas metadado
            # órfão e pode inclusive já ter sido reutilizado pelo Windows.
            logger.warning("[OWNER] STALE_OWNER_LOCK_REMOVED previous_pid=%s", previous_pid)
        handle.seek(0);handle.truncate();handle.write(str(os.getpid()).encode());handle.flush();handle.seek(0)
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally: handle.close()


def start_agent(pipe_name=None):
    with single_agent_lock():
        _start_agent_loop(pipe_name)


def ipc_self_test(delay_seconds=0):
    if os.name != "nt":
        return {"success": False, "code": "IPC_WINDOWS_REQUIRED"}
    import win32file

    pipe_name = f"PIGORemoteSyncSelfTest{os.getpid()}"
    pipe_path = rf"\\.\pipe\{pipe_name}"
    secret = uuid.uuid4().hex
    owner = AgentOwner(lambda: True, lambda: True, lambda: True, interval_minutes=60)
    server = NamedPipeServer(owner, secret, pipe_path, acl_mode="user")
    owner.start()
    server.start()
    if delay_seconds:
        time.sleep(delay_seconds)
    message = {
        "version": PROTOCOL_VERSION,
        "request_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "nonce": uuid.uuid4().hex,
        "command": "ping",
        "payload": {},
    }
    message["authentication"] = RequestAuthenticator(secret).sign(message)
    handle = win32file.CreateFile(
        pipe_path,
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        0,
        None,
        win32file.OPEN_EXISTING,
        0,
        None,
    )
    try:
        win32file.WriteFile(handle, json.dumps(message).encode("utf-8"))
        _, raw = win32file.ReadFile(handle, 65536)
        response = json.loads(bytes(raw).decode("utf-8"))
    finally:
        win32file.CloseHandle(handle)
        owner.stop_event.set()
    return {
        "success": response.get("success") is True and response.get("code") == "PONG",
        "pipe": pipe_name,
        "connected": True,
        "handshake": response.get("code") == "PONG",
        "protocol": response.get("version"),
        "owner_pid": response.get("data", {}).get("pid"),
        "client_delay_seconds": delay_seconds,
        "pipe_instances": server.instance_count,
    }


def _start_agent_loop(pipe_name=None):
    logger.info("AGENTE P.I.G.O ATIVO")
    log_startup_context()

    def run_when_available():
        if diagnose_remote():
            return run_sync()
        Progress(DATA_DIR, owner.progress).update(phase="failed", message="Diagnostico remoto falhou. Consulte o aplicativo e os logs; os checkpoints foram preservados.")
        logger.error("Diagnóstico remoto falhou; coleta pesada adiada para o próximo ciclo.")
        return False

    def diagnose_owner():
        remote = diagnose_remote_result()
        if not remote["success"]:
            return remote
        firebird = test_firebird_connection()
        cash_register = None
        if firebird["success"]:
            connection = get_db_connection()
            try:
                schema = FirebirdSchema(connection).load()
                cash_register = diagnose_cash_register_compatibility(connection, schema)
            finally:
                connection.close()
        return {
            **remote,
            "success": bool(firebird["success"]),
            "firebird": bool(firebird["success"]),
            "cash_register": cash_register,
            "writeback": {"enabled": CONFIG.writeback_enabled,
                          "configured": bool(CONFIG.writeback_procedure and CONFIG.writeback_resources)},
            "code": "DIAGNOSTIC_AUTHENTICATED" if firebird["success"] else "FIREBIRD_DIAGNOSTIC_FAILED",
        }

    def reload_owner():
        global CONFIG, FB_HOST, FB_PORT, FB_DATABASE, FB_USER, FB_PASS, FB_CLIENT_PATH, FB_CHARSET, FB_DRIVER
        global API_BASE_URL, COMPANY_CNPJ, LICENSE_API_KEY, SYNC_INTERVAL, _firebird_provider
        candidate = ResolvedAgentConfig.resolve(CONFIG_FILE, ENV_FILE, CREDENTIAL_STORE)
        candidate.validate_firebird()
        if not candidate.api_base_url or not candidate.company_cnpj:
            raise RuntimeError("Configuracao remota invalida")
        CONFIG = candidate
        FB_HOST, FB_PORT, FB_DATABASE = candidate.firebird_host, candidate.firebird_port, candidate.firebird_database
        FB_USER, FB_PASS = candidate.firebird_user, candidate.firebird_password
        FB_CLIENT_PATH, FB_CHARSET, FB_DRIVER = candidate.firebird_client_path, candidate.firebird_charset, candidate.firebird_driver
        API_BASE_URL, COMPANY_CNPJ = candidate.api_base_url, candidate.company_cnpj
        LICENSE_API_KEY, SYNC_INTERVAL = candidate.license_api_key, candidate.sync_interval_minutes
        _firebird_provider = None
        return SYNC_INTERVAL

    service_mode = os.getenv("PIGO_SERVICE_MODE", "false").lower() == "true"
    owner_type = "service" if service_mode else "desktop"
    def run_writeback():
        if not active_api_token():
            return False
        changed = poll_commands(get_db_connection, remote_endpoint, active_api_token(), COMPANY_CNPJ,
            CONFIG.writeback_enabled, CONFIG.writeback_procedure, CONFIG.writeback_resources,
            headers=remote_sync_headers(), progress=owner.progress)
        return changed

    # Gravacao no ERP desligada: nao consulta a fila de comandos nem entra no estado WRITING.
    # Assim o desktop atual nao ve um estado novo e o PIGO nao recebe consultas a cada 15 s.
    owner = AgentOwner(run_when_available, diagnose_owner, reload_owner, owner_type, service_mode, SYNC_INTERVAL,
                       writeback_callback=run_writeback if CONFIG.writeback_enabled else None)
    logger.info("[WRITEBACK] fila_de_comandos=%s", "ativa" if CONFIG.writeback_enabled else "desligada")
    global SYNC_PROGRESS_CALLBACK, SYNC_PAUSE_CALLBACK
    SYNC_PROGRESS_CALLBACK = owner.progress
    SYNC_PAUSE_CALLBACK = owner.pause_requested.is_set
    log_process_identity("startup", owner)
    selected_pipe = rf"\\.\pipe\{pipe_name}" if pipe_name else PIPE_NAME
    ipc = NamedPipeServer(owner, CREDENTIAL_STORE.ensure_ipc_secret(), selected_pipe, acl_mode="service" if service_mode else "user")
    owner.start(); ipc.start()
    logger.info("[OWNER] first_sync=scheduled interval_minutes=%s", SYNC_INTERVAL)
    while owner.state != "STOPPED": time.sleep(0.5)


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print("PIGO Remote Sync Agent")
        print("  --owner [--pipe-name NAME]  Inicia o proprietário e o servidor IPC")
        print("  --activate                  Realiza a primeira ativação")
        print("  --reactivate                Reativa explicitamente a instalação")
        print("  --test-firebird             Testa a conexão Firebird")
        print("  --export-schema             Exporta estrutura do banco sem registros comerciais")
        print("  --diagnose                  Testa a autenticação remota")
        print("  --ipc-self-test             Testa servidor, conexão e handshake IPC")
        raise SystemExit(0)
    if "--clear-credentials" in sys.argv:
        CREDENTIAL_STORE.clear_token()
        logger.info("[ATIVACAO] credencial local removida")
        raise SystemExit(0)
    if "--activate" in sys.argv or "--reactivate" in sys.argv:
        log_process_identity("reactivate" if "--reactivate" in sys.argv else "activate")
        log_startup_context()
        activation_result = activate_remote("--reactivate" in sys.argv)
        print(json.dumps(activation_result, ensure_ascii=False))
        raise SystemExit(0 if activation_result.get("success") else 1)
    if "--ipc-self-test" in sys.argv or "--ipc-self-test-delayed" in sys.argv:
        result = ipc_self_test(5 if "--ipc-self-test-delayed" in sys.argv else 0)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result["success"] else 1)
    if "--diagnose" in sys.argv:
        log_process_identity("diagnose")
        log_startup_context()
        raise SystemExit(0 if diagnose_remote() else 1)
    if "--sync-once" in sys.argv:
        log_process_identity("sync-once-legacy")
        log_startup_context()
        raise SystemExit(0 if diagnose_remote() and run_sync() else 1)
    if "--test-firebird" in sys.argv:
        log_process_identity("test-firebird")
        log_startup_context()
        outcome = test_firebird_connection()
        print(json.dumps(outcome, ensure_ascii=False))
        raise SystemExit(0 if outcome["success"] else 1)
    if "--export-schema" in sys.argv:
        from export_schema import export_structure
        connection = None
        try:
            connection = get_db_connection()
            schema = FirebirdSchema(connection).load()
            selected = Path(DIAGNOSTIC_FILE)
            target = export_structure(connection, schema, selected if selected.is_absolute() else DIAGNOSTIC_DIR / selected)
            print(json.dumps({"success": True, "code": "SCHEMA_EXPORTED", "path": target,
                              "message": "Estrutura do ERP exportada sem registros comerciais."}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"success": False, "code": type(exc).__name__,
                              "message": "Não foi possível ler a estrutura do ERP. Verifique a conexão Firebird."}, ensure_ascii=False))
            raise SystemExit(1)
        finally:
            if connection:
                connection.close()
        raise SystemExit(0)
    if "--owner" in sys.argv:
        pipe_name = sys.argv[sys.argv.index("--pipe-name") + 1] if "--pipe-name" in sys.argv and sys.argv.index("--pipe-name") + 1 < len(sys.argv) else PIPE_NAME.rsplit("\\", 1)[-1]
        logger.info("[OWNER] explicit_mode=true pipe_name=%s", pipe_name)
    else:
        pipe_name = None
    start_agent(pipe_name)
