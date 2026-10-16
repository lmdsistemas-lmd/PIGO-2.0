import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import DashboardVendas from "./pages/DashboardVendas";
import DashboardFinanceiro from "./pages/DashboardFinanceiro";
import DashboardEstoque from "./pages/DashboardEstoque";
import DashboardConsolidado from "./pages/DashboardConsolidado";
import DetalhesPedidos from "./pages/DetalhesPedidos";
import Reports from "./pages/Reports";
import Funcionarios from "./pages/Funcionarios";
import FuncionarioNovoVinculo from "./pages/FuncionarioNovoVinculo";
import FuncionarioAnalise from "./pages/FuncionarioAnalise";
import Performance from "./pages/Performance";
import PerformanceExclusoes from "./pages/PerformanceExclusoes";
import PerformanceInclusoes from "./pages/PerformanceInclusoes";
import PerformanceAlteracoes from "./pages/PerformanceAlteracoes";
import PerformanceCancelamentos from "./pages/PerformanceCancelamentos";
import Login from "./pages/Login";
import CommercialAnalytics from "./pages/CommercialAnalytics";
import SalesGoals from "./pages/SalesGoals";
import Operations from "./pages/Operations";
import { OPERATIONS } from "./config/operations";
import ProtectedRoute from "./routes/ProtectedRoute";
import BottomNavigation from "./components/BottomNavigation";

import Access from "./pages/Access";
import { useAuth } from "./context/AuthContext";
import { firstAllowedPath } from "./utils/access";
import "./styles/reference-layout.css";

function AppLayout() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const referenceLayout = !pathname.startsWith('/funcionarios') && !pathname.startsWith('/performance');
  const [isMobileOrTablet, setIsMobileOrTablet] = useState(window.innerWidth <= 1200);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('pigo_sidebar_collapsed') === 'true');
  function toggleSidebarCollapsed() {
    setSidebarCollapsed((previous) => {
      localStorage.setItem('pigo_sidebar_collapsed', String(!previous));
      return !previous;
    });
  }
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  useEffect(() => {
    function handleResize() {
      const isResponsive = window.innerWidth <= 1200;
      setIsMobileOrTablet(isResponsive);

      if (!isResponsive) {
        setSidebarOpen(false);
      }
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  function handleToggleSidebar() {
    if (isMobileOrTablet) {
      setSidebarOpen((prev) => !prev);
    } else {
      toggleSidebarCollapsed();
    }
  }

  function handleCloseSidebar() {
    setSidebarOpen(false);
  }


  const sharedLayoutProps = {
    onToggleSidebar: handleToggleSidebar,
    isMobileOrTablet,
    theme,
    toggleTheme,
  };

  return (
    <div
      className={`app-shell notranslate ${referenceLayout ? "reference-layout" : ""} ${isMobileOrTablet ? "mobile-mode" : ""} ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}
      translate="no"
    >
      {!isMobileOrTablet && (
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapsed={toggleSidebarCollapsed}
          isMobileOrTablet={isMobileOrTablet}
          isOpen={sidebarOpen}
          onClose={handleCloseSidebar}
        />
      )}

      {isMobileOrTablet && (
        <BottomNavigation />
      )}

      <div className="app-content">
        <Routes>
          <Route path="/" element={<Navigate to={firstAllowedPath(user)} replace />} />

          <Route
            path="/dashboard/consolidado"
            element={<DashboardConsolidado {...sharedLayoutProps} />}
          />

          <Route path="/dashboard/vendas" element={<DashboardVendas {...sharedLayoutProps} />} />
          <Route path="/dashboard/vendas/detalhes" element={<DetalhesPedidos {...sharedLayoutProps} />} />
          <Route
            path="/dashboard/financeiro"
            element={<DashboardFinanceiro {...sharedLayoutProps} />}
          />
          <Route
            path="/dashboard/estoque"
            element={<DashboardEstoque {...sharedLayoutProps} />}
          />
          <Route path="/estoque" element={<Navigate to="/dashboard/estoque" replace />} />
          <Route path="/dashboard/clientes" element={<CommercialAnalytics mode="clientes" {...sharedLayoutProps} />} />
          <Route path="/dashboard/curva-abc" element={<CommercialAnalytics mode="abc" {...sharedLayoutProps} />} />
          <Route path="/dashboard/metas" element={<SalesGoals {...sharedLayoutProps} />} />
          {OPERATIONS.map((operation) => <Route key={operation.path} path={operation.path} element={<Operations {...operation} {...sharedLayoutProps} />} />)}

          {['usuarios','perfis','permissoes'].map(section => <Route key={section} path={`/acesso/${section}`} element={<Access section={section} {...sharedLayoutProps} />} />)}
          <Route path="/acesso" element={<Navigate to="/acesso/usuarios" replace />} />
          <Route path="/sem-acesso" element={<div className="access-denied"><h1>Acesso não atribuído</h1><p>Solicite ao administrador um perfil com permissões no PIGO.</p><a href="/login">Voltar ao login</a></div>} />
          <Route path="/relatorios" element={<Reports {...sharedLayoutProps} />} />
          <Route path="/relatorios/:categoria" element={<Reports {...sharedLayoutProps} />} />
          <Route path="/relatorios/:categoria/novo" element={<Reports {...sharedLayoutProps} />} />
          <Route path="/relatorios/:categoria/preview-temporario" element={<Reports {...sharedLayoutProps} />} />
          <Route path="/relatorios/:categoria/:reportId/editar" element={<Reports {...sharedLayoutProps} />} />
          <Route path="/relatorios/:categoria/:reportId/preview" element={<Reports {...sharedLayoutProps} />} />

          <Route path="/funcionarios" element={<Funcionarios {...sharedLayoutProps} />} />
          <Route
            path="/funcionarios/novo"
            element={<FuncionarioNovoVinculo {...sharedLayoutProps} />}
          />
          <Route
            path="/funcionarios/:pes_id/analise"
            element={<FuncionarioAnalise {...sharedLayoutProps} />}
          />

          <Route path="/performance" element={<Performance {...sharedLayoutProps} />} />
          <Route
            path="/performance/exclusoes"
            element={<PerformanceExclusoes {...sharedLayoutProps} />}
          />
          <Route
            path="/performance/inclusoes"
            element={<PerformanceInclusoes {...sharedLayoutProps} />}
          />
          <Route
            path="/performance/alteracoes"
            element={<PerformanceAlteracoes {...sharedLayoutProps} />}
          />
          <Route
            path="/performance/cancelamentos"
            element={<PerformanceCancelamentos {...sharedLayoutProps} />}
          />

          <Route path="*" element={<Navigate to={firstAllowedPath(user)} replace />} />
        </Routes>
      </div>

    </div>
  );
}

function PrivateApp() {
  return (
    <ProtectedRoute>
      <AppLayout />
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<PrivateApp />} />
    </Routes>
  );
}
