from app.database.connection import engine
from app.database.base import Base

from app.models.departamento import Departamento
from app.models.cargo import Cargo
from app.models.funcionario import Funcionario
from app.models.saas import Tenant, User, License, SyncJob

def create_tables():
    Base.metadata.create_all(bind=engine)