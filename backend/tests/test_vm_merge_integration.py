"""VM contract regression on a disposable PostgreSQL database, never production."""
import os
import unittest
import uuid
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from pathlib import Path
from sqlalchemy import text

@unittest.skipUnless(os.environ.get('PIGO_VM_TEST_DATABASE_URL'), 'requires disposable pigo_vm_test_ database')
class VMMergeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.database.connection import engine,SessionLocal
        if os.environ.get('PIGO_EXPECT_BACKEND_ROOT'):
            import app.main as loaded_main
            assert Path(loaded_main.__file__).is_relative_to(Path(os.environ['PIGO_EXPECT_BACKEND_ROOT']))
        cls.db_factory=SessionLocal
        assert str(engine.url)==str(__import__('sqlalchemy').make_url(os.environ['PIGO_VM_TEST_DATABASE_URL']))
        assert engine.url.host=='127.0.0.1' and engine.url.database.startswith('pigo_vm_test_')
        with engine.begin() as db:
            assert db.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()==0
        from scripts.apply_migrations import main
        main()
        # Running additive migrations again must keep an existing VM row intact.
        main()
        from app.models.saas import Tenant
        from app.models.official import Company
        from app.core.security import create_access_token
        cls.ids=[uuid.uuid4(),uuid.uuid4()];cls.cnpjs=['00000000000191','00000000000272'];cls.headers=[]
        with SessionLocal() as db:
            for index,identifier in enumerate(cls.ids):
                expires=datetime.now(timezone.utc)+timedelta(days=30)
                db.add(Tenant(id=identifier,cnpj=cls.cnpjs[index],razao_social='Synthetic '+str(index),email='test@example.invalid',status='ATIVO',has_pigo_access=True,license_status='active',data_vencimento=expires,license_expires_at=expires))
                db.add(Company(name='Synthetic '+str(index),cnpj=cls.cnpjs[index]))
                cls.headers.append({'Authorization':'Bearer '+create_access_token({'sub':'synthetic-admin','role':'ADMIN','tenant_id':str(identifier),'cnpj':cls.cnpjs[index]})})
            db.commit()
        from app.services.sync_service import SyncService
        with SessionLocal() as db:
            for tenant in cls.ids:
                for table,rows in [('TB_USUARIO',[{'USU_ID':'1','USU_LOGIN':'synthetic','USU_NOME':'Synthetic admin','USU_ADMINISTRADOR':'S'}]),('TB_ESPECIE_MOEDA',[{'ESP_ID':'1','ESP_EMPRESA':'1','ESP_DESCRICAO':'Dinheiro'}]),('TB_FECHAMENTO_CAIXA',[{'FCX_ID':'10','FCX_EMPRESA':'1','FCX_STATUS':'FECHADO','FCX_USU_ABERTURA':'1','FCX_VALOR_TOTAL':100 if tenant==cls.ids[0] else 9999,'FCX_DT_ABERTURA':'2026-10-16 08:00:00'}]),('TB_FECHAMENTO_CAIXA_ITEM',[{'FCXI_FECHAMENTO':'10','FCXI_EMPRESA':'1','FCXI_SEQUENCIA':'1','FCXI_ESPECIE_MOEDA':'1','FCXI_VALOR_TOTAL':100,'FCXI_VALOR_CAIXA':100,'FCXI_DIFERENCA':0}])]:
                    result=SyncService._sync_generic_table(db,str(tenant),table,rows);assert result['inserted']==len(rows),result
            db.commit()
        main()
        with SessionLocal() as db:
            assert db.execute(text('SELECT COUNT(*) FROM "TB_FECHAMENTO_CAIXA"')).scalar()==2
            assert db.execute(text('SELECT SUM("FCX_VALOR_TOTAL") FROM "TB_FECHAMENTO_CAIXA"')).scalar()==10099
        from fastapi.testclient import TestClient
        from app.main import app
        cls.api=TestClient(app,client=('127.0.0.1',50000));cls.api.__enter__()
    @classmethod
    def tearDownClass(cls):cls.api.__exit__(None,None,None)
    def test_activation_preserves_vm_contract_and_revoked_installation_blocks_sync(self):
        from app.models.saas import AgentInstallation,Tenant
        payload={'license_api_key':'synthetic-license-not-real','company_cnpj':self.cnpjs[0],'installation_id':'synthetic-installation-activation','machine_name':'SYNTHETIC','machine_fingerprint':'synthetic-fingerprint','agent_version':'test'}
        with patch('app.services.agent_activation_service.requests.post') as remote:
            remote.return_value.status_code=200;remote.return_value.json.return_value={'project':{'slug':'p-i-g-o-dashboard'},'license':{'status':'active'}}
            response=self.api.post('/api/agent/activate',json=payload)
            self.assertEqual(response.status_code,200,response.text);data=response.json();self.assertEqual(data['code'],'AGENT_ACTIVATED');self.assertIn('remote_sync_token',data)
            self.assertEqual(remote.call_count,1)
        agent={'Authorization':'Bearer '+data['remote_sync_token'],'X-Installation-Id':payload['installation_id']}
        self.assertEqual(self.api.get('/api/sync/health',params={'cnpj':self.cnpjs[0]},headers=agent).status_code,200)
        response=self.api.post('/api/agent/installations/'+payload['installation_id']+'/revoke',headers=self.headers[1]);self.assertEqual(response.status_code,404,response.text)
        response=self.api.post('/api/agent/installations/'+payload['installation_id']+'/regenerate-token',headers=self.headers[1]);self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.api.get('/api/sync/health',params={'cnpj':self.cnpjs[0]},headers=agent).status_code,200)
        self.assertEqual(self.api.post('/api/agent/installations/'+payload['installation_id']+'/revoke',headers=self.headers[0]).status_code,200)
        response=self.api.get('/api/sync/health',params={'cnpj':self.cnpjs[0]},headers=agent);self.assertEqual(response.status_code,403);self.assertEqual(response.json()['code'],'INSTALLATION_BLOCKED')
    def test_legacy_cash_api_and_approved_detail_adapter_share_vm_rows(self):
        legacy=self.api.get('/api/cash-register/closings',params={'company':'1'},headers=self.headers[0]);self.assertEqual(legacy.status_code,200,legacy.text)
        self.assertEqual(legacy.json()['items'][0]['totals']['total'],100)
        foreign=self.api.get('/api/cash-register/closings',params={'company':'1'},headers=self.headers[1]);self.assertEqual(foreign.json()['items'][0]['totals']['total'],9999)
        legacy=self.api.get('/api/cash-register/closings/10',params={'company':'1'},headers=self.headers[0]);self.assertEqual(legacy.status_code,200,legacy.text);self.assertEqual(legacy.json()['paymentMethods'][0]['total'],100)
        modern=self.api.get('/api/operacoes/fechamentos/10',params={'empresa_id':1},headers=self.headers[0]);self.assertEqual(modern.status_code,200,modern.text);self.assertEqual(modern.json()['cash_payments'][0]['total'],100)
        for fmt,prefix in [('excel',b'PK'),('pdf',b'%PDF')]:
            response=self.api.get('/api/operacoes/fechamentos/10/export',params={'empresa_id':1,'tab':'financeiro','format':fmt},headers=self.headers[0]);self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '');self.assertTrue(response.content.startswith(prefix))
    def test_sync_canonical_company_and_missing_sequences_keep_physical_rows(self):
        from app.services.sync_service import SyncService
        with self.db_factory() as db:
            rows=[{'ERP_COMPANY_ID':'1','FCXI_EMPRESA':'1','FCXI_FECHAMENTO':'10','FCXI_SEQUENCIA':'2','FCXI_ESPECIE_MOEDA':'1','FCXI_VALOR_TOTAL':25},{'FCXI_EMPRESA':'1','FCXI_FECHAMENTO':'10','FCXI_ESPECIE_MOEDA':'1','FCXI_VALOR_TOTAL':999}]
            result=SyncService._sync_generic_table(db,str(self.ids[0]),'TB_FECHAMENTO_CAIXA_ITEM',rows);db.commit()
            self.assertEqual(result['inserted'],1);self.assertEqual(result['ignored'],1)
            self.assertEqual(result['pk_columns'],['tenant_id','erp_company_id','FCXI_FECHAMENTO','FCXI_SEQUENCIA'])
            self.assertEqual(db.execute(text('SELECT COUNT(*) FROM "TB_FECHAMENTO_CAIXA_ITEM" WHERE tenant_id=:tenant'),{'tenant':str(self.ids[0])}).scalar(),2)
            with self.assertRaises(ValueError):SyncService._normalize_row_contract('TB_FECHAMENTO_CAIXA_ITEM',{'erp_company_id':'2','FCXI_EMPRESA':'1'})
    def test_schema_contains_all_vm_and_new_feature_tables(self):
        with self.db_factory() as db:
            names=set(db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).scalars())
        self.assertTrue({'agent_installations','municipality_geocodes','municipality_coordinate_overrides','TB_FECHAMENTO_CAIXA','pigo_access_profiles','pigo_access_users','erp_commands','sales_goals'}<=names)
    def test_sales_preserves_vm_status_and_end_of_day_without_cross_tenant_totals(self):
        from datetime import date
        from app.services.sync_service import SyncService
        today=date.today().isoformat()
        with self.db_factory() as db:
            for tenant,amount in [(self.ids[0],100),(self.ids[1],9999)]:
                for table,rows in [
                    ('TB_PESSOA',[{'PES_ID':'101','PES_RSOCIAL_NOME':'Synthetic customer','PES_FANTASIA_APELIDO':'','PES_DT_CADASTRO':today}]),
                    ('TB_CLIENTE',[{'CLI_PESSOA':'101','CLI_EMPRESA':'1'}]),
                    ('TB_PEDIDO_VENDA',[{'PEV_ID':str(i),'PEV_EMPRESA':'1','PEV_CLIENTE':'101','PEV_DT_FATURAMENTO':today+' 23:59:59','PEV_DT_LANCAMENTO':today+' 23:59:59','PEV_STATUS':status,'PEV_VALOR_TOTAL':amount} for i,status in [(1,'F'),(2,'F'),(3,'C')]]),
                    ('TB_PEDIDO_VENDA_ITEM',[{'PEVI_EMPRESA':'1','PEVI_PEDIDO_VENDA':str(i),'PEVI_SEQUENCIA':'1','PEVI_PRODUTO':'1','PEVI_QUANTIDADE':2,'PEVI_VALOR_CUSTO_UNITARIO':10,'PEVI_VALOR_TOTAL':amount} for i in [1,2,3]])]:
                    SyncService._sync_generic_table(db,str(tenant),table,rows)
            db.commit()
        for headers,total in [(self.headers[0],200),(self.headers[1],19998)]:
            response=self.api.get('/api/dashboard/vendas',params={'empresa_id':1,'period':'today','status':'FATURADO'},headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            data=response.json();self.assertEqual(data['resumo']['faturamento'],total);self.assertEqual(data['resumo']['pedidos'],2)
            self.assertEqual(data['resumo']['itensPorVenda'],2);self.assertIsInstance(data['resumo']['novosClientes'],int)
            self.assertEqual(sum(row['valor'] for row in data['historico']),total)
    def test_coordinate_catalog_and_manual_override_contract_remain_available(self):
        from app.services.municipality_coordinate_resolver import MunicipalityCoordinateResolver
        with self.db_factory() as db:
            db.execute(text("INSERT INTO municipality_geocodes(ibge_code,name,state_code,latitude,longitude,source,source_version) VALUES('1721000','Palmas','TO',-10.18,-48.33,'synthetic','test')"));db.commit()
        MunicipalityCoordinateResolver.clear_cache();resolution=MunicipalityCoordinateResolver().resolve('1721000','Palmas')
        self.assertEqual(resolution.resolution_source,'IBGE_CODE');self.assertEqual(resolution.ibge_code,'1721000');self.assertAlmostEqual(resolution.latitude,-10.18)
    def test_local_pigo_permissions_cover_vm_cash_and_installation_management(self):
        from app.models.pigo_access import PigoAccessProfile,PigoAccessUser
        from app.models.saas import AgentInstallation
        from app.models.official import Company
        from app.services.pigo_access_service import payload_for
        from app.core.security import create_access_token
        headers=[]
        with self.db_factory() as db:
            company=db.query(Company).filter(Company.cnpj==self.cnpjs[0]).one()
            for name,permissions in [('finance',['finance.read']),('admin',['access.manage'])]:
                profile=PigoAccessProfile(id=uuid.uuid4(),tenant_id=self.ids[0],name=name,permissions=permissions);db.add(profile);db.flush()
                user=PigoAccessUser(id=uuid.uuid4(),tenant_id=self.ids[0],profile_id=profile.id,login=name,name=name,password_hash='not-a-real-password',active=True,token_version=1);db.add(user);db.flush()
                headers.append({'Authorization':'Bearer '+create_access_token({**payload_for(user,profile),'cnpj':self.cnpjs[0]})})
            db.add(AgentInstallation(tenant_id=self.ids[0],company_id=company.id,installation_id='synthetic-local-admin-installation',machine_name='SYNTHETIC',machine_fingerprint='synthetic-fingerprint',agent_version='test',status='ACTIVE'))
            db.commit()
        self.assertEqual(self.api.get('/api/cash-register/closings',params={'company':'1'},headers=headers[0]).status_code,200)
        path='/api/agent/installations/synthetic-local-admin-installation/revoke'
        self.assertEqual(self.api.post(path,headers=headers[0]).status_code,403)
        self.assertEqual(self.api.get('/api/cash-register/closings',params={'company':'1'},headers=headers[1]).status_code,403)
        self.assertEqual(self.api.post(path,headers=headers[1]).status_code,200)
