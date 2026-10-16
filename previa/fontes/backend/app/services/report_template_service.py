from uuid import UUID

from sqlalchemy.orm import Session

from app.models.reporting import ReportTemplate
from app.schemas.reporting import ReportTemplateInput


class ReportTemplateService:
    def __init__(self, db: Session, tenant_id: str, user: dict):
        self.db = db
        self.tenant_id = UUID(str(tenant_id))
        self.user = user

    def list(self, category=None):
        query = self.db.query(ReportTemplate).filter(
            ReportTemplate.tenant_id == self.tenant_id,
            ReportTemplate.active.is_(True),
        )
        if category:
            query = query.filter(ReportTemplate.category == category)
        return [self.serialize(item) for item in query.order_by(ReportTemplate.updated_at.desc()).all() if self._can_view(item)]

    def get(self, template_id):
        item = self.db.query(ReportTemplate).filter(
            ReportTemplate.id == template_id,
            ReportTemplate.tenant_id == self.tenant_id,
            ReportTemplate.active.is_(True),
        ).first()
        if not item:
            raise LookupError("Relatório não encontrado.")
        if not self._can_view(item):
            raise PermissionError("Usuário sem permissão para este relatório.")
        return item

    def create(self, payload: ReportTemplateInput):
        item = ReportTemplate(
            tenant_id=self.tenant_id,
            name=payload.name,
            description=payload.description,
            category=payload.definition.category,
            source=payload.definition.source,
            schema=payload.definition.model_dump(mode="json"),
            permissions=payload.permissions,
            created_by=str(self.user.get("sub") or self.user.get("id") or "unknown"),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self.serialize(item)

    def update(self, template_id, payload):
        item = self.get(template_id)
        item.name, item.description = payload.name, payload.description
        item.category, item.source = payload.definition.category, payload.definition.source
        item.schema, item.permissions = payload.definition.model_dump(mode="json"), payload.permissions
        self.db.commit(); self.db.refresh(item)
        return self.serialize(item)

    def duplicate(self, template_id):
        item = self.get(template_id)
        payload = ReportTemplateInput(
            name=f"{item.name} (cópia)", description=item.description or "",
            definition=item.schema, permissions=item.permissions,
        )
        return self.create(payload)

    def delete(self, template_id):
        item = self.get(template_id)
        item.active = False
        self.db.commit()

    @staticmethod
    def serialize(item):
        return {
            "id": str(item.id), "name": item.name, "description": item.description or "",
            "category": item.category, "source": item.source, "definition": item.schema,
            "permissions": item.permissions, "created_by": item.created_by,
            "created_at": item.created_at, "updated_at": item.updated_at,
        }

    def _can_view(self, item):
        permissions = {str(value).lower() for value in (item.permissions or ["all"])}
        role = str(self.user.get("role") or self.user.get("perfil") or "user").lower()
        aliases = {role}
        if role in {"erp-admin", "administrador erp", "admin"}:
            aliases.add("administrator")
        return bool({"all", "todos"} & permissions or aliases & permissions or item.created_by == str(self.user.get("sub") or self.user.get("id")))
