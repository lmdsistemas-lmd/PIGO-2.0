"""Durable outbound commands. Only the authenticated agent can confirm ERP writes."""
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import text

from app.services.operations_service import OperationsService


EDITABLE = {
    "clientes": {"nome": "text", "fantasia": "text", "documento": "text", "email": "text", "telefone": "text", "status": "text"},
    "fornecedores": {"nome": "text", "fantasia": "text", "email": "text", "telefone": "text", "status": "text"},
    "produtos": {"nome": "text", "barras": "text", "referencia": "text", "departamento": "text", "grupo": "text", "subgrupo": "text", "marca": "text", "venda": "number", "custo": "number", "minimo": "number", "status": "text"},
    "grupos": {"nome": "text", "status": "text"},
    "marcas": {"nome": "text", "status": "text"},
    "departamentos": {"nome": "text", "status": "text"},
    "subgrupos": {"nome": "text", "grupo": "text", "status": "text"},
    "plano-contas": {"nome": "text", "pai": "text", "tipo": "text", "dre": "text"},
}


def validate_payload(resource, action, payload):
    allowed = EDITABLE.get(resource)
    if not allowed or not payload or set(payload) - set(allowed):
        raise ValueError("Informe somente os campos editáveis deste cadastro.")
    if action == "create" and not str(payload.get("nome") or "").strip():
        raise ValueError("Informe o nome ou a descrição.")
    clean = {}
    for key, value in payload.items():
        if value is None:
            clean[key] = None
        elif allowed[key] == "number":
            try:
                number = Decimal(str(value))
                if not number.is_finite() or number < 0 or number >= Decimal("1000000000000"):
                    raise ValueError
                clean[key] = str(number)
            except (ValueError, InvalidOperation):
                raise ValueError("Valores de preço, custo e estoque mínimo devem ser números positivos ou zero.") from None
        elif not isinstance(value, str) or len(value) > 250:
            raise ValueError("Campos de texto devem ter até 250 caracteres.")
        else:
            clean[key] = value.strip()
    if "nome" in clean and not str(clean["nome"] or "").strip():
        raise ValueError("O nome ou a descrição não pode ficar vazio.")
    return clean


def public_command(row):
    return {key: row[key] for key in ("id", "resource", "action", "record_id", "status", "result", "created_at", "updated_at")}


def same_previous_value(current, expected, kind):
    if current is None or expected is None:
        return current is None and expected is None
    if kind == "number":
        try:
            return Decimal(str(current)) == Decimal(str(expected))
        except InvalidOperation:
            return False
    return current == expected


class ErpCommandService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, str(tenant)

    def enqueue(self, request_id, company, resource, action, record_id, payload, expected, user):
        clean = validate_payload(resource, action, payload)
        self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:id,0))"), {"id": str(request_id)})
        previous = self.db.execute(text("SELECT * FROM erp_commands WHERE id=:id"), {"id": str(request_id)}).mappings().first()
        if previous:
            if (str(previous["tenant_id"]) != self.tenant or previous["company_erp_id"] != company
                    or previous["resource"] != resource or previous["action"] != action
                    or previous["record_id"] != record_id or previous["payload"] != clean or previous["expected"] != expected):
                raise ValueError("Identificador de solicitação já utilizado. Atualize a tela.")
            return public_command(previous)
        # Company and record membership are checked server-side before accepting a command.
        company_exists = self.db.execute(text('SELECT 1 FROM "TB_EMPRESA" WHERE tenant_id=:tenant AND "EMP_ID"::text=:company'),
                                         {"tenant": self.tenant, "company": str(company)}).first()
        if not company_exists:
            raise ValueError("Empresa não encontrada nos dados sincronizados.")
        if action == "update":
            if not record_id:
                raise ValueError("Selecione o registro a editar.")
            current = OperationsService(self.db, self.tenant).detail(resource, company, record_id)["record"]
            if set(expected) != set(clean):
                raise ValueError("Envie o valor anterior de cada campo alterado.")
            for key in clean:
                if not same_previous_value(current.get(key), expected[key], EDITABLE[resource][key]):
                    raise ValueError("Este cadastro foi atualizado. Recarregue antes de editar.")
        elif record_id is not None or expected:
            raise ValueError("Novo cadastro não deve informar código ou valores anteriores.")
        row = self.db.execute(text("""INSERT INTO erp_commands
            (id, tenant_id, company_erp_id, resource, action, record_id, payload, expected, requested_by)
            VALUES (:id,:tenant,:company,:resource,:action,:record,CAST(:payload AS jsonb),CAST(:expected AS jsonb),:user)
            RETURNING *"""), {"id": str(request_id), "tenant": self.tenant, "company": company,
            "resource": resource, "action": action, "record": record_id, "payload": json.dumps(clean),
            "expected": json.dumps(expected), "user": user}) .mappings().one()
        self.db.commit()
        return public_command(row)

    def list(self, company, resource):
        return [public_command(row) for row in self.db.execute(text("""SELECT * FROM erp_commands
            WHERE tenant_id=:tenant AND company_erp_id=:company AND resource=:resource
            ORDER BY created_at DESC LIMIT 30"""), {"tenant": self.tenant, "company": company, "resource": resource}).mappings()]

    def claim(self, resources):
        supported = sorted(set(resources) & set(EDITABLE))
        self.db.execute(text("""INSERT INTO erp_agent_capabilities (tenant_id,resources)
            VALUES (:tenant,CAST(:resources AS jsonb)) ON CONFLICT (tenant_id)
            DO UPDATE SET resources=EXCLUDED.resources,seen_at=now()"""),
            {"tenant": self.tenant, "resources": json.dumps(supported)})
        if not supported:
            self.db.commit()
            return []
        token = str(uuid4())
        rows = self.db.execute(text("""WITH next_command AS (
            SELECT id FROM erp_commands WHERE tenant_id=:tenant
            AND resource IN (SELECT jsonb_array_elements_text(CAST(:resources AS jsonb)))
            AND (status='pending' OR (status='processing' AND lease_until < now()))
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
        ) UPDATE erp_commands c SET status='processing',lease_token=:token,
            lease_until=now()+interval '5 minutes',attempts=attempts+1,updated_at=now()
            FROM next_command n WHERE c.id=n.id RETURNING c.*"""),
            {"tenant": self.tenant, "resources": json.dumps(supported), "token": token}).mappings().all()
        self.db.commit()
        return [{key: row[key] for key in ("id", "company_erp_id", "resource", "action", "record_id", "payload", "expected", "lease_token")} for row in rows]

    def acknowledge(self, command_id, lease_token, status, record_id, message):
        row = self.db.execute(text("SELECT * FROM erp_commands WHERE id=:id AND tenant_id=:tenant FOR UPDATE"),
                              {"id": str(command_id), "tenant": self.tenant}).mappings().first()
        if not row:
            raise LookupError("Solicitação não encontrada.")
        if str(row["lease_token"]) != str(lease_token):
            raise ValueError("A reserva desta solicitação expirou.")
        result = {"record_id": record_id, "message": message}
        if row["status"] in {"applied", "rejected"}:
            if row["status"] != status or row["result"] != result:
                raise ValueError("Solicitação já finalizada com outro resultado.")
            return public_command(row)
        updated = self.db.execute(text("""UPDATE erp_commands SET status=:status,result=CAST(:result AS jsonb),
            lease_until=NULL,updated_at=now() WHERE id=:id RETURNING *"""),
            {"id": str(command_id), "status": status, "result": json.dumps(result)}).mappings().one()
        self.db.commit()
        return public_command(updated)
