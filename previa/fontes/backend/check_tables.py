from app.database.erp_connection import current_cnpj
current_cnpj.set('58253989000125')

# Test Estoque
print("=== ESTOQUE ===")
try:
    from app.services.dashboard_estoque_service import DashboardEstoqueService
    s = DashboardEstoqueService()
    r = s.get_dashboard_estoque(empresa_id=1)
    print("OK! Produtos:", r.get("resumoProdutos", {}).get("total", "?"))
except Exception as e:
    import traceback; traceback.print_exc()

# Test Financeiro
print("\n=== FINANCEIRO ===")
try:
    from app.services.dashboard_financeiro_service import DashboardFinanceiroService
    s = DashboardFinanceiroService()
    r = s.get_dashboard_financeiro(period="year", report_type="faturamento", start=None, end=None, empresa_id=1)
    print("OK! Keys:", list(r.keys()))
except Exception as e:
    import traceback; traceback.print_exc()

# Test Consolidado
print("\n=== CONSOLIDADO ===")
try:
    from app.services.dashboard_consolidado_service import DashboardConsolidadoService
    s = DashboardConsolidadoService()
    r = s.get_dashboard_data("year", None, None)
    print("OK! Keys:", list(r.keys()) if isinstance(r, dict) else type(r))
except Exception as e:
    import traceback; traceback.print_exc()
