from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password
from app.services.audit_service import write_audit_log
from app.database.connection import get_db
from app.models.pigo_access import PigoAccessProfile,PigoAccessUser
from app.routes.auth import get_current_user
from app.services.pigo_access_service import PERMISSIONS,validate_permissions

router=APIRouter(prefix='/acesso',tags=['Acesso ao PIGO'])


def administrator(user=Depends(get_current_user)):
    if user.get('auth_source')=='pigo':
        allowed='access.manage' in user.get('permissions',[])
    else:allowed=str(user.get('role','')).lower() in {'erp-admin','admin','administrator','administrador'}
    if not allowed:raise HTTPException(403,'Somente administradores de acesso podem gerenciar usuários e perfis.')
    return user


def scope(user):
    try:return UUID(str(user['tenant_id']))
    except (KeyError,ValueError):raise HTTPException(401,'Empresa autenticada ausente.')


def audit(db,user,action,row):
    write_audit_log(db, action='pigo_access.'+action, entity_type=row.__tablename__, entity_id=str(row.id),
                    metadata={'tenant_id':str(scope(user)),'actor':str(user.get('sub',''))})


def commit(db):
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Nome de perfil ou login já cadastrado nesta empresa.')


def profile_data(row):return {'id':str(row.id),'nome':row.name,'permissions':row.permissions}
def user_data(row,profile):return {'id':str(row.id),'login':row.login,'nome':row.name,'ativo':row.active,'perfil_id':str(row.profile_id),'perfil':profile.name}


class NamedInput(BaseModel):
    @field_validator('nome',check_fields=False,mode='before')
    @classmethod
    def clean_name(cls,value):
        return value.strip() if isinstance(value,str) else value


class ProfileInput(NamedInput):
    nome:str=Field(min_length=2,max_length=100)
    permissions:list[str]=Field(default_factory=list,max_length=30)


class UserInput(NamedInput):
    login:str=Field(min_length=3,max_length=100,pattern=r'^[a-zA-Z0-9_.@-]+$')
    nome:str=Field(min_length=2,max_length=150)
    senha:str=Field(min_length=10,max_length=200)
    perfil_id:UUID


class UserUpdate(NamedInput):
    nome:str=Field(min_length=2,max_length=150)
    perfil_id:UUID
    ativo:bool=True
    senha:str|None=Field(default=None,min_length=10,max_length=200)


@router.get('/permissoes')
def permission_catalog(user=Depends(administrator)):
    return [{'key':key,'nome':name,'grupo':group} for key,name,group in PERMISSIONS]


@router.get('/perfis')
def profiles(db=Depends(get_db),user=Depends(administrator)):
    return [profile_data(row) for row in db.execute(select(PigoAccessProfile).where(PigoAccessProfile.tenant_id==scope(user)).order_by(PigoAccessProfile.name)).scalars()]


@router.post('/perfis',status_code=201)
def create_profile(payload:ProfileInput,db=Depends(get_db),user=Depends(administrator)):
    row=PigoAccessProfile(tenant_id=scope(user),name=payload.nome.strip(),permissions=validate_permissions(payload.permissions))
    db.add(row);
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Nome de perfil ou login já cadastrado nesta empresa.")
    audit(db,user,"profile_created",row);commit(db);return profile_data(row)


@router.patch('/perfis/{profile_id}')
def update_profile(profile_id:UUID,payload:ProfileInput,db=Depends(get_db),user=Depends(administrator)):
    row=db.execute(select(PigoAccessProfile).where(PigoAccessProfile.id==profile_id,PigoAccessProfile.tenant_id==scope(user)).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404,'Perfil não encontrado.')
    permissions=validate_permissions(payload.permissions)
    if user.get('auth_source')=='pigo':
        actor=db.get(PigoAccessUser,UUID(user['pigo_user_id']))
        if actor and actor.profile_id==row.id and 'access.manage' not in permissions:
            raise HTTPException(409,'Não é possível remover sua própria permissão de administrar acessos.')
    row.name=payload.nome.strip();row.permissions=permissions;audit(db,user,"profile_updated",row);commit(db);return profile_data(row)


@router.get('/usuarios')
def users(db=Depends(get_db),user=Depends(administrator)):
    rows=db.execute(select(PigoAccessUser,PigoAccessProfile).join(PigoAccessProfile,PigoAccessProfile.id==PigoAccessUser.profile_id).where(PigoAccessUser.tenant_id==scope(user),PigoAccessProfile.tenant_id==scope(user)).order_by(PigoAccessUser.name))
    return [user_data(row,profile) for row,profile in rows]


def own_profile(db,user,profile_id):
    row=db.execute(select(PigoAccessProfile).where(PigoAccessProfile.id==profile_id,PigoAccessProfile.tenant_id==scope(user))).scalar_one_or_none()
    if not row:raise HTTPException(404,'Perfil não encontrado nesta empresa.')
    return row


@router.post('/usuarios',status_code=201)
def create_user(payload:UserInput,db=Depends(get_db),user=Depends(administrator)):
    profile=own_profile(db,user,payload.perfil_id)
    row=PigoAccessUser(tenant_id=scope(user),profile_id=profile.id,login=payload.login.casefold(),name=payload.nome.strip(),password_hash=hash_password(payload.senha))
    db.add(row);
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Nome de perfil ou login já cadastrado nesta empresa.")
    audit(db,user,"user_created",row);commit(db);return user_data(row,profile)


@router.patch('/usuarios/{user_id}')
def update_user(user_id:UUID,payload:UserUpdate,db=Depends(get_db),user=Depends(administrator)):
    row=db.execute(select(PigoAccessUser).where(PigoAccessUser.id==user_id,PigoAccessUser.tenant_id==scope(user)).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404,'Usuário não encontrado.')
    profile=own_profile(db,user,payload.perfil_id)
    if user.get('pigo_user_id')==str(row.id) and (not payload.ativo or 'access.manage' not in profile.permissions):
        raise HTTPException(409,'Não é possível revogar seu próprio acesso administrativo nesta tela.')
    if row.active != payload.ativo:row.token_version+=1
    row.name=payload.nome.strip();row.profile_id=profile.id;row.active=payload.ativo
    if payload.senha:row.password_hash=hash_password(payload.senha);row.token_version+=1
    audit(db,user,"user_updated",row);commit(db);return user_data(row,profile)
