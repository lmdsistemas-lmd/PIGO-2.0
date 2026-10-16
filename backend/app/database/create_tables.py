from app.database.connection import engine
from app.database.base import Base

from app.models.departamento import Departamento
from app.models.cargo import Cargo
from app.models.pigo_access import PigoAccessProfile, PigoAccessUser
from app.models.funcionario import Funcionario
from app.models.saas import Tenant, LegacyUser, Plan, SyncJob, SyncVenda, SyncFinanceiro, SyncErpUser
from app.models.official import (
    ApiKey,
    ApplicationLog,
    AuditLog,
    Company,
    Dashboard,
    DashboardWidget,
    ErrorLog,
    Integration,
    OfficialUser,
    Permission,
    Role,
    RolePermission,
    SystemSetting,
)

def create_tables():
    Base.metadata.create_all(bind=engine)
