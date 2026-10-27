"""Validation and PostgreSQL receipts for transactional Remote Sync batches."""
import hashlib
import json
import re
from sqlalchemy import text


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_batch(table, rows, batch):
    if not isinstance(batch, dict) or batch.get("protocol_version") != 2:
        raise ValueError("SYNC_PROTOCOL_UNSUPPORTED")
    batch_id = str(batch.get("batch_id", ""))
    digest = str(batch.get("payload_sha256", ""))
    keys = batch.get("key_columns")
    if not re.fullmatch(r"[a-f0-9]{32}", batch_id) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("SYNC_BATCH_INVALID")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError("SYNC_BATCH_ROW_LIMIT")
    if not isinstance(keys, list) or not keys or len(keys) != len(set(keys)) or any(
            not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", key) for key in keys):
        raise ValueError("SYNC_BATCH_KEYS_INVALID")
    content = canonical({"type": table, "key_columns": keys, "content": rows}).encode("utf-8")
    if len(content) > 1_000_000:
        raise ValueError("SYNC_BATCH_BYTE_LIMIT")
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("SYNC_BATCH_DIGEST_MISMATCH")
    return batch_id, digest, keys


def begin_batch(db, tenant_id, installation_id, batch_id, digest):
    # A retry can wait at most3s for a previous request, then gets retried by the agent.
    db.execute(text("SET LOCAL lock_timeout = '3s'"))
    db.execute(text("SET LOCAL statement_timeout = '25s'"))
    lock = int.from_bytes(hashlib.sha256(("pigo-sync:" + tenant_id).encode()).digest()[:8], "big", signed=True)
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock}).scalar():
        raise ValueError("SYNC_RECEIVER_BUSY")
    # This tiny metadata table does not modify or truncate the mirror's business records.
    db.execute(text('''CREATE TABLE IF NOT EXISTS public.pigo_sync_batch_receipts (
        tenant_id TEXT NOT NULL, installation_id TEXT NOT NULL, batch_id TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL, result JSONB NOT NULL,
        committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(tenant_id, installation_id, batch_id)
    )'''))
    found = db.execute(text('''SELECT payload_sha256,result FROM public.pigo_sync_batch_receipts
        WHERE tenant_id=:tenant AND installation_id=:installation AND batch_id=:batch'''),
        {"tenant": tenant_id, "installation": installation_id, "batch": batch_id}).first()
    if found:
        if found[0] != digest:
            raise ValueError("SYNC_BATCH_ID_REUSED")
        result = dict(found[1])
        result["replayed"] = True
        return result
    return None


def save_receipt(db, tenant_id, installation_id, batch_id, digest, result):
    db.execute(text('''INSERT INTO public.pigo_sync_batch_receipts
        (tenant_id,installation_id,batch_id,payload_sha256,result)
        VALUES(:tenant,:installation,:batch,:digest,CAST(:result AS JSONB))'''),
        {"tenant": tenant_id, "installation": installation_id, "batch": batch_id,
         "digest": digest, "result": json.dumps(result, ensure_ascii=False)})
