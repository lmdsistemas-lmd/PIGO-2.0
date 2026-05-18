from app.database.erp_connection import current_cnpj
current_cnpj.set('58253989000125')

from app.services.dashboard_vendas_service import DashboardVendasService

s = DashboardVendasService()
try:
    # Pedido ID from the terminal log was 25345, empresa 1
    print("=== TEST PEDIDO DETALHES ===")
    r = s.get_pedido_detalhes_completos(pedido_id=25345, empresa_id=1)
    print("OK! Chaves:", r.keys())
    print("Itens:", len(r.get("itens", [])))
    print("Financeiro:", len(r.get("pagamentos", [])))
except Exception as e:
    import traceback; traceback.print_exc()
