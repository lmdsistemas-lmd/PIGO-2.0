from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import Mock

from app.database.erp_connection import current_cnpj, current_tenant_id
from app.services.dashboard_vendas_service import DashboardVendasService


class SalesTenantContextTests(unittest.TestCase):
    def test_parallel_dashboard_requests_keep_each_tenant_in_every_worker(self):
        barrier = Barrier(2)

        def request(tenant, cnpj, amount):
            tenant_token = current_tenant_id.set(tenant)
            cnpj_token = current_cnpj.set(cnpj)
            try:
                def result(value):
                    def query(*args):
                        self.assertEqual(current_tenant_id.get(), tenant)
                        self.assertEqual(current_cnpj.get(), cnpj)
                        return value
                    return query

                service = DashboardVendasService()
                repository = Mock()
                repository.get_resumo_kpis.side_effect = result({
                    'faturamento': amount, 'pedidos': 1, 'itens': 1, 'custo': 10})
                repository.get_faturamento_total.side_effect = result(amount)
                repository.get_novos_clientes_count.side_effect = result(3)
                series = ['get_historico_vendas', 'get_top_clientes', 'get_top_produtos',
                          'get_vendas_por_cidade', 'get_vendas_por_vendedor', 'get_vendas_por_grupo',
                          'get_vendas_por_marca', 'get_media_por_faixa_horaria', 'get_media_por_dia_semana']
                for name in series:
                    getattr(repository, name).side_effect = result([])
                service.repository = repository
                barrier.wait(timeout=5)
                data = service.get_dashboard_vendas('month', None, None, 1)
                self.assertEqual(data['resumo']['faturamento'], amount)
                self.assertEqual(data['resumo']['novosClientes'], 3)
                repository.get_novos_clientes_count.assert_called_once()
                repository.get_resumo_kpis.assert_called_once()
                for name in series:
                    getattr(repository, name).assert_called_once()
                self.assertGreaterEqual(repository.get_faturamento_total.call_count, 1)
            finally:
                current_cnpj.reset(cnpj_token)
                current_tenant_id.reset(tenant_token)

        with ThreadPoolExecutor(max_workers=2) as requests:
            jobs = [requests.submit(request, 'tenant-a', '00000000000191', 1000),
                    requests.submit(request, 'tenant-b', '00000000000272', 100000)]
            for job in jobs:
                job.result(timeout=15)


if __name__ == '__main__':
    unittest.main()
