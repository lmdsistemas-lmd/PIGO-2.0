from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_tenant_id = Column(String(100), unique=True)
    cnpj = Column(String(14), unique=True, nullable=False)
    razao_social = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255))
    email = Column(String(255), nullable=False)
    telefone = Column(String(20))
    responsavel = Column(String(255))
    status = Column(String(20), default="ATIVO")
    plano = Column(String(50), default="TESTE")
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True)
    data_vencimento = Column(DateTime(timezone=True), nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    api_token = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    api_token_active = Column(Boolean, nullable=False, default=True)
    api_token_created_at = Column(DateTime(timezone=True))
    api_token_last_used_at = Column(DateTime(timezone=True))
    license_status = Column(String(30), default="unknown")
    has_pigo_access = Column(Boolean, nullable=False, default=False)
    license_expires_at = Column(DateTime(timezone=True))
    license_control_id = Column(String(100))
    license_source_updated_at = Column(DateTime(timezone=True))
    product_slug = Column(String(100), default="p-i-g-o-dashboard")
    environment = Column(String(50), default="production")
    logo_url = Column(Text)
    last_sync = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

class LegacyUser(Base):
    __tablename__ = "legacy_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    username = Column(String(100), unique=True, nullable=False)
    password = Column(Text, nullable=False)
    role = Column(String(50), default="RESELLER")
    name = Column(String(255))
    logo_url = Column(Text)
    status = Column(String(20), default="ATIVO")
    data_vencimento = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("legacy_users.id"), nullable=True)

class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50))
    description = Column(Text)
    price = Column(Numeric(10, 2), default=0)
    duration = Column(Integer, default=30)
    active = Column(Boolean, default=True)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"))
    status = Column(String(20))
    table_name = Column(String(100))
    records_synced = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

class SyncVenda(Base):
    __tablename__ = "sync_vendas_diarias"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    data_venda = Column(DateTime(timezone=True), primary_key=True)
    faturamento = Column(Numeric(18, 2), default=0)
    pedidos = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class SyncFinanceiro(Base):
    __tablename__ = "sync_financeiro_stats"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    inadimplencia_total = Column(Numeric(18, 2), default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class SyncErpUser(Base):
    __tablename__ = "sync_erp_users"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    usu_login = Column(String(100), primary_key=True)
    usu_nome = Column(String(255))
    usu_senha = Column(String(255))
    usu_administrador = Column(String(1)) # 'S' ou 'N'
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

