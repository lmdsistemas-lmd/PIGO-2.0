import DashboardWorkspace, { DashboardBlock } from "../components/DashboardWorkspace";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Topbar from "../components/Topbar";
import DashboardFilters from "../components/DashboardFilters";
import api from "../services/api";
import { useEmpresa } from "../context/EmpresaContext";
import "../styles/dashboard.css";
import "../styles/topbar.css";
import "../styles/dashboard-vendas.css";

const FinancialMap = lazy(() => import("../components/FinancialMap"));

function formatCurrency(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value || 0));
}

function formatNumber(value) {
  return new Intl.NumberFormat("pt-BR").format(Number(value || 0));
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1).replace(".", ",")}%`;
}

const COLORS = [
  "#2563eb",
  "#60a5fa",
  "#7c3aed",
  "#a78bfa",
  "#16a34a",
  "#4ade80",
  "#f59e0b",
  "#fbbf24",
  "#ef4444",
  "#fb7185",
  "#0ea5e9",
  "#14b8a6",
  "#8b5cf6",
  "#22c55e",
];

const MONTH_ORDER = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

function CustomTooltip({ active, payload, label, currency = false }) {
  if (!active || !payload || !payload.length) {
    return null;
  }

  return (
    <div className="vendas-tooltip">
      {label ? <div className="vendas-tooltip-title">{label}</div> : null}

      {payload.map((entry, index) => (
        <div className="vendas-tooltip-row" key={`${entry.name}-${index}`}>
          <span
            className="vendas-tooltip-dot"
            style={{ backgroundColor: entry.color || "#2563eb" }}
          />
          <span className="vendas-tooltip-label">{entry.name}</span>
          <strong className="vendas-tooltip-value">
            {currency ? formatCurrency(entry.value) : formatNumber(entry.value)}
          </strong>
        </div>
      ))}
    </div>
  );
}

function preparePieData(items = [], limit = 8) {
  const normalized = items
    .map((item) => ({
      label: item.label || "Nao informado",
      valor: Number(item.valor || 0),
    }))
    .filter((item) => item.valor > 0)
    .sort((a, b) => b.valor - a.valor);

  if (!normalized.length) {
    return [];
  }

  const topItems = normalized.slice(0, limit);
  const others = normalized.slice(limit);
  const othersTotal = others.reduce((sum, item) => sum + item.valor, 0);

  const merged = othersTotal > 0
    ? [...topItems, { label: "Outros", valor: othersTotal }]
    : topItems;

  const total = merged.reduce((sum, item) => sum + item.valor, 0);

  return merged.map((item, index) => ({
    ...item,
    percent: total > 0 ? (item.valor / total) * 100 : 0,
    color: COLORS[index % COLORS.length],
  }));
}

function DashboardVendas({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const { empresaAtual } = useEmpresa();
  const navigate = useNavigate();

  const [filters, setFilters] = useState({
    period: "today",
    status: "TODOS",
    start: null,
    end: null,
  });

  const [dashboardData, setDashboardData] = useState({
    resumo: {
      faturamento: 0,
      pedidos: 0,
      ticketMedio: 0,
      variation: "Sem base anterior",
    },
    historico: [],
    topClientes: [],
    topProdutos: [],
    vendasPorCidade: [],
    vendasPorVendedor: [],
    vendasPorGrupo: [],
    vendasPorMarca: [],
    mediaPorFaixaHoraria: [],
    mediaPorDiaSemana: [],
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [snapshotPreview,setSnapshotPreview] = useState(false);

  // Estados para Detalhes e Modais
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState(null); // 'pedidos' ou 'clientes'
  const [modalData, setModalData] = useState([]);
  const [modalLoading, setModalLoading] = useState(false);

  const openDetails = async (type) => {
    if (type === 'pedidos') {
      // Para pedidos, abrimos em uma nova aba
      const params = new URLSearchParams();
      params.set("period", filters.period);
      if (filters.period === "custom" && filters.start && filters.end) {
        params.set("start", filters.start);
        params.set("end", filters.end);
      }
      if (empresaAtual?.id) {
        params.set("empresa_id", String(empresaAtual.id));
      }
      navigate(`/dashboard/vendas/detalhes?${params.toString()}`);
      return;
    }

    setModalType(type);
    setShowModal(true);
    setModalLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("period", filters.period);
      if (filters.period === "custom" && filters.start && filters.end) {
        params.set("start", filters.start);
        params.set("end", filters.end);
      }
      if (empresaAtual?.id) {
        params.set("empresa_id", String(empresaAtual.id));
      }

      const endpoint = "/dashboard/vendas/clientes_novos";
      
      const response = await api.get(`${endpoint}?${params.toString()}`);
      setModalData(response.data.data || []);
    } catch (err) {
      console.error("Erro ao buscar detalhes:", err);
    } finally {
      setModalLoading(false);
    }
  };

  function handleFilters(newFilters) {
    setFilters(newFilters);
  }

  useEffect(() => {
    let ignore = false;
    let inFlight = false;
    const controller = new AbortController();

    async function loadDashboard() {
      if (inFlight) return;
      inFlight = true;
      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams();
        params.set("period", filters.period);

        if (filters.period === "custom" && filters.start && filters.end) {
          params.set("start", filters.start);
          params.set("end", filters.end);
        }

        if (empresaAtual?.id) {
          params.set("empresa_id", String(empresaAtual.id));
        }

        const response = await api.get(`/dashboard/vendas?${params.toString()}`, { signal: controller.signal });
        const data = response.data;

        if (!ignore) {
          setSnapshotPreview(response.headers?.["x-pigo-preview"] === "synthetic-snapshot");
          setDashboardData({
            resumo: data?.resumo ?? {
              faturamento: 0,
              pedidos: 0,
              ticketMedio: 0,
              variation: "Sem base anterior",
            },
            historico: data?.historico ?? [],
            topClientes: data?.topClientes ?? [],
            topProdutos: data?.topProdutos ?? [],
            vendasPorCidade: data?.vendasPorCidade ?? [],
            vendasPorVendedor: data?.vendasPorVendedor ?? [],
            vendasPorGrupo: data?.vendasPorGrupo ?? [],
            vendasPorMarca: data?.vendasPorMarca ?? [],
            mediaPorFaixaHoraria: data?.mediaPorFaixaHoraria ?? [],
            mediaPorDiaSemana: data?.mediaPorDiaSemana ?? [],
          });
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Erro ao carregar dados.");
        }
      } finally {
        inFlight = false;
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    if (filters.period === "custom" && (!filters.start || !filters.end)) {
      return;
    }

    loadDashboard();
    const refresh = () => { if (document.visibilityState === "visible") loadDashboard(); };
    const interval = window.setInterval(refresh, 60000);
    window.addEventListener("focus", refresh);

    return () => {
      ignore = true;
      controller.abort();
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
    };
  }, [filters.period, filters.status, filters.start, filters.end, empresaAtual?.id]);

  const historicoMeta = useMemo(() => {
    const raw = dashboardData.historico || [];
    const years = [...new Set(raw.map((item) => Number(item?.ano || 0)).filter(Boolean))].sort(
      (a, b) => b - a
    );

    const anoAtual = years[0] || new Date().getFullYear();
    const anoAnterior = years[1] || anoAtual - 1;

    return { anoAtual, anoAnterior };
  }, [dashboardData.historico]);

  const historicoData = useMemo(() => {
    const raw = dashboardData.historico || [];
    if (!raw.length) return [];

    const hasYearData = raw.some((item) => item?.ano !== undefined && item?.ano !== null);

    if (!hasYearData) {
      return raw.map((item) => ({
        label: item.label,
        anoAtual: Number(item.valor || 0),
        anoAnterior: 0,
      }));
    }

    const years = [...new Set(raw.map((item) => Number(item.ano)).filter(Boolean))].sort((a, b) => b - a);
    const anoAtualRef = years[0] || new Date().getFullYear();
    const anoAnteriorRef = years[1] || anoAtualRef - 1;

    const grouped = {};

    MONTH_ORDER.forEach((month) => {
      grouped[month] = {
        label: month,
        anoAtual: 0,
        anoAnterior: 0,
      };
    });

    raw.forEach((item) => {
      const monthLabel = item.label;
      const ano = Number(item.ano || 0);
      const valor = Number(item.valor || 0);

      if (!grouped[monthLabel]) {
        grouped[monthLabel] = {
          label: monthLabel,
          anoAtual: 0,
          anoAnterior: 0,
        };
      }

      if (ano === anoAtualRef) {
        grouped[monthLabel].anoAtual = valor;
      } else if (ano === anoAnteriorRef) {
        grouped[monthLabel].anoAnterior = valor;
      }
    });

    return MONTH_ORDER.map((month) => grouped[month]).filter(Boolean);
  }, [dashboardData.historico]);

  const faixaData = useMemo(
    () =>
      (dashboardData.mediaPorFaixaHoraria || []).map((item) => ({
        ...item,
        valor: Number(item.valor || 0),
      })),
    [dashboardData.mediaPorFaixaHoraria]
  );

  const diaSemanaData = useMemo(
    () =>
      (dashboardData.mediaPorDiaSemana || []).map((item) => ({
        ...item,
        valor: Number(item.valor || 0),
      })),
    [dashboardData.mediaPorDiaSemana]
  );

  const grupoData = useMemo(
    () => preparePieData(dashboardData.vendasPorGrupo || [], 8),
    [dashboardData.vendasPorGrupo]
  );

  const marcaData = useMemo(
    () => preparePieData(dashboardData.vendasPorMarca || [], 8),
    [dashboardData.vendasPorMarca]
  );

  const maxClienteValor = useMemo(() => {
    if (!dashboardData.topClientes.length) return 1;
    return Math.max(...dashboardData.topClientes.map((item) => Number(item.valor || 0)), 1);
  }, [dashboardData.topClientes]);

  const maxVendedorValor = useMemo(() => {
    if (!dashboardData.vendasPorVendedor.length) return 1;
    return Math.max(
      ...dashboardData.vendasPorVendedor.map((item) => Number(item.valor || 0)),
      1
    );
  }, [dashboardData.vendasPorVendedor]);

  const maxCidadeQuantidade = useMemo(() => {
    if (!dashboardData.vendasPorCidade.length) return 1;
    return Math.max(
      ...dashboardData.vendasPorCidade.map((item) => Number(item.quantidade || 0)),
      1
    );
  }, [dashboardData.vendasPorCidade]);

  return (
    <DashboardWorkspace dashboard="vendas"><div className="dashboard-page">
      <Topbar
        titulo="Dashboard de Vendas"
        caminho="Dashboard / Vendas"
        subtitulo="Visão geral das vendas e performance comercial"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <DashboardFilters onChange={handleFilters} />

      {loading && (
        <div className="status-message info-message">
          Carregando dados do ERP...
        </div>
      )}

      {error && <div className="status-message error-message" role="alert">{error}</div>}

      {/* Primeira Linha: 5 Cards (Performance) */}
      <div className="cards-grid cards-grid-5">
        <DashboardBlock id="vendas-0" title="Vendas" kind="metric"><div 
          className="card-kpi clickable-card" 
          onClick={() => openDetails('pedidos')}
          style={{ background: 'linear-gradient(135deg, #2563eb, #3b82f6)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(37, 99, 235, 0.2)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Vendas</h3>
            <i className="fas fa-dollar-sign"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatCurrency(dashboardData.resumo.faturamento)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span>Hoje</span>
            <span style={{ fontWeight: 700, color: '#ffffff' }}>{dashboardData.resumo.variation}</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-1" title="Ticket Médio" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #059669, #10b981)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(16, 185, 129, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Ticket Médio</h3>
            <i className="fas fa-box"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatCurrency(dashboardData.resumo.ticketMedio)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-2" title="Pedidos" kind="metric"><div 
          className="card-kpi clickable-card" 
          onClick={() => openDetails('pedidos')}
          style={{ background: 'linear-gradient(135deg, #ea580c, #f97316)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(249, 115, 22, 0.2)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Pedidos</h3>
            <i className="fas fa-copy"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatNumber(dashboardData.resumo.pedidos)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-3" title="Itens por venda" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #0891b2, #06b6d4)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(6, 182, 212, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Itens por venda</h3>
            <i className="fas fa-list-ol"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatNumber(dashboardData.resumo.itensPorVenda)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-4" title="Novos Clientes" kind="metric"><div 
          className="card-kpi clickable-card" 
          onClick={() => openDetails('clientes')}
          style={{ background: 'linear-gradient(135deg, #7c3aed, #8b5cf6)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(139, 92, 246, 0.2)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Novos Clientes</h3>
            <i className="fas fa-users"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{dashboardData.topClientes.length}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>
      </div>

      {/* Segunda Linha: 5 Cards (Rentabilidade) */}
      <div className="cards-grid cards-grid-5">
        <DashboardBlock id="vendas-5" title="Total custo (CMV)" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #334155, #475569)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(71, 85, 105, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Total custo (CMV)</h3>
            <i className="fas fa-box-open"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatCurrency(dashboardData.resumo.custoTotal)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-6" title="Lucro bruto" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #0d9488, #14b8a6)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(20, 184, 166, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>Lucro bruto</h3>
            <i className="fas fa-arrow-up"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatCurrency(dashboardData.resumo.lucroBruto)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Hoje</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-7" title="% Margem de lucro" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(99, 102, 241, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>% Margem de lucro</h3>
            <i className="fas fa-chart-pie"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatPercent(dashboardData.resumo.margemLucro)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>% de lucro sobre vendas</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-8" title="% Markup" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #d97706, #f59e0b)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(245, 158, 11, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>% Markup</h3>
            <i className="fas fa-calculator"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatPercent(dashboardData.resumo.markup)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>% de venda sobre custo</span>
          </div>
        </div></DashboardBlock>

        <DashboardBlock id="vendas-9" title="% Lucratividade Real" kind="metric"><div className="card-kpi" style={{ background: 'linear-gradient(135deg, #db2777, #ec4899)', color: '#fff', padding: '16px', borderRadius: '12px', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 4px 15px rgba(236, 72, 153, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.9 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, margin: 0, color: '#fff' }}>% Lucratividade Real</h3>
            <i className="fas fa-chart-line"></i>
          </div>
          <p style={{ fontSize: '20px', fontWeight: 800, margin: '8px 0', color: '#ffffff' }}>{formatPercent(dashboardData.resumo.lucratividade)}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', opacity: 0.9, fontWeight: 500, color: '#ffffff' }}>
            <span style={{ color: '#ffffff' }}>Lucro sobre receitas</span>
          </div>
        </div></DashboardBlock>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .cards-grid .card-kpi p,
        .cards-grid .card-kpi h3,
        .cards-grid .card-kpi span,
        .cards-grid .card-kpi i {
          color: #ffffff !important;
        }
      `}} />

      <DashboardBlock id="vendas-10" title="Faturamento Anual - vs" kind="wide" rows={historicoData} labelKey="label" series={[{"key":"anoAtual","label":"anoAtual"},{"key":"anoAnterior","label":"anoAnterior"}]}><div className="chart-box large premium-box vendas-chart-card">
        <div className="vendas-box-header">
          <h3>
            Faturamento Anual - {historicoMeta.anoAtual} vs {historicoMeta.anoAnterior}
          </h3>
        </div>

        {historicoData.length ? (
          <ResponsiveContainer width="100%" height={330}>
            <AreaChart data={historicoData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorAnoAtual" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity={0.04} />
                </linearGradient>

                <linearGradient id="colorAnoAnterior" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#93c5fd" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#93c5fd" stopOpacity={0.02} />
                </linearGradient>
              </defs>

              <CartesianGrid stroke="#e9eef7" vertical={false} strokeDasharray="4 4" />
              <XAxis
                dataKey="label"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#64748b", fontSize: 12 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#64748b", fontSize: 12 }}
              />
              <Tooltip content={<CustomTooltip currency />} />

              <Area
                type="monotone"
                dataKey="anoAtual"
                name={String(historicoMeta.anoAtual)}
                stroke="#2563eb"
                strokeWidth={2.6}
                fill="url(#colorAnoAtual)"
                dot={{ r: 3, fill: "#2563eb", stroke: "#ffffff", strokeWidth: 1.5 }}
                activeDot={{ r: 5 }}
              />

              <Area
                type="monotone"
                dataKey="anoAnterior"
                name={String(historicoMeta.anoAnterior)}
                stroke="#93c5fd"
                strokeWidth={2.3}
                fill="url(#colorAnoAnterior)"
                dot={{ r: 3, fill: "#93c5fd", stroke: "#ffffff", strokeWidth: 1.5 }}
                activeDot={{ r: 5 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">Nenhum dado encontrado para o histórico de vendas.</div>
        )}
      </div></DashboardBlock>

      <div className="two-columns">
        <DashboardBlock id="vendas-11" title="Média por Faixa Horária" kind="chart" rows={faixaData} labelKey="faixa" series={[{"key":"valor","label":"Ticket Médio"}]}><div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Média por Faixa Horária</h3>
          </div>

          {faixaData.length ? (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={faixaData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorFaixa" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.42} />
                    <stop offset="100%" stopColor="#7c3aed" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e9eef7" vertical={false} strokeDasharray="4 4" />
                <XAxis
                  dataKey="faixa"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#64748b", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#64748b", fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip currency />} />
                <Area
                  type="monotone"
                  dataKey="valor"
                  name="Ticket Médio"
                  stroke="#7c3aed"
                  strokeWidth={2.5}
                  fill="url(#colorFaixa)"
                  dot={false}
                  activeDot={{ r: 5 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">Sem dados por faixa horária.</div>
          )}
        </div></DashboardBlock>

        <DashboardBlock id="vendas-12" title="Média por Dia da Semana" kind="chart" rows={diaSemanaData} labelKey="dia" series={[{"key":"valor","label":"Ticket Médio"}]}><div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Média por Dia da Semana</h3>
          </div>

          {diaSemanaData.length ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={diaSemanaData} barCategoryGap={22}>
                <CartesianGrid stroke="#e9eef7" vertical={false} strokeDasharray="4 4" />
                <XAxis
                  dataKey="dia"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#64748b", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#64748b", fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip currency />} />
                <Bar
                  dataKey="valor"
                  name="Ticket Médio"
                  fill="#3b82f6"
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">Sem dados por dia da semana.</div>
          )}
        </div></DashboardBlock>
      </div>

      <div className="two-columns">
        <DashboardBlock id="vendas-13" title="Produtos mais Vendidos" kind="table" rows={dashboardData.topProdutos} labelKey="produto" series={[{"key":"valor","label":"Valor"}]}><div className="table-box premium-box">
          <div className="vendas-box-header">
            <h3>Produtos mais Vendidos</h3>
          </div>

          {dashboardData.topProdutos.length ? (
            <div className="table-responsive">
              <table className="custom-table premium-table">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th>Qtd</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.topProdutos.slice(0, 5).map((produto) => (
                    <tr key={`${produto.produto}-${produto.valor}`}>
                      <td>{produto.produto}</td>
                      <td>{formatNumber(produto.quantidade)}</td>
                      <td>{formatCurrency(produto.valor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">Sem dados.</div>
          )}
        </div></DashboardBlock>

        <DashboardBlock id="vendas-14" title="Top Clientes" kind="table" rows={dashboardData.topClientes} labelKey="nome" series={[{"key":"valor","label":"Valor"}]}><div className="table-box premium-box">
          <div className="vendas-box-header">
            <h3>Top Clientes</h3>
          </div>

          {dashboardData.topClientes.length ? (
            <div className="table-responsive">
              <table className="custom-table premium-table">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th>Pedidos</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.topClientes.slice(0, 5).map((cliente) => (
                    <tr key={cliente.nome}>
                      <td>{cliente.nome}</td>
                      <td>{cliente.pedidos}</td>
                      <td>{formatCurrency(cliente.valor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">Sem dados.</div>
          )}
        </div></DashboardBlock>
      </div>

      <div className="two-columns">
        <DashboardBlock id="vendas-15" title="Vendas por Grupo" kind="chart" rows={grupoData} labelKey="label" series={[{"key":"valor","label":"Valor"}]}><div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Vendas por Grupo</h3>
          </div>

          {grupoData.length ? (
            <div className="vendas-pie-layout">
              <div className="vendas-pie-chart-side">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={grupoData}
                      dataKey="valor"
                      nameKey="label"
                      cx="42%"
                      outerRadius={95}
                      innerRadius={48}
                      paddingAngle={3}
                      labelLine={false}
                    >
                      {grupoData.map((entry) => (
                        <Cell key={`grupo-${entry.label}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip currency />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="vendas-pie-legend-side">
                <div className="vendas-pie-legend-list">
                  {grupoData.map((item) => (
                    <div className="vendas-pie-legend-item" key={`grupo-legenda-${item.label}`}>
                      <span
                        className="vendas-pie-legend-color"
                        style={{ backgroundColor: item.color }}
                      />
                      <div className="vendas-pie-legend-text">
                        <strong>{item.label}</strong>
                        <span>
                          {formatPercent(item.percent)} • {formatCurrency(item.valor)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">Nenhum grupo encontrado no período.</div>
          )}
        </div></DashboardBlock>

        <DashboardBlock id="vendas-16" title="Vendas por Marcas" kind="chart" rows={marcaData} labelKey="label" series={[{"key":"valor","label":"Valor"}]}><div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Vendas por Marcas</h3>
          </div>

          {marcaData.length ? (
            <div className="vendas-pie-layout">
              <div className="vendas-pie-chart-side">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={marcaData}
                      dataKey="valor"
                      nameKey="label"
                      cx="42%"
                      outerRadius={95}
                      innerRadius={48}
                      paddingAngle={3}
                      labelLine={false}
                    >
                      {marcaData.map((entry) => (
                        <Cell key={`marca-${entry.label}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip currency />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="vendas-pie-legend-side">
                <div className="vendas-pie-legend-list">
                  {marcaData.map((item) => (
                    <div className="vendas-pie-legend-item" key={`marca-legenda-${item.label}`}>
                      <span
                        className="vendas-pie-legend-color"
                        style={{ backgroundColor: item.color }}
                      />
                      <div className="vendas-pie-legend-text">
                        <strong>{item.label}</strong>
                        <span>
                          {formatPercent(item.percent)} • {formatCurrency(item.valor)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">Nenhuma marca encontrada no período.</div>
          )}
        </div></DashboardBlock>
      </div>

      <div className="two-columns">
        <DashboardBlock id="vendas-17" title="Top Clientes" kind="chart" rows={dashboardData.topClientes} labelKey="nome" series={[{"key":"valor","label":"Valor"}]}><div className="chart-box premium-box">
          <div className="vendas-box-header">
            <h3>Top Clientes</h3>
          </div>

          {dashboardData.topClientes.length ? (
            <div className="vendas-ranking-list">
              {dashboardData.topClientes.map((cliente) => {
                const width = (Number(cliente.valor || 0) / maxClienteValor) * 100;

                return (
                  <div className="vendas-ranking-item" key={cliente.nome}>
                    <div className="vendas-ranking-top">
                      <div className="vendas-ranking-main">
                        <strong>{cliente.nome}</strong>
                        <span>{formatNumber(cliente.pedidos)} pedidos</span>
                      </div>
                      <div className="vendas-ranking-value">
                        {formatCurrency(cliente.valor)}
                      </div>
                    </div>

                    <div className="vendas-progress-track">
                      <div
                        className="vendas-progress-fill blue"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">Nenhum cliente encontrado no período.</div>
          )}
        </div></DashboardBlock>

        <DashboardBlock id="vendas-18" title="Vendas por Vendedor" kind="chart" rows={dashboardData.vendasPorVendedor} labelKey="vendedor" series={[{"key":"valor","label":"Valor"}]}><div className="chart-box premium-box">
          <div className="vendas-box-header">
            <h3>Vendas por Vendedor</h3>
          </div>

          {dashboardData.vendasPorVendedor.length ? (
            <div className="vendas-ranking-list">
              {dashboardData.vendasPorVendedor.map((vendedor) => {
                const width = (Number(vendedor.valor || 0) / maxVendedorValor) * 100;

                return (
                  <div
                    className="vendas-ranking-item"
                    key={`${vendedor.vendedor}-${vendedor.valor}`}
                  >
                    <div className="vendas-ranking-top">
                      <div className="vendas-ranking-main">
                        <strong>{vendedor.vendedor}</strong>
                        <span>{formatNumber(vendedor.pedidos)} pedidos</span>
                      </div>
                      <div className="vendas-ranking-value">
                        {formatCurrency(vendedor.valor)}
                      </div>
                    </div>

                    <div className="vendas-progress-track">
                      <div
                        className="vendas-progress-fill green"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">Nenhum vendedor encontrado no período.</div>
          )}
        </div></DashboardBlock>
      </div>

      <DashboardBlock id="vendas-19" title="Vendas por Cidade" kind="chart" rows={dashboardData.vendasPorCidade} labelKey="cidade" series={[{"key":"quantidade","label":"Pedidos"}]}><div className="chart-box premium-box">
        <div className="vendas-box-header">
          <h3>Vendas por Cidade</h3>
        </div>

        {dashboardData.vendasPorCidade.length ? (
          <div className="vendas-distribution-list">
            {dashboardData.vendasPorCidade.map((cidade) => {
              const width = (Number(cidade.quantidade || 0) / maxCidadeQuantidade) * 100;

              return (
                <div className="vendas-distribution-item" key={cidade.cidade}>
                  <div className="vendas-distribution-header">
                    <span>{cidade.cidade}</span>
                    <strong>{formatNumber(cidade.quantidade)}</strong>
                  </div>

                  <div className="vendas-progress-track">
                    <div
                      className="vendas-progress-fill purple"
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">Nenhuma cidade encontrada no período.</div>
        )}
      </div></DashboardBlock>
      <DashboardBlock id="vendas-mapa" title="Mapa de vendas por município" kind="map"><section className="chart-box"><h3>Mapa de vendas por município</h3><p className="financial-map-caption">{snapshotPreview ? "Prévia: fotografia de pedidos fictícios por município. Não acompanha um ERP." : "Pedidos faturados por município, conforme dados sincronizados do ERP. Consulta atualizada a cada minuto."}</p><Suspense fallback={<p>Carregando mapa…</p>}><FinancialMap cities={dashboardData.vendasPorCidade} metricLabel="Vendas" /></Suspense></section></DashboardBlock>

      {/* Modal de Detalhes renderizado via Portal para ignorar contexto de stacking */}
      {showModal && createPortal(
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{modalType === 'pedidos' ? 'Listagem de Pedidos' : 'Novos Clientes'}</h2>
                <p>Período selecionado: {filters.period === 'today' ? 'Hoje' : filters.period === 'month' ? 'Este Mês' : 'Personalizado'}</p>
                <small>{modalData.length} registros encontrados</small>
              </div>
              <button className="modal-close" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            
            <div className="modal-body">
              {modalLoading ? (
                <div className="modal-loading">Buscando detalhes no ERP...</div>
              ) : modalData.length === 0 ? (
                <div className="empty-state">Nenhum registro encontrado para este filtro.</div>
              ) : (
                <div className="modal-table-wrapper">
                  {modalType === 'pedidos' ? (
                    <table className="modal-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Data</th>
                          <th>Cliente</th>
                          <th style={{ textAlign: 'right' }}>Valor</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {modalData.map((item) => (
                          <tr key={item.id}>
                            <td>#{item.id}</td>
                            <td>{new Date(item.data).toLocaleDateString('pt-BR')}</td>
                            <td>{item.cliente}</td>
                            <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatCurrency(item.valor)}</td>
                            <td>
                              <span className={`status-badge ${item.status.toLowerCase()}`}>
                                {item.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="client-list">
                      {modalData.map((item) => (
                        <div className="client-item" key={item.id}>
                          <div className="client-info">
                            <strong>{item.nome}</strong>
                            {item.fantasia && <span>{item.fantasia}</span>}
                            <small>Cadastro: {new Date(item.data_cadastro).toLocaleDateString('pt-BR')}</small>
                          </div>
                          <div className="client-id">ID: {item.id}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      <style dangerouslySetInnerHTML={{ __html: `
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(10px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 200000;
          padding: 20px;
          animation: fadeIn 0.2s ease;
        }
        
        /* Regras globais aplicadas ao body quando modal está aberto */
        body.modal-open-active {
          overflow: hidden !important;
        }
        body.modal-open-active .sidebar {
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s ease;
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .modal-container {
          background: var(--bg-card);
          width: 100%;
          max-width: 900px;
          max-height: 85vh;
          border-radius: 24px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          border: 1px solid var(--border-color);
          animation: slideUp 0.3s ease;
        }
        @keyframes slideUp { from { transform: translateY(30px); } to { transform: translateY(0); } }

        .modal-header {
          padding: 24px 32px;
          border-bottom: 1px solid var(--border-color);
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }
        .modal-header h2 { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
        .modal-header p { color: var(--text-muted); font-size: 14px; margin: 0; }
        .modal-header small { color: var(--primary); font-weight: 700; text-transform: uppercase; font-size: 11px; }

        .modal-close {
          background: #f1f5f9;
          border: none;
          width: 40px;
          height: 40px;
          border-radius: 50%;
          font-size: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: #64748b;
          transition: 0.2s;
        }
        .modal-close:hover { background: #e2e8f0; color: #0f172a; transform: rotate(90deg); }

        .modal-body {
          padding: 0;
          overflow-y: auto;
          flex: 1;
        }
        .modal-loading { padding: 60px; text-align: center; color: var(--primary); font-weight: 700; }

        .modal-table-wrapper { padding: 0; }
        .modal-table { width: 100%; border-collapse: collapse; }
        .modal-table th { background: #f8fafc; padding: 16px 32px; text-align: left; font-size: 13px; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; position: sticky; top: 0; }
        .modal-table td { padding: 16px 32px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        
        .status-badge { padding: 4px 10px; border-radius: 99px; font-size: 11px; font-weight: 800; text-transform: uppercase; }
        .status-badge.concluido { background: #dcfce7; color: #166534; }
        .status-badge.aberto { background: #fef9c3; color: #854d0e; }
        .status-badge.faturado { background: #dbeafe; color: #1e40af; }

        .client-list { display: flex; flex-direction: column; }
        .client-item { padding: 20px 32px; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; }
        .client-item:hover { background: #f8fafc; }
        .client-info { display: flex; flex-direction: column; gap: 4px; }
        .client-info strong { font-size: 15px; color: #0f172a; }
        .client-info span { font-size: 13px; color: #64748b; }
        .client-info small { color: var(--primary); font-weight: 600; font-size: 12px; }
        .client-id { font-size: 12px; color: #94a3b8; background: #f1f5f9; padding: 4px 10px; border-radius: 6px; }
      `}} />
    </div></DashboardWorkspace>
  );
}


export default DashboardVendas;
