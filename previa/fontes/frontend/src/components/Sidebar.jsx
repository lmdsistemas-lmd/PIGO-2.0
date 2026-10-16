import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import "../styles/sidebar.css";
import { OPERATION_GROUPS } from "../config/operations";

function Sidebar({
  isMobileOrTablet = false,
  isOpen = false,
  onClose = () => {},
}) {
  const location = useLocation();

  const [dashboardOpen, setDashboardOpen] = useState(
    location.pathname.startsWith("/dashboard")
  );

  const isDashboardRoute = location.pathname.startsWith("/dashboard");
  const isVendasRoute = location.pathname === "/dashboard/vendas";
  const isFinanceiroRoute = location.pathname === "/dashboard/financeiro";
  const isEstoqueRoute = location.pathname === "/dashboard/estoque";
  const isConsolidadoRoute = location.pathname === "/dashboard/consolidado";
  const isRelatoriosRoute = location.pathname.startsWith("/relatorios");
  const isFuncionariosRoute = location.pathname.startsWith("/funcionarios");
  const isPerformanceRoute = location.pathname.startsWith("/performance");
  const showDashboardSubmenu = dashboardOpen || isDashboardRoute;

  function handleDashboardClick() {
    setDashboardOpen((prev) => !prev);
  }

  function handleMobileNavigate() {
    if (isMobileOrTablet) {
      onClose();
    }
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
            <span className="menu-label">Gestão</span>
          </button>

          {showDashboardSubmenu && (
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
              {[["clientes", "Clientes"], ["metas", "Metas de Vendas"], ["curva-abc", "Curva ABC"]].map(([path, label]) => (
                <Link key={path} to={`/dashboard/${path}`} onClick={handleMobileNavigate}
                  className={`submenu-item ${location.pathname === `/dashboard/${path}` ? "submenu-item-active" : ""}`}>{label}</Link>
              ))}
            </div>
          )}
        </div>

        {OPERATION_GROUPS.map((group) => <details className="menu-group" key={group.title} open={group.items.some(([resource]) => location.pathname === `${group.prefix}/${resource}`) || undefined}>
          <summary className="menu-item"><span className="menu-icon" aria-hidden="true"><img src="/icons/painel.svg" alt="" /></span><span className="menu-label">{group.title === "Financeiro" ? group.title : `Cadastros · ${group.title}`}</span></summary>
          <div className="submenu">{group.items.map(([resource, label]) => <Link key={resource} to={`${group.prefix}/${resource}`} onClick={handleMobileNavigate} className={`submenu-item ${location.pathname === `${group.prefix}/${resource}` ? "submenu-item-active" : ""}`}>{label}</Link>)}</div>
        </details>)}

        <Link
          to="/relatorios"
          onClick={handleMobileNavigate}
          className={`menu-item ${isRelatoriosRoute ? "active" : ""}`}
          title="Relatórios"
        >
          <span className="menu-icon" aria-hidden="true">
            <img src="/icons/relatorio.svg" alt="" />
          </span>
          <span className="menu-label">Relatórios com IA</span>
        </Link>

        <Link
          to="/funcionarios"
          onClick={handleMobileNavigate}
          className={`menu-item ${isFuncionariosRoute ? "active" : ""}`}
          title="Funcionários"
        >
          <span className="menu-icon" aria-hidden="true">
            <img src="/icons/funcionario.svg" alt="" />
          </span>
          <span className="menu-label">Equipe</span>
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

    </>
  );
}

export default Sidebar;
