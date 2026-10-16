import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from app.database.base import Base


class PigoAccessProfile(Base):
    __tablename__='pigo_access_profiles'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    tenant_id=Column(UUID(as_uuid=True),ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False)
    name=Column(String(100),nullable=False)
    permissions=Column(JSONB,nullable=False,default=list)
    created_at=Column(DateTime(timezone=True),server_default=func.now())
    __table_args__=(UniqueConstraint('tenant_id','name',name='uq_pigo_profile_tenant_name'),)


class PigoAccessUser(Base):
    __tablename__='pigo_access_users'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    tenant_id=Column(UUID(as_uuid=True),ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False)
    profile_id=Column(UUID(as_uuid=True),ForeignKey('pigo_access_profiles.id',ondelete='RESTRICT'),nullable=False)
    login=Column(String(100),nullable=False)
    name=Column(String(150),nullable=False)
    password_hash=Column(Text,nullable=False)
    active=Column(Boolean,nullable=False,default=True)
    token_version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),server_default=func.now())
    __table_args__=(UniqueConstraint('tenant_id','login',name='uq_pigo_user_tenant_login'),)
