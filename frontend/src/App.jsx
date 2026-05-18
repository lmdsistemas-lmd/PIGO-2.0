import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import DashboardVendas from "./pages/DashboardVendas";
import DashboardFinanceiro from "./pages/DashboardFinanceiro";
import DashboardEstoque from "./pages/DashboardEstoque";
import DashboardConsolidado from "./pages/DashboardConsolidado";
import DetalhesPedidos from "./pages/DetalhesPedidos";
import Relatorios from "./pages/Relatorios";
import RelatoriosVendas from "./pages/RelatoriosVendas";
import RelatorioPreviewPage from "./pages/RelatorioPreviewPage";
import RelatoriosFinanceiro from "./pages/RelatoriosFinanceiro";
import RelatoriosConsultoria from "./pages/RelatoriosConsultoria";
import RelatoriosDiversos from "./pages/RelatoriosDiversos";
import Funcionarios from "./pages/Funcionarios";
import FuncionarioNovoVinculo from "./pages/FuncionarioNovoVinculo";
import FuncionarioAnalise from "./pages/FuncionarioAnalise";
import Performance from "./pages/Performance";
import PerformanceExclusoes from "./pages/PerformanceExclusoes";
import PerformanceInclusoes from "./pages/PerformanceInclusoes";
import PerformanceAlteracoes from "./pages/PerformanceAlteracoes";
import PerformanceCancelamentos from "./pages/PerformanceCancelamentos";
import Login from "./pages/Login";
import ProtectedRoute from "./routes/ProtectedRoute";
import BottomNavigation from "./components/BottomNavigation";

function AppLayout() {
  const [isMobileOrTablet, setIsMobileOrTablet] = useState(window.innerWidth <= 1200);
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    <div className={`app-shell notranslate ${isMobileOrTablet ? "mobile-mode" : ""}`} translate="no">
      {!isMobileOrTablet && (
        <Sidebar
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
          <Route path="/" element={<Navigate to="/dashboard/vendas" replace />} />

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

          <Route path="/relatorios" element={<Relatorios {...sharedLayoutProps} />} />
          <Route
            path="/relatorios/vendas"
            element={<RelatoriosVendas {...sharedLayoutProps} />}
          />
          <Route
            path="/relatorios/preview"
            element={<RelatorioPreviewPage {...sharedLayoutProps} />}
          />
          <Route
            path="/relatorios/financeiro"
            element={<RelatoriosFinanceiro {...sharedLayoutProps} />}
          />
          <Route
            path="/relatorios/consultoria"
            element={<RelatoriosConsultoria {...sharedLayoutProps} />}
          />
          <Route
            path="/relatorios/diversos"
            element={<RelatoriosDiversos {...sharedLayoutProps} />}
          />

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

          <Route path="*" element={<Navigate to="/dashboard/vendas" replace />} />
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
