import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password
from app.models.official import (
    Company,
    Dashboard,
    DashboardWidget,
    OfficialUser,
    Permission,
    Role,
    RolePermission,
    SystemSetting,
)


PERMISSIONS = [
    ("auth", "login", "auth.login", "Acessar o sistema"),
    ("users", "manage", "users.manage", "Gerenciar usuarios"),
    ("roles", "manage", "roles.manage", "Gerenciar perfis e permissoes"),
    ("companies", "manage", "companies.manage", "Gerenciar empresas/clientes"),
    ("license-control", "read", "license-control.read", "Consultar status sincronizado do License Control"),
    ("dashboards", "read", "dashboards.read", "Visualizar dashboards"),
    ("dashboards", "manage", "dashboards.manage", "Gerenciar dashboards"),
    ("settings", "manage", "settings.manage", "Gerenciar configuracoes"),
    ("audit", "read", "audit.read", "Visualizar auditoria"),
    ("integrations", "manage", "integrations.manage", "Gerenciar integracoes"),
]


def _get_or_create(db, model, defaults=None, **filters):
    instance = db.query(model).filter_by(**filters).first()
    if instance:
        return instance
    instance = model(**filters, **(defaults or {}))
    db.add(instance)
    db.flush()
    return instance


def seed(db):
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError(
            "A variavel INITIAL_ADMIN_PASSWORD nao foi configurada."
        )

    company = _get_or_create(
        db,
        Company,
        cnpj="00000000000000",
        defaults={
            "name": "Empresa Teste P.I.G.O",
            "legal_name": "Empresa Teste P.I.G.O LTDA",
            "email": "admin@pigo.local",
            "status": "active",
        },
    )

    super_admin = _get_or_create(
        db,
        Role,
        slug="super-admin",
        defaults={"name": "Super Admin", "description": "Acesso total ao P.I.G.O Dashboard", "is_system": True},
    )
    admin = _get_or_create(
        db,
        Role,
        slug="admin",
        defaults={"name": "Admin", "description": "Administrador da empresa", "is_system": True},
    )

    created_permissions = []
    for module, action, slug, description in PERMISSIONS:
        created_permissions.append(
            _get_or_create(
                db,
                Permission,
                slug=slug,
                defaults={"module": module, "action": action, "description": description},
            )
        )

    for permission in created_permissions:
        _get_or_create(db, RolePermission, role_id=super_admin.id, permission_id=permission.id)

    for permission in created_permissions:
        if permission.slug not in {"roles.manage"}:
            _get_or_create(db, RolePermission, role_id=admin.id, permission_id=permission.id)

    existing_admin = db.query(OfficialUser).filter_by(email="admin@pigo.local").first()
    if not existing_admin:
        db.add(
            OfficialUser(
                company_id=company.id,
                role_id=super_admin.id,
                email="admin@pigo.local",
                name="Administrador Inicial",
                password_hash=hash_password(admin_password),
                status="active",
            )
        )

    _get_or_create(
        db,
        SystemSetting,
        key="app.general",
        defaults={
            "value": {"name": "P.I.G.O Dashboard", "environment": "test"},
            "description": "Configuracao geral inicial",
        },
    )
    _get_or_create(
        db,
        SystemSetting,
        key="license.source",
        defaults={
            "value": {"source": "license_control", "local_license_enabled": False},
            "description": "Licenciamento gerenciado exclusivamente pelo License Control",
        },
    )

    dashboard = _get_or_create(
        db,
        Dashboard,
        company_id=company.id,
        slug="principal",
        defaults={
            "name": "Dashboard Principal",
            "description": "Painel inicial da plataforma",
            "is_default": True,
            "layout": {"columns": 12},
        },
    )
    _get_or_create(
        db,
        DashboardWidget,
        dashboard_id=dashboard.id,
        widget_type="summary",
        title="Resumo Geral",
        defaults={"config": {"source": "future"}, "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
    )

    db.commit()


if __name__ == "__main__":
    from app.database.connection import SessionLocal

    session = SessionLocal()
    try:
        seed(session)
        print("Seed inicial aplicado.")
    finally:
        session.close()
