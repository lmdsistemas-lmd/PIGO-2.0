"""ERP writes through a locally configured business procedure, in one transaction.

The ERP receipt and the business write commit together. A lost HTTP ACK can then
be replayed without creating a second customer/product. No SQL comes from PIGO.
"""
import hashlib
import json
import logging
import re

import requests

RESOURCES = {"clientes", "fornecedores", "produtos", "grupos", "marcas", "departamentos", "subgrupos", "plano-contas"}
logger = logging.getLogger(__name__)


def execute_command(conn, procedure, command, cnpj):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,30}", procedure):
        raise ValueError("Procedimento de gravação inválido.")
    if command["resource"] not in RESOURCES or command["action"] not in {"create", "update"}:
        raise ValueError("Comando de cadastro inválido.")
    identity = str(command["id"])
    envelope = {key: command[key] for key in ("id", "company_erp_id", "resource", "action", "record_id", "payload", "expected")}
    envelope["cnpj"] = cnpj
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT PAYLOAD_HASH, RESULT_JSON FROM PIGO_COMMAND_RECEIPT WHERE COMMAND_ID=?", (identity,))
        previous = cursor.fetchone()
        if previous:
            if previous[0].strip() != digest:
                raise ValueError("Solicitação repetida com conteúdo divergente.")
            data = previous[1].read() if hasattr(previous[1], "read") else previous[1]
            result = json.loads(data)
            conn.rollback()
            return result
        # Reserve the identifier before calling business rules. A competing agent
        # hits the PK constraint and retries after the first transaction commits.
        cursor.execute("INSERT INTO PIGO_COMMAND_RECEIPT (COMMAND_ID,PAYLOAD_HASH) VALUES (?,?)", (identity, digest))
        cursor.execute(f"EXECUTE PROCEDURE {procedure} (?, ?, ?, ?, ?, ?, ?)", (
            identity, command["company_erp_id"], command["resource"], command["action"], command["record_id"],
            json.dumps(command["payload"], ensure_ascii=True), json.dumps(command["expected"], ensure_ascii=True)))
        row = cursor.fetchone()
        if not row or row[0] not in {"applied", "rejected"} or (row[0] == "applied" and not row[1]):
            raise ValueError("Resposta inválida do procedimento ERP; transação desfeita.")
        result = {"status": row[0], "record_id": str(row[1]) if row[1] is not None else None,
                  "message": str(row[2] or "")[:300]}
        if result["status"] == "rejected":
            # A rejection must never commit partial business writes.
            conn.rollback()
            cursor.execute("INSERT INTO PIGO_COMMAND_RECEIPT (COMMAND_ID,PAYLOAD_HASH,RESULT_JSON) VALUES (?,?,?)",
                           (identity, digest, json.dumps(result, ensure_ascii=True)))
            conn.commit()
            return result
        cursor.execute("UPDATE PIGO_COMMAND_RECEIPT SET RESULT_JSON=? WHERE COMMAND_ID=?",
                       (json.dumps(result, ensure_ascii=True), identity))
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def poll_commands(connection_factory, endpoint, token, cnpj, enabled, procedure, resources, headers=None, progress=None):
    configured = sorted(set(resources) & RESOURCES) if enabled else []
    if enabled and (not procedure or not configured):
        logger.error("[WRITEBACK] Configure procedimento e cadastros antes de ativar a gravação.")
        return None
    conn = None
    try:
        if configured:
            conn = connection_factory()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT FIRST 1 COMMAND_ID FROM PIGO_COMMAND_RECEIPT")
                cursor.fetchall()
                cursor.execute("SELECT RDB$PROCEDURE_NAME FROM RDB$PROCEDURES WHERE TRIM(RDB$PROCEDURE_NAME)=?", (procedure,))
                if not cursor.fetchone():
                    raise ValueError("Procedimento ERP ainda não instalado.")
            finally:
                cursor.close()
                conn.rollback()
        with requests.Session() as http:
            headers = headers or {"Authorization": "Bearer " + token}
            response = http.post(endpoint("sync/commands/claim"), headers=headers,
                                 json={"cnpj": cnpj, "resources": configured}, timeout=30)
            response.raise_for_status()
            commands = response.json()["commands"]
            for command in commands:
                if progress:
                    progress("writeback.started", command_id=str(command["id"]))
                result = execute_command(conn, procedure, command, cnpj)
                acknowledged = http.post(endpoint(f"sync/commands/{command['id']}/ack"), headers=headers,
                    json={"cnpj": cnpj, "lease_token": command["lease_token"], **result}, timeout=30)
                acknowledged.raise_for_status()
                if progress:
                    progress("writeback.completed", command_id=str(command["id"]), status=result["status"])
                logger.info("[WRITEBACK] Solicitação %s: %s", command["id"], result["status"])
        return bool(commands)
    except Exception as exc:
        # Never expose connection strings, tokens or customer data in logs.
        logger.warning("[WRITEBACK] Ciclo adiado (%s). Solicitações sem confirmação serão retomadas.", type(exc).__name__)
        return None
    finally:
        if conn:
            conn.close()
