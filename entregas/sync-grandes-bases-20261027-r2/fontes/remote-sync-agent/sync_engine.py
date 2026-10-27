"""Bounded uploads with durable acknowledgements. No writes to the source ERP.

An incremental scan compares confirmed fingerprints. It does not pretend that
business dates or increasing IDs identify edits to older records.
"""
import base64
import hashlib
import html
import json
import logging
import math
import os
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

log = logging.getLogger(__name__)
CONTRACT = json.loads(Path(__file__).with_name("sync_contract.json").read_text(encoding="utf-8"))
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def windows_protect(data, decrypt=False):
    """Protect the pending commercial batch without changing the credential vault."""
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    result = Blob()
    crypt = ctypes.windll.crypt32
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 4, ctypes.byref(result))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def encode_pending(document):
    text = canonical(document)
    if sys.platform == "win32":
        return "dpapi-v1:" + base64.b64encode(windows_protect(text.encode("utf-8"))).decode("ascii")
    return text  # Development tests; the Windows installer rejects other platforms.


def decode_pending(text):
    if text.startswith("dpapi-v1:"):
        text = windows_protect(base64.b64decode(text.split(":", 1)[1]), decrypt=True).decode("utf-8")
    return json.loads(text)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def wire_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)  # Preserve monetary precision, including during hashing.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("SYNC_NONFINITE_VALUE")
    return value


def resolve_keys(table, fields):
    variants = CONTRACT["TABLE_KEY_VARIANTS"].get(table, [])
    if table in {"TB_FECHAMENTO_CAIXA", "TB_FECHAMENTO_CAIXA_ITEM", "TB_FECHAMENTO_CAIXA_VENDA", "TB_MOVIMENTO_CAIXA"}:
        variants = [CONTRACT["TABLE_PK_MAP"][table]]
    for keys in variants or [CONTRACT["TABLE_PK_MAP"][table]]:
        if all(fields.get(key) is not None for key in keys):
            return list(keys)
    raise ValueError("SYNC_KEY_FIELDS_MISSING:" + table)


@dataclass
class TablePlan:
    name: str
    source: str
    fields: dict
    order_keys: list | None = None
    parent_fields: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in (self.name, self.source, *self.fields.keys(), *[v for v in self.fields.values() if v is not None]):
            if not IDENTIFIER.fullmatch(name):
                raise ValueError("SYNC_INVALID_IDENTIFIER")
        for name, projection in self.parent_fields.items():
            if name not in self.fields or self.fields[name] is not None:
                raise ValueError("SYNC_PARENT_PROJECTION_INVALID")
            if set(projection) != {"table", "key", "source_key", "value"} or any(
                    not isinstance(value, str) or not IDENTIFIER.fullmatch(value) for value in projection.values()):
                raise ValueError("SYNC_PARENT_PROJECTION_INVALID")
            if projection["source_key"] not in self.fields.values():
                raise ValueError("SYNC_PARENT_PROJECTION_KEY_MISSING")
        self.keys = resolve_keys(self.name, self.fields)
        self.refresh_signature()

    def refresh_signature(self):
        definition = [self.name, self.source, self.fields, self.keys]
        if self.parent_fields:
            definition.append(self.parent_fields)
        self.signature = hashlib.sha256(canonical(definition).encode()).hexdigest()

    @property
    def sql(self):
        selected = []
        for name, actual in self.fields.items():
            parent = self.parent_fields.get(name)
            if parent:
                # The planner verifies the parent key is globally unique. A scalar
                # lookup preserves orphan barcode rows and cannot multiply records.
                expression = ("(SELECT PIGO_PARENT." + parent["value"] + " FROM " + parent["table"] +
                              " PIGO_PARENT WHERE PIGO_PARENT." + parent["key"] + " = " +
                              self.source + "." + parent["source_key"] + ")")
            else:
                expression = actual or "NULL"
            selected.append(expression + " AS " + name)
        columns = ", ".join(selected)
        return "SELECT " + columns + " FROM " + self.source

    def count(self, connection):
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM " + self.source)
            total = int(cursor.fetchone()[0])
        finally:
            cursor.close()
        connection.commit()
        return total

    def pages(self, connection, size):
        if self.order_keys:
            yield from self._keyset_pages(connection, size)
            return
        cursor = connection.cursor()
        try:
            cursor.execute(self.sql)
            names = list(self.fields)
            while True:
                rows = cursor.fetchmany(size)
                if not rows:
                    break
                yield [{name: wire_value(value) for name, value in zip(names, row)} for row in rows]
        finally:
            cursor.close()


    def _keyset_pages(self, connection, size):
        # Use the source PK index. No OFFSET and no Firebird transaction held
        # while an HTTP upload waits on the remote server.
        last = None
        source_keys = [self.fields[key] for key in self.order_keys]
        bound_cursor = connection.cursor()
        try:
            bound_cursor.execute("SELECT FIRST 1 " + ", ".join(source_keys) + " FROM " + self.source +
                                 " ORDER BY " + ", ".join(key + " DESC" for key in source_keys), [])
            bound = bound_cursor.fetchone()
        finally:
            bound_cursor.close()
        connection.commit()
        if bound is None:
            return
        upper = tuple(bound)
        upper_parameters, upper_terms = [], []
        for position, key in enumerate(source_keys):
            comparison = " <= ?" if position == len(source_keys) - 1 else " < ?"
            term = [earlier + " = ?" for earlier in source_keys[:position]] + [key + comparison]
            upper_terms.append("(" + " AND ".join(term) + ")")
            upper_parameters.extend(upper[:position + 1])
        select = self.sql.replace("SELECT ", f"SELECT FIRST {int(size)} ", 1)
        indexes = [list(self.fields).index(key) for key in self.order_keys]
        while True:
            parameters, terms = [], []
            if last is not None:
                for position, key in enumerate(source_keys):
                    term = [earlier + " = ?" for earlier in source_keys[:position]] + [key + " > ?"]
                    terms.append("(" + " AND ".join(term) + ")")
                    parameters.extend(last[:position + 1])
            conditions = ["(" + " OR ".join(upper_terms) + ")"]
            if terms:
                conditions.insert(0, "(" + " OR ".join(terms) + ")")
            sql = select + " WHERE " + " AND ".join(conditions)
            parameters.extend(upper_parameters)
            sql += " ORDER BY " + ", ".join(source_keys)
            cursor = connection.cursor()
            try:
                cursor.execute(sql, parameters)
                rows = cursor.fetchmany(size)
            finally:
                cursor.close()
            connection.commit()  # Only SELECTs were executed on this connection.
            if not rows:
                break
            last = tuple(rows[-1][index] for index in indexes)
            if any(value is None for value in last):
                raise ValueError("SYNC_NULL_SOURCE_PRIMARY_KEY:" + self.name)
            names = list(self.fields)
            yield [{name: wire_value(value) for name, value in zip(names, row)} for row in rows]


@contextmanager
def cycle_lock(data_dir):
    """Also covers manual --sync, which did not hold the owner process lock."""
    path = Path(data_dir) / "sync-cycle.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("SYNC_ALREADY_RUNNING") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("SYNC_ALREADY_RUNNING") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class Checkpoints:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tables_state (
                name TEXT PRIMARY KEY, signature TEXT NOT NULL,
                initial_done INTEGER NOT NULL DEFAULT 0, expected INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS fingerprints (
                table_name TEXT NOT NULL, record_key TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY(table_name, record_key)
            ) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS outbox (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), document TEXT NOT NULL
            );
        """)

    def register(self, plan, total, initial=False):
        with self.db:
            self.db.execute("""INSERT INTO tables_state(name,signature,expected) VALUES(?,?,?)
                ON CONFLICT(name) DO UPDATE SET expected=excluded.expected,
                initial_done=CASE WHEN signature=excluded.signature AND (?=0 OR expected=excluded.expected) THEN initial_done ELSE 0 END,
                signature=excluded.signature""", (plan.name, plan.signature, total, int(initial)))

    def plan_done(self, plan):
        row = self.db.execute("SELECT signature,initial_done FROM tables_state WHERE name=?", (plan.name,)).fetchone()
        return bool(row and row[0] == plan.signature and row[1])

    def initial_done(self, name):
        return bool(self.db.execute("SELECT initial_done FROM tables_state WHERE name=?", (name,)).fetchone()[0])

    def estimated_total(self, name):
        return int(self.db.execute("SELECT expected FROM tables_state WHERE name=?", (name,)).fetchone()[0])

    def mark_done(self, name, observed):
        with self.db:
            self.db.execute("UPDATE tables_state SET initial_done=1,expected=? WHERE name=?", (observed, name))

    def begin_unindexed_scan(self):
        self.db.execute("CREATE TEMP TABLE IF NOT EXISTS scan_keys(record_key TEXT PRIMARY KEY) WITHOUT ROWID")
        with self.db:
            self.db.execute("DELETE FROM scan_keys")

    def check_unindexed_keys(self, keys):
        try:
            with self.db:
                self.db.executemany("INSERT INTO scan_keys VALUES(?)", [(key,) for key in keys])
        except sqlite3.IntegrityError as exc:
            raise ValueError("SYNC_DUPLICATE_PHYSICAL_KEY") from exc

    def known(self, name, keys):
        if not keys:
            return {}
        found = {}
        for start in range(0, len(keys), 400):
            group = keys[start:start + 400]
            found.update(self.db.execute(
                "SELECT record_key,digest FROM fingerprints WHERE table_name=? AND record_key IN (" +
                ",".join("?" for _ in group) + ")", (name, *group)).fetchall())
        return found

    def pending(self):
        row = self.db.execute("SELECT document FROM outbox WHERE singleton=1").fetchone()
        return decode_pending(row[0]) if row else None

    def stage(self, table, keys, rows):
        document = {"table": table, "keys": keys, "rows": rows, "batch_id": uuid.uuid4().hex}
        document["payload_sha256"] = batch_digest(table, keys, rows)
        with self.db:
            self.db.execute("INSERT INTO outbox VALUES(1,?)", (encode_pending(document),))
        return document

    def acknowledge(self, document):
        with self.db:
            self.db.executemany("""INSERT INTO fingerprints VALUES(?,?,?)
                ON CONFLICT(table_name,record_key) DO UPDATE SET digest=excluded.digest""",
                [(document["table"], row_key(row, document["keys"]), row_digest(row)) for row in document["rows"]])
            self.db.execute("DELETE FROM outbox WHERE singleton=1")

    def close(self):
        self.db.close()


def row_key(row, keys):
    values = [row.get(key) for key in keys]
    if any(value is None or str(value).strip() == "" for value in values):
        raise ValueError("SYNC_INCOMPLETE_PHYSICAL_KEY")
    return hashlib.sha256(canonical(values).encode()).hexdigest()


def row_digest(row):
    return hashlib.sha256(canonical(row).encode()).hexdigest()


def batch_digest(table, keys, rows):
    return hashlib.sha256(canonical({"type": table, "key_columns": keys, "content": rows}).encode()).hexdigest()


def bounded_batches(rows, count=500, max_bytes=750_000):
    batch, size = [], 2
    for row in rows:
        length = len(canonical(row).encode("utf-8")) + 1
        if length > max_bytes:
            raise ValueError("SYNC_RECORD_EXCEEDS_BATCH_LIMIT")
        if batch and (len(batch) >= count or size + length > max_bytes):
            yield batch
            batch, size = [], 2
        batch.append(row)
        size += length
    if batch:
        yield batch


class Progress:
    def __init__(self, directory, callback=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.callback = callback
        self.data = {"phase": "counting", "mode": "pending", "total": None,
                     "verified": 0, "sent": 0, "unchanged": 0, "percent": None, "table": None, "companies": [], "unavailable": []}

    def update(self, **values):
        self.data.update(values)
        total = self.data["total"]
        if self.data["phase"] == "completed":
            self.data["percent"] = 100.0
        elif total is not None:
            self.data["percent"] = min(99.9, round(100 * self.data["verified"] / max(1, total), 1))
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._atomic("progresso.json", json.dumps(self.data, ensure_ascii=False, indent=2))
        percent = self.data["percent"]
        label = "Calculando total…" if percent is None else f"{percent:.1f}%"
        titles = {"preparing": "Conferindo conexoes e estrutura", "counting": "Contando registros", "scanning": "Conferindo e enviando", "resuming": "Retomando lote pendente",
                  "completed": "Sincronização concluída", "failed": "Interrompida — o próximo ciclo retomará os dados pendentes", "paused": "Sincronização pausada"}
        title = titles.get(self.data["phase"], self.data["phase"])
        if self.data["phase"] == "completed" and self.data["unavailable"]:
            title = "Sincronização dos recursos disponíveis concluída"
        if self.data["phase"] == "unavailable":
            title = "Nenhum recurso compatível disponível nesta estrutura"
        escape = lambda value: html.escape(str(value))
        gaps = self.data["unavailable"]
        availability = ("<details><summary>Recursos fora desta carga (" + str(len(gaps)) + ")</summary><ul>" + "".join("<li><b>" + escape(item["table"]) + "</b>: " + escape(item["reason"]) + "</li>" for item in gaps) + "</ul></details>") if gaps else ""
        companies = " · ".join(escape(str(item["id"]) + " — " + item["name"]) for item in self.data["companies"])
        content = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta http-equiv="refresh" content="3">
<meta name="viewport" content="width=device-width"><title>Progresso PIGO</title>
<style>body{{font:16px system-ui;background:#f3f6fb;color:#10264b;margin:0;padding:32px}}main{{max-width:800px;margin:auto;background:white;padding:28px;border-radius:16px}}progress{{width:100%;height:28px}}.metrics{{display:flex;gap:28px;flex-wrap:wrap}}small{{color:#52647d}}h1{{font-size:24px}}</style>
<main><h1>PIGO Remote Sync</h1><h2>{escape(title)}</h2><p>{escape({'initial':'Primeira carga: histórico integral','incremental':'Atualizações — comparação local de registros'}.get(self.data['mode'],'Conferindo a sincronização'))}</p>
<progress max="100" {'' if percent is None else 'value="'+str(percent)+'"'}></progress><p><b>{label}</b> dos recursos disponíveis nesta execução</p>
<p>Empresas no mesmo acesso: {companies or "Identificando na leitura"}</p><p>Tabela: <b>{escape(self.data['table'] or '—')}</b></p><div class="metrics">
<p>Total previsto<br><b>{escape(total if total is not None else 'Calculando')}</b></p>
<p>Conferidos nesta execução<br><b>{self.data['verified']}</b></p>
<p>Enviados e confirmados<br><b>{self.data['sent']}</b></p>
<p>Já confirmados, sem alteração<br><b>{self.data['unchanged']}</b></p></div>
{availability}<p>{escape(self.data.get('message',''))}</p><p><small>Última atualização: {datetime.now().astimezone().strftime("%d/%m/%Y %H:%M:%S")}</small></p><small>Atualização automática a cada 3 segundos. O progresso só avança após confirmação do servidor ou conferência de um registro já confirmado. O total pode variar se o ERP mudar durante a leitura.</small></main></html>'''
        self._atomic("progresso.html", content)
        if self.callback:
            self.callback("sync.progress", table=self.data["table"], progress=dict(self.data))

    def _atomic(self, name, content):
        target = self.directory / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        # A browser or antivirus may briefly hold a Windows sharing lock.
        for attempt in range(4):
            try:
                temporary.write_text(content, encoding="utf-8")
                os.replace(temporary, target)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05)


class SyncPaused(Exception):
    pass


class SyncEngine:
    def __init__(self, directory, scope, send, progress=None, batch_size=500, should_pause=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.scope = hashlib.sha256(canonical(scope).encode()).hexdigest()
        self.send = send
        self.should_pause = should_pause or (lambda: False)
        self.progress = progress or Progress(self.directory)
        self.size = max(1, min(int(batch_size), 500))

    def _deliver(self, state, document):
        if self.should_pause():
            raise SyncPaused("SYNC_PAUSED_BETWEEN_BATCHES")
        ack = self.send(document)
        if not (isinstance(ack, dict) and ack.get("success") is True and
                ack.get("protocol_version") == 2 and ack.get("batch_id") == document["batch_id"] and
                ack.get("payload_sha256") == document["payload_sha256"] and
                ack.get("received") == len(document["rows"]) and
                ack.get("persisted") == len(document["rows"]) and ack.get("ignored") == 0):
            raise RuntimeError("SYNC_BATCH_NOT_CONFIRMED")
        state.acknowledge(document)
        log.info("[SYNC_LOTE] tabela=%s lote=%s confirmados=%s replay=%s", document["table"], document["batch_id"], len(document["rows"]), ack.get("replayed", False))

    def run(self, connection, plans):
        with cycle_lock(self.directory):
            state = Checkpoints(self.directory / ("sync-v2-" + self.scope[:24] + ".sqlite3"))
            try:
                unavailable = getattr(plans, "unavailable", [])
                self.progress.update(phase="counting", unavailable=unavailable, message="Contando os recursos disponíveis, sem iniciar outro ciclo.")
                if not plans:
                    self.progress.update(phase="unavailable", total=0, message="A estrutura não possui recursos compatíveis com os mapeamentos atuais. Consulte a lista de recursos fora desta carga.")
                    return False
                totals = {}
                initial = any(not state.plan_done(plan) for plan in plans)
                self.progress.update(mode="initial" if initial else "incremental")
                for plan in plans:
                    if self.should_pause():
                        raise SyncPaused("SYNC_PAUSED_BEFORE_COUNT")
                    self.progress.update(table=plan.name)
                    totals[plan.name] = plan.count(connection) if initial else state.estimated_total(plan.name)
                    state.register(plan, totals[plan.name], initial=initial)
                total = sum(totals.values())
                self.progress.update(total=total, mode="initial" if initial else "incremental", verified=0)
                pending = state.pending()
                if pending:
                    self.progress.update(phase="resuming", table=pending["table"])
                    self._deliver(state, pending)
                    self.progress.update(resumed=len(pending["rows"]))
                verified = unchanged = sent = 0
                completed_counts = {}
                for plan in plans:
                    self.progress.update(phase="scanning", table=plan.name, message="")
                    if initial and plan.name != "TB_EMPRESA" and state.initial_done(plan.name):
                        completed_counts[plan.name] = totals[plan.name]
                        verified += totals[plan.name]
                        unchanged += totals[plan.name]
                        self.progress.update(verified=verified, unchanged=unchanged,
                                             message="Tabela confirmada na carga inicial anterior; alterações serão conferidas no próximo ciclo.")
                        continue
                    observed = 0
                    if not plan.order_keys:
                        state.begin_unindexed_scan()
                    for page in plan.pages(connection, self.size):
                        observed += len(page)
                        if plan.name == "TB_EMPRESA":
                            companies = self.progress.data["companies"] + [{"id": str(row.get("EMP_ID")), "name": str(row.get("EMP_FANTASIA") or row.get("EMP_RAZAO_SOCIAL") or "Empresa")[:120]} for row in page]
                            self.progress.update(companies=companies[:50])
                        if self.should_pause():
                            raise SyncPaused("SYNC_PAUSED_BETWEEN_BATCHES")
                        keys = [row_key(row, plan.keys) for row in page]
                        if not plan.order_keys:
                            state.check_unindexed_keys(keys)
                        if len(set(keys)) != len(keys):
                            raise ValueError("SYNC_DUPLICATE_PHYSICAL_KEY:" + plan.name)
                        known = state.known(plan.name, keys)
                        changes = [row for row, key in zip(page, keys) if known.get(key) != row_digest(row)]
                        same = len(page) - len(changes)
                        unchanged += same
                        verified += same
                        for batch in bounded_batches(changes, self.size):
                            document = state.stage(plan.name, plan.keys, batch)
                            self._deliver(state, document)
                            verified += len(batch)
                            sent += len(batch)
                            self.progress.update(verified=verified, sent=sent, unchanged=unchanged)
                        self.progress.update(verified=verified, sent=sent, unchanged=unchanged)
                    state.mark_done(plan.name, observed)
                    completed_counts[plan.name] = observed
                    if self.progress.callback:
                        self.progress.callback("sync.table.completed", table=plan.name, records=observed)
                    log.info("[SYNC_TABELA] tabela=%s concluida=true", plan.name)
                if self.progress.callback:
                    for name, count in completed_counts.items():
                        self.progress.callback("sync.table.completed", table=name, records=count)
                self.progress.update(phase="completed", table=None, total=verified, verified=verified, sent=sent, unchanged=unchanged,
                                     message="Todos os lotes dos recursos disponíveis foram confirmados. Consulte os recursos fora desta carga, se houver. A próxima leitura transmitirá apenas registros novos ou alterados.")
                return True
            except SyncPaused:
                self.progress.update(phase="paused", message="Pausada entre lotes; as confirmações foram preservadas.")
                raise
            except Exception as exc:
                self.progress.update(phase="failed", message=type(exc).__name__ + ": " + str(exc)[:160])
                raise
            finally:
                state.close()
