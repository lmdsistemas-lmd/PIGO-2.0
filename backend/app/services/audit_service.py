from sqlalchemy.orm import Session

from app.models.official import AuditLog


def write_audit_log(
    db: Session,
    action: str,
    user_id=None,
    company_id=None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            user_id=user_id,
            company_id=company_id,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata or {},
        )
    )
