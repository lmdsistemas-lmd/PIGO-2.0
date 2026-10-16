from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.database.connection import SessionLocal
from app.models.saas import Tenant
from app.services.tenant_access_service import validate_tenant_access
from app.models.pigo_access import PigoAccessProfile, PigoAccessUser
from app.core.security import verify_password

PERMISSIONS=[
    ('management.read','Consultar Gestão','Gestão'),('management.manage','Cadastrar e editar metas','Gestão'),
    ('inventory.read','Consultar Estoque','Gestão'),('finance.read','Consultar Financeiro','Financeiro'),
    ('catalogs.read','Consultar Cadastros','Cadastros'),('catalogs.manage','Solicitar gravação de cadastros no ERP','Cadastros'),
    ('reports.read','Consultar relatórios e usar assistente IA','Relatórios'),('reports.manage','Criar e editar relatórios','Relatórios'),
    ('team.read','Consultar Equipe','Equipe'),('performance.read','Consultar Performance','Performance'),
    ('access.manage','Administrar usuários e perfis do PIGO','Acesso'),
]
ALLOWED_PERMISSIONS={row[0] for row in PERMISSIONS}


def validate_permissions(permissions):
    if not set(permissions)<=ALLOWED_PERMISSIONS:
        raise HTTPException(422,'Permissão desconhecida.')
    return sorted(set(permissions))


def payload_for(user,profile):
    permissions=list(profile.permissions)
    role='administrator' if any(p.endswith('.manage') for p in permissions) else 'finance' if 'finance.read' in permissions else 'user'
    return {'sub':'pigo:'+str(user.id),'id':str(user.id),'pigo_user_id':str(user.id),'login':user.login,
            'nome':user.name,'perfil':profile.name,'role':role,'auth_source':'pigo',
            'permissions':permissions,'tenant_id':str(user.tenant_id),'token_version':user.token_version}


def authenticate_local(db,tenant,login,password):
    user=db.execute(select(PigoAccessUser).where(PigoAccessUser.tenant_id==tenant.id,PigoAccessUser.login==login.strip().casefold())).scalar_one_or_none()
    if not user or not user.active or not verify_password(password,user.password_hash):
        raise HTTPException(401,'Usuário ou senha do PIGO inválidos.')
    profile=db.execute(select(PigoAccessProfile).where(PigoAccessProfile.id==user.profile_id,PigoAccessProfile.tenant_id==tenant.id)).scalar_one_or_none()
    if not profile:raise HTTPException(403,'Perfil de acesso indisponível.')
    return {**payload_for(user,profile),'cnpj':tenant.cnpj,'empresa':tenant.nome_fantasia or tenant.razao_social}


def live_local_payload(payload):
    try: user_id=UUID(str(payload['pigo_user_id']));tenant_id=UUID(str(payload['tenant_id']))
    except (ValueError,KeyError):raise HTTPException(401,'Sessão PIGO inválida.')
    with SessionLocal() as db:
        ok,message=validate_tenant_access(db.get(Tenant,tenant_id))
        if not ok:raise HTTPException(403,message)
        user=db.execute(select(PigoAccessUser).where(PigoAccessUser.id==user_id,PigoAccessUser.tenant_id==tenant_id)).scalar_one_or_none()
        if not user or not user.active or user.token_version!=payload.get('token_version'):
            raise HTTPException(401,'Acesso revogado. Entre novamente.')
        profile=db.execute(select(PigoAccessProfile).where(PigoAccessProfile.id==user.profile_id,PigoAccessProfile.tenant_id==tenant_id)).scalar_one_or_none()
        if not profile:raise HTTPException(403,'Perfil indisponível.')
        return {**payload,**payload_for(user,profile)}


def permission_for(path,method):
    if path in {'/api/auth/me','/api/me/tenant','/api/empresas','/api/health'}:return ''
    if path.startswith('/api/acesso'):return 'access.manage'
    if path.startswith('/api/agent/installations/'):return 'access.manage'
    if path.startswith('/api/cash-register/'):
        return 'finance.read' if method in {'GET','HEAD'} else None
    if path.startswith('/api/dashboard/financeiro'):return 'finance.read'
    if path.startswith('/api/dashboard/estoque'):return 'inventory.read'
    if path.startswith('/api/dashboard/metas') and method not in {'GET','HEAD'}:return 'management.manage'
    if path.startswith(('/api/dashboard/','/api/indicadores')):return 'management.read'
    if path.startswith('/api/operacoes/'):
        resource=path.split('/')[3]
        return 'finance.read' if resource in {'receber','pagar','fluxo-caixa','fechamentos','cheques','sangrias'} else 'catalogs.read'
    if path.startswith('/api/erp/cadastros/'):return 'catalogs.read' if method in {'GET','HEAD'} else 'catalogs.manage'
    if path.startswith('/api/reports'):
        if method in {'GET','HEAD'} or path in {'/api/reports/assistant/interpret','/api/reports/preview','/api/reports/export'}:return 'reports.read'
        return 'reports.manage'
    if path.startswith(('/api/erp/colaboradores','/api/funcionarios','/api/departamentos','/api/cargos')):return 'team.read' if method in {'GET','HEAD'} else None
    if path.startswith('/api/performance'):return 'performance.read'
    return None


def check_permission(payload,path,method):
    permission=permission_for(path,method)
    if permission is None or (permission and permission not in payload.get('permissions',[])):
        raise HTTPException(403,'Seu perfil não permite esta operação no PIGO.')
