import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import FeatureDevelopmentModal from "./FeatureDevelopmentModal";
import "../styles/sidebar.css";

const REPORTS_DEVELOPMENT_MESSAGE = [
  "Estamos trabalhando para disponibilizar este módulo em breve.",
  "A área de Relatórios está em desenvolvimento e receberá diversos recursos para geração de relatórios gerenciais, financeiros, operacionais e indicadores do sistema.",
  "Em uma próxima atualização, esta funcionalidade estará disponível.",
];

function Sidebar({
  isMobileOrTablet = false,
  isOpen = false,
  onClose = () => {},
  onReportsDevelopment = () => {},
}) {
  const location = useLocation();

  const [dashboardOpen, setDashboardOpen] = useState(
    location.pathname.startsWith("/dashboard")
  );
  const [reportsDevelopmentOpen, setReportsDevelopmentOpen] = useState(false);

  useEffect(() => {
    if (location.pathname.startsWith("/dashboard")) {
      setDashboardOpen(true);
    }
  }, [location.pathname]);

  const isDashboardRoute = location.pathname.startsWith("/dashboard");
  const isVendasRoute = location.pathname === "/dashboard/vendas";
  const isFinanceiroRoute = location.pathname === "/dashboard/financeiro";
  const isEstoqueRoute = location.pathname === "/dashboard/estoque";
  const isConsolidadoRoute = location.pathname === "/dashboard/consolidado";
  const isRelatoriosRoute = location.pathname.startsWith("/relatorios");
  const isFuncionariosRoute = location.pathname.startsWith("/funcionarios");
  const isPerformanceRoute = location.pathname.startsWith("/performance");

  function handleDashboardClick() {
    setDashboardOpen((prev) => !prev);
  }

  function handleMobileNavigate() {
    if (isMobileOrTablet) {
      onClose();
    }
  }

  function handleReportsClick(event) {
    event.preventDefault();
    event.stopPropagation();
    setReportsDevelopmentOpen(true);
    handleMobileNavigate();
  }

  return (
    <>
      <aside
        className={`sidebar ${isMobileOrTablet ? "sidebar-overlay-mode" : ""} ${
          isOpen ? "sidebar-open" : ""
        }`}
      >
        <div className="logo">
          <img
            src="/logo-comprida.svg"
            alt="LMD Sistemas"
            className="sidebar-logo-full"
          />
          <img
            src="/logo-azul.svg"
            alt="LMD"
            className="sidebar-logo-icon"
          />
        </div>

      <nav className="sidebar-nav">
        <div className="menu-group">
          <button
            type="button"
            className={`menu-item ${isDashboardRoute ? "active" : ""}`}
            onClick={handleDashboardClick}
            title="Dashboard"
          >
            <span className="menu-icon" aria-hidden="true">
              <img src="/icons/painel.svg" alt="" />
            </span>
            <span className="menu-label">Dashboard</span>
          </button>

          {dashboardOpen && (
            <div className="submenu">
              <Link
                to="/dashboard/vendas"
                onClick={handleMobileNavigate}
                className={`submenu-item ${
                  isVendasRoute ? "submenu-item-active" : ""
                }`}
              >
                Vendas
              </Link>

              <Link
                to="/dashboard/financeiro"
                onClick={handleMobileNavigate}
                className={`submenu-item ${
                  isFinanceiroRoute ? "submenu-item-active" : ""
                }`}
              >
                Financeiro
              </Link>

              <Link
                to="/dashboard/estoque"
                onClick={handleMobileNavigate}
                className={`submenu-item ${
                  isEstoqueRoute ? "submenu-item-active" : ""
                }`}
              >
                Estoque
              </Link>

              <Link
                to="/dashboard/consolidado"
                onClick={handleMobileNavigate}
                className={`submenu-item ${
                  isConsolidadoRoute ? "submenu-item-active" : ""
                }`}
              >
                Consolidado
              </Link>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={handleReportsClick}
          className={`menu-item ${isRelatoriosRoute ? "active" : ""}`}
          title="Relatórios"
        >
          <span className="menu-icon" aria-hidden="true">
            <img src="/icons/relatorio.svg" alt="" />
          </span>
          <span className="menu-label">Relatórios</span>
        </button>

        <Link
          to="/funcionarios"
          onClick={handleMobileNavigate}
          className={`menu-item ${isFuncionariosRoute ? "active" : ""}`}
          title="Funcionários"
        >
          <span className="menu-icon" aria-hidden="true">
            <img src="/icons/funcionario.svg" alt="" />
          </span>
          <span className="menu-label">Funcionários</span>
        </Link>

        <Link
          to="/performance"
          onClick={handleMobileNavigate}
          className={`menu-item ${isPerformanceRoute ? "active" : ""}`}
          title="Performance"
        >
          <span className="menu-icon" aria-hidden="true">
            <img src="/icons/performance.svg" alt="" />
          </span>
          <span className="menu-label">Performance</span>
        </Link>
        </nav>
      </aside>

      <FeatureDevelopmentModal
        open={reportsDevelopmentOpen}
        title="🚧 Relatórios em Desenvolvimento"
        message={REPORTS_DEVELOPMENT_MESSAGE}
        onClose={() => setReportsDevelopmentOpen(false)}
      />
    </>
  );
}

export default Sidebar;
