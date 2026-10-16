"""Read employee identity and audit by the ERP's explicit person/user links."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from app.routes.auth import get_current_user
from app.services.erp_query_service import ERPQueryService

router = APIRouter(prefix='/funcionarios', tags=['Funcionários'], dependencies=[Depends(get_current_user)])


def _normalizar_funcionario_erp(row: dict[str, Any]) -> dict[str, Any]:
    person = row.get('COL_PESSOA') or row.get('PES_ID')
    return {'pes_id': person, 'col_pessoa': person, 'usuario_id': None, 'login': None,
            'nome': str(row.get('PES_RSOCIAL_NOME') or row.get('PES_FANTASIA_APELIDO') or 'Funcionário sem nome').strip(),
            'cpf': row.get('PES_CNPJ_CPF'), 'email': row.get('PES_EMAIL'),
            'telefone': row.get('PES_TELEFONE'), 'celular': row.get('PES_CELULAR'),
            'cargo_oficial': str(row.get('COL_FUNCAO') or row.get('PES_PROFISSAO') or 'Não informado').strip(),
            'status': str(row.get('COL_STATUS') or row.get('PES_STATUS') or 'Sem status').strip(),
            'salario': float(row['COL_SALARIO_VALOR']) if row.get('COL_SALARIO_VALOR') is not None else None,
            'data_admissao': str(row['COL_DATA_ADMISSAO']) if row.get('COL_DATA_ADMISSAO') else None,
            'data_afastamento': str(row['COL_DATA_AFASTAMENTO']) if row.get('COL_DATA_AFASTAMENTO') else None,
            'departamento_id': None, 'departamento_nome': None,
            'vendedor': str(row.get('PES_VENDEDOR') or '').strip().upper() == 'S', 'origem': 'colaborador'}


def _normalizar_usuario_erp(row):
    return {'pes_id': row['USU_ID'], 'col_pessoa': row['USU_ID'], 'usuario_id': row['USU_ID'],
            'login': row.get('USU_LOGIN'), 'nome': row.get('USU_NOME') or row.get('USU_LOGIN') or 'Usuário ERP',
            'cargo_oficial': 'Administrador ERP' if str(row.get('USU_ADMINISTRADOR')).upper() in {'S','SIM','1','TRUE','T'} else 'Usuário ERP',
            'status': 'Ativo', 'origem': 'usuario_erp', 'vendedor': False,
            **{key: None for key in ['cpf','email','telefone','celular','salario','data_admissao','data_afastamento','departamento_id','departamento_nome']}}


def collaborators_sql(service):
    fields = {
        'C': ('TB_COLABORADOR', ['COL_PESSOA','COL_EMPRESA','COL_FUNCAO','COL_STATUS',
              'COL_SALARIO_VALOR','COL_DATA_ADMISSAO','COL_DATA_AFASTAMENTO']),
        'P': ('TB_PESSOA', ['PES_ID','PES_RSOCIAL_NOME','PES_FANTASIA_APELIDO','PES_CNPJ_CPF',
              'PES_EMAIL','PES_TELEFONE','PES_CELULAR','PES_VENDEDOR','PES_PROFISSAO','PES_STATUS']),
    }
    expressions=[]
    for alias,(table,names) in fields.items():
        columns=service.table_columns(table)
        for name in names:
            if name in columns:expressions.append(f'{alias}.{name}')
            elif name=='COL_FUNCAO' and 'COL_CARGO' in columns:expressions.append('C.COL_CARGO AS COL_FUNCAO')
            else:expressions.append(f'NULL AS {name}')
    return 'SELECT '+', '.join(expressions)+' FROM TB_COLABORADOR C LEFT JOIN TB_PESSOA P ON P.PES_ID=C.COL_PESSOA'


USERS = 'SELECT U.USU_ID, U.USU_LOGIN, U.USU_NOME, U.USU_ADMINISTRADOR FROM TB_USUARIO U'


@router.get('')
@router.get('/')
def listar_funcionarios(nome: str = '', status_filtro: str = Query(default='', alias='status'),
                        cargo: str = '', empresa_id: int | None = Query(default=None, gt=0)):
    service = ERPQueryService()
    company_sql, params = service.empresa_filter('C.COL_EMPRESA', empresa_id)
    rows = service.fetch_all(collaborators_sql(service) + ' WHERE 1=1 ' + company_sql + ' ORDER BY P.PES_RSOCIAL_NOME', params)
    records = [_normalizar_funcionario_erp(row) for row in rows]
    if not records:
        records = [_normalizar_usuario_erp(row) for row in service.fetch_all(USERS + ' ORDER BY U.USU_NOME')]
    return [row for row in records if all(str(value or '').strip().casefold() in str(row.get(field) or '').casefold()
            for field, value in [('nome', nome), ('status', status_filtro), ('cargo_oficial', cargo)])]


def _identity(service, person_id, company_id, origin):
    params = {'funcionario_id': str(person_id)}
    if origin != 'usuario_erp':
        company_sql, company_params = service.empresa_filter('C.COL_EMPRESA', company_id)
        row = service.fetch_one(collaborators_sql(service) + ' WHERE CAST(C.COL_PESSOA AS VARCHAR(30))=:funcionario_id ' + company_sql,
                                {**params, **company_params})
        if row:
            return _normalizar_funcionario_erp(row), row
    if origin != 'colaborador':
        row = service.fetch_one(USERS + ' WHERE CAST(U.USU_ID AS VARCHAR(30))=:funcionario_id', params)
        if row:
            return _normalizar_usuario_erp(row), row
    raise HTTPException(404, 'Funcionário não encontrado na empresa selecionada.')


@router.get('/{pes_id}/auditoria')
def listar_auditoria_funcionario(pes_id: int, tipo: str = Query(default=''), data_inicial: str = Query(default=''),
        data_final: str = Query(default=''), limit: int = Query(default=100, ge=1, le=5000),
        empresa_id: int | None = Query(default=None, gt=0), origem: Literal['colaborador','usuario_erp'] | None = Query(default=None)):
    service = ERPQueryService()
    employee, _ = _identity(service, pes_id, empresa_id, origem)
    columns = service.table_columns('TB_AUDITORIA')
    user_ids = []
    if employee['origem'] == 'usuario_erp':
        user_ids = [str(employee['usuario_id'])]
    elif 'USU_VENDEDOR' in service.table_columns('TB_USUARIO'):
        users = service.fetch_all(USERS + ' WHERE CAST(U.USU_VENDEDOR AS VARCHAR(30))=:person_id', {'person_id':str(pes_id)})
        user_ids = sorted({str(user['USU_ID']) for user in users})
    params = {}
    identity_filters = []
    for index, user_id in enumerate(user_ids):
        key = f'employee_user_{index}'
        identity_filters.append(f'CAST(A.AUD_USUARIO AS VARCHAR(30))=:{key}')
        params[key] = user_id
    if employee['origem'] == 'colaborador' and 'AUD_VENDEDOR' in columns:
        identity_filters.append('CAST(A.AUD_VENDEDOR AS VARCHAR(30))=:employee_person')
        params['employee_person'] = str(pes_id)
    available = bool(identity_filters) and (empresa_id is None or 'AUD_EMPRESA' in columns)
    response = {'pes_id':pes_id, 'col_pessoa':pes_id, 'usuario_ids_relacionados':user_ids,
                'tipo_filtro':tipo or None, 'data_inicial':data_inicial or None, 'data_final':data_final or None,
                'limit':limit, 'total':0, 'registros':[], 'available':available}
    if not available:
        return {**response, 'message':'O vínculo entre este colaborador e os usuários da auditoria ainda não foi sincronizado.'}
    filters = ['(' + ' OR '.join(identity_filters) + ')']
    if empresa_id is not None:
        filters.append('CAST(A.AUD_EMPRESA AS VARCHAR(30))=:employee_company')
        params['employee_company'] = str(empresa_id)
    for value, suffix, operator in [(data_inicial,'start','>='),(data_final,'end','<=')]:
        if value:
            from datetime import date
            try: date.fromisoformat(value)
            except ValueError: raise HTTPException(422,'Data inválida. Use AAAA-MM-DD.')
            filters.append(f'CAST(A.AUD_DT_LANCAMENTO AS DATE){operator}CAST(:employee_{suffix} AS DATE)')
            params['employee_'+suffix] = value
    if data_inicial and data_final and data_final < data_inicial:
        raise HTTPException(422,'Data final anterior à data inicial.')
    if tipo.strip():
        filters.append("(UPPER(COALESCE(A.AUD_TABELA_DESC,'')) LIKE :employee_type OR UPPER(COALESCE(A.AUD_ACAO,''))=:employee_action)")
        params.update(employee_type='%'+tipo.strip().upper()+'%',employee_action=tipo.strip().upper()[:1])
    seller = 'A.AUD_VENDEDOR' if 'AUD_VENDEDOR' in columns else 'NULL'
    sql = f'''SELECT FIRST {limit} A.AUD_USUARIO,A.AUD_ACAO,A.AUD_TABELA_DESC,A.AUD_DESC_REGISTRO,
              A.AUD_DT_ACAO,A.AUD_DT_LANCAMENTO,A.AUD_SEQUENCIA,A.AUD_ID_REGISTRO,A.AUD_TABELA,{seller} AS VENDEDOR
              FROM TB_AUDITORIA A WHERE {' AND '.join(filters)} ORDER BY A.AUD_DT_LANCAMENTO DESC,A.AUD_SEQUENCIA DESC'''
    actions = {'I':'Inclusão','A':'Alteração','E':'Exclusão','C':'Cancelamento'}
    records = [{'aud_usuario':row.get('AUD_USUARIO'), 'acao_sigla':row.get('AUD_ACAO'),
                'acao':actions.get(str(row.get('AUD_ACAO') or '').upper(),'Não informado'),
                'tabela_desc':row.get('AUD_TABELA_DESC'), 'campo_desc':None, 'descricao_registro':row.get('AUD_DESC_REGISTRO'),
                'data_hora':str(row['AUD_DT_ACAO']) if row.get('AUD_DT_ACAO') else None,
                'data_lancamento':str(row['AUD_DT_LANCAMENTO']) if row.get('AUD_DT_LANCAMENTO') else None,
                'aud_sequencia':row.get('AUD_SEQUENCIA'), 'aud_id_registro':row.get('AUD_ID_REGISTRO'),
                'aud_tabela':row.get('AUD_TABELA'), 'aud_vendedor':row.get('VENDEDOR'), 'valor_antigo':None, 'valor_novo':None}
               for row in service.fetch_all(sql,params)]
    return {**response,'total':len(records),'registros':records}


@router.get('/{pes_id}')
def detalhar_funcionario(pes_id: int, empresa_id: int | None = Query(default=None, gt=0),
                        origem: Literal['colaborador','usuario_erp'] | None = Query(default=None)):
    employee, row = _identity(ERPQueryService(), pes_id, empresa_id, origem)
    return {**employee,'data_admissao_oficial':employee.get('data_admissao'),
            'salario_oficial':employee.get('salario'),'status_oficial':employee.get('status'),
            'erp_colaborador':{key:row.get(key) for key in ['COL_PESSOA','COL_EMPRESA','COL_STATUS']} if employee['origem']=='colaborador' else None,
            'erp_pessoa':{key:row.get(key) for key in ['PES_ID','PES_RSOCIAL_NOME','PES_EMAIL']} if employee['origem']=='colaborador' else None,
            'erp_usuario':{key:row.get(key) for key in ['USU_ID','USU_LOGIN','USU_NOME','USU_ADMINISTRADOR']} if employee['origem']=='usuario_erp' else None}
