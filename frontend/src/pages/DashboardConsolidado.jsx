import { useEffect, useMemo, useState } from "react";
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
  Legend
} from "recharts";
import Topbar from "../components/Topbar";
import DashboardFilters from "../components/DashboardFilters";
import api from "../services/api";
import "../styles/dashboard.css";
import "../styles/dashboard-vendas.css";

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

function formatAxisValue(value) {
  const num = Number(value || 0);
  if (num >= 1000000) return `${(num / 1000000).toFixed(1).replace(".", ",")}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return String(num);
}

const COLORS = [
  "#2563eb",
  "#16a34a",
  "#7c3aed",
  "#f59e0b",
  "#ef4444",
  "#0ea5e9",
  "#8b5cf6",
  "#22c55e",
];

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

export default function DashboardConsolidado({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const [filters, setFilters] = useState({
    period: "this_month",
    start: null,
    end: null,
  });

  const [data, setData] = useState({
    cards: {
      faturamento_total: 0,
      total_vendas: 0,
      ticket_medio: 0,
      filiais_ativas: 0
    },
    resumo_filiais: [],
    graficos: {
      vendas_dia_semana: [],
      vendas_mensais: []
    }
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError("");
        const params = new URLSearchParams();
        params.set("period", filters.period);
        if (filters.start) params.set("start", filters.start);
        if (filters.end) params.set("end", filters.end);

        const response = await api.get(`/api/dashboard/consolidado?${params.toString()}`);
        setData(response.data);
      } catch (err) {
        setError("Erro ao carregar dados consolidados.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [filters]);

  const pieData = useMemo(() => {
    return data.resumo_filiais.map((f, i) => ({
      name: f.nome,
      value: f.faturamento,
      color: COLORS[i % COLORS.length],
      percent: f.participacao
    }));
  }, [data.resumo_filiais]);

  const filiaisNomes = useMemo(() => {
    const nomes = new Set();
    data.graficos.vendas_dia_semana.forEach(d => {
      Object.keys(d).forEach(k => {
        if (k !== "name") nomes.add(k);
      });
    });
    return Array.from(nomes);
  }, [data.graficos.vendas_dia_semana]);

  return (
    <div className="dashboard-page">
      <Topbar
        titulo="Consolidado de Filiais"
        caminho="Dashboard / Consolidado"
        subtitulo="Visão unificada de performance de toda a rede"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <DashboardFilters onChange={setFilters} />

      {loading && <div className="status-message info-message">Carregando dados consolidados...</div>}
      {error && <div className="status-message error-message">{error}</div>}

      <div className="cards-grid">
        <div className="card-kpi card-kpi-premium">
          <h3>Faturamento Total</h3>
          <p>{formatCurrency(data.cards.faturamento_total)}</p>
          <span>Rede Completa</span>
        </div>
        <div className="card-kpi card-kpi-soft" style={{ borderLeft: '4px solid #7c3aed' }}>
          <h3>Total de Vendas</h3>
          <p>{formatNumber(data.cards.total_vendas)}</p>
          <span>Rede Completa</span>
        </div>
        <div className="card-kpi card-kpi-soft" style={{ borderLeft: '4px solid #16a34a' }}>
          <h3>Ticket Médio</h3>
          <p>{formatCurrency(data.cards.ticket_medio)}</p>
          <span>Média da Rede</span>
        </div>
        <div className="card-kpi card-kpi-soft" style={{ borderLeft: '4px solid #f59e0b' }}>
          <h3>Filiais Ativas</h3>
          <p>{data.cards.filiais_ativas}</p>
          <span>No Período</span>
        </div>
      </div>

      <div className="two-columns">
        <div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Participação no Faturamento</h3>
          </div>
          {pieData.length ? (
            <div className="vendas-pie-layout">
              <div className="vendas-pie-chart-side">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip currency />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="vendas-pie-legend-side">
                <div className="vendas-pie-legend-list">
                  {pieData.map((item, index) => (
                    <div className="vendas-pie-legend-item" key={index}>
                      <span className="vendas-pie-legend-color" style={{ backgroundColor: item.color }} />
                      <div className="vendas-pie-legend-text">
                        <strong>{item.name}</strong>
                        <span>{formatPercent(item.percent)} • {formatCurrency(item.value)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">Nenhuma filial encontrada no período.</div>
          )}
        </div>

        <div className="chart-box premium-box vendas-chart-card">
          <div className="vendas-box-header">
            <h3>Ticket Médio por Filial</h3>
          </div>
          {data.resumo_filiais.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.resumo_filiais} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="nome" type="category" axisLine={false} tickLine={false} width={100} fontSize={12} />
                <Tooltip content={<CustomTooltip currency />} />
                <Bar dataKey="ticket_medio" name="Ticket Médio" radius={[0, 4, 4, 0]}>
                  {data.resumo_filiais.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">Sem dados.</div>
          )}
        </div>
      </div>

      <div className="chart-box large premium-box vendas-chart-card">
        <div className="vendas-box-header">
          <h3>Vendas por Dia da Semana</h3>
        </div>
        {data.graficos.vendas_dia_semana.length ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.graficos.vendas_dia_semana}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
              <YAxis axisLine={false} tickLine={false} tickFormatter={formatAxisValue} tick={{ fontSize: 11, fill: '#64748b' }} width={45} />
              <Tooltip content={<CustomTooltip currency />} />
              <Legend />
              {filiaisNomes.map((name, index) => (
                <Bar key={name} dataKey={name} fill={COLORS[index % COLORS.length]} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">Sem dados por dia da semana.</div>
        )}
      </div>

      <div className="chart-box large premium-box vendas-chart-card">
        <div className="vendas-box-header">
          <h3>Vendas Mensais por Filial</h3>
        </div>
        {data.graficos.vendas_mensais.length ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.graficos.vendas_mensais}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
              <YAxis axisLine={false} tickLine={false} tickFormatter={formatAxisValue} tick={{ fontSize: 11, fill: '#64748b' }} width={45} />
              <Tooltip content={<CustomTooltip currency />} />
              <Legend />
              {filiaisNomes.map((name, index) => (
                <Area 
                  key={name} 
                  type="monotone" 
                  dataKey={name} 
                  stroke={COLORS[index % COLORS.length]} 
                  fill={COLORS[index % COLORS.length]} 
                  fillOpacity={0.1} 
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">Sem dados mensais.</div>
        )}
      </div>

      <div className="table-box premium-box" style={{ marginTop: '24px' }}>
        <div className="vendas-box-header">
          <h3>Indicadores Detalhados por Filial</h3>
        </div>
        <div className="table-responsive">
          <table className="custom-table premium-table">
            <thead>
              <tr>
                <th>Filial</th>
                <th>Faturamento</th>
                <th>Participação</th>
                <th>Ticket Médio</th>
                <th>Vendas</th>
              </tr>
            </thead>
            <tbody>
              {data.resumo_filiais.map((f) => (
                <tr key={f.id}>
                  <td><strong>{f.nome}</strong></td>
                  <td>{formatCurrency(f.faturamento)}</td>
                  <td>{formatPercent(f.participacao)}</td>
                  <td>{formatCurrency(f.ticket_medio)}</td>
                  <td>{formatNumber(f.vendas)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
