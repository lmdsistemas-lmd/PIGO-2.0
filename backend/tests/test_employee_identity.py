import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from app.routes.funcionarios import _identity, listar_auditoria_funcionario, collaborators_sql


class EmployeeIdentityTests(unittest.TestCase):
    def test_explicit_collaborator_does_not_fall_back_to_an_unrelated_user_with_same_id(self):
        service=Mock();service.empresa_filter.return_value=(' AND C.COL_EMPRESA=:empresa_id',{'empresa_id':'1'})
        service.table_columns.return_value={'COL_PESSOA','COL_EMPRESA','PES_ID'}
        service.fetch_one.return_value=None
        with self.assertRaises(HTTPException) as error:
            _identity(service,201,1,'colaborador')
        self.assertEqual(error.exception.status_code,404)
        service.fetch_one.assert_called_once()
        self.assertEqual(service.fetch_one.call_args.args[1]['empresa_id'],'1')

    @patch('app.routes.funcionarios.ERPQueryService')
    def test_audit_uses_linked_user_not_person_id_and_keeps_company_filter(self,factory):
        service=factory.return_value
        service.empresa_filter.return_value=(' AND C.COL_EMPRESA=:empresa_id',{'empresa_id':'1'})
        service.fetch_one.return_value={'COL_PESSOA':'201','COL_EMPRESA':'1','PES_RSOCIAL_NOME':'Ana'}
        service.table_columns.side_effect=lambda table: {'AUD_EMPRESA','AUD_USUARIO'} if table=='TB_AUDITORIA' else {'USU_ID','USU_VENDEDOR'}
        service.fetch_all.side_effect=[[{'USU_ID':'7'}],[]]
        result=listar_auditoria_funcionario(201,tipo='',data_inicial='',data_final='',limit=100,empresa_id=1,origem='colaborador')
        self.assertEqual(result['usuario_ids_relacionados'],['7'])
        query,params=service.fetch_all.call_args.args
        self.assertEqual(params['employee_user_0'],'7')
        self.assertEqual(params['employee_company'],'1')
        self.assertNotIn('201',[v for k,v in params.items() if k.startswith('employee_user_')])
        self.assertIn('AUD_EMPRESA',query)

    @patch('app.routes.funcionarios.ERPQueryService')
    def test_missing_person_user_link_reports_unavailable_without_guessing_identity(self,factory):
        service=factory.return_value
        service.empresa_filter.return_value=('',{})
        service.fetch_one.return_value={'COL_PESSOA':'201','PES_RSOCIAL_NOME':'Ana'}
        service.table_columns.side_effect=lambda table: {'AUD_EMPRESA','AUD_USUARIO'} if table=='TB_AUDITORIA' else {'USU_ID'}
        result=listar_auditoria_funcionario(201,tipo='',data_inicial='',data_final='',limit=100,empresa_id=1,origem='colaborador')
        self.assertFalse(result['available'])
        self.assertEqual(result['registros'],[])
        service.fetch_all.assert_not_called()

    def test_older_agent_schema_keeps_employee_query_usable_without_optional_new_fields(self):
        service=Mock()
        service.table_columns.side_effect=lambda table: {'COL_PESSOA','COL_EMPRESA','COL_CARGO'} if table=='TB_COLABORADOR' else {'PES_ID','PES_RSOCIAL_NOME'}
        query=collaborators_sql(service)
        self.assertIn('NULL AS COL_SALARIO_VALOR',query)
        self.assertNotIn('C.COL_SALARIO_VALOR',query)
        self.assertIn('C.COL_CARGO AS COL_FUNCAO',query)
