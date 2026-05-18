import { useState, useEffect } from "react";
import Topbar from "../components/Topbar";
import api from "../services/api";
import { useEmpresa } from "../context/EmpresaContext";
import "../styles/dashboard.css";
import "../styles/topbar.css";

export default function DashboardEstoque({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const { empresaAtual } = useEmpresa();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    resumo: { totalProdutos: 0, ativos: 0, inativos: 0 },
    valores: { custoTotal: 0, vendaTotal: 0 },
    alertas: { total: 0, semEstoque: 0, abaixoMinimo: 0 },
    compras: { quantidade: 0, valorTotal: 0 },
    rotatividade: [],
    criticos: [],
  });
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const formatCurrency = (val) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(val || 0);
  const formatNumber = (val) =>
    new Intl.NumberFormat("pt-BR").format(val || 0);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        
        let url = "/api/dashboard/estoque";
        if (empresaAtual && empresaAtual.id) {
          url += `?empresa_id=${empresaAtual.id}`;
        }
        
        const response = await api.get(url);
        setData(response.data);
        setLastUpdate(new Date());
      } catch (err) {
        console.error("Erro ao buscar dados do dashboard de estoque:", err);
        setError("Não foi possível carregar os dados. Verifique a conexão.");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    // Atualiza a cada 5 minutos
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [empresaAtual]);

  const stockKPIs = [
    { 
      label: "Produtos", 
      value: formatNumber(data.resumo.totalProdutos), 
      sub: `${formatNumber(data.resumo.ativos)} ativos • ${formatNumber(data.resumo.inativos)} inativos`, 
      color: "#2563eb", icon: "📦" 
    },
    { 
      label: "Valor em Estoque (Custo)", 
      value: formatCurrency(data.valores.custoTotal), 
      sub: "", 
      color: "#b48c04", icon: "💲" 
    },
    { 
      label: "Valor em Estoque (Venda)", 
      value: formatCurrency(data.valores.vendaTotal), 
      sub: "", 
      color: "#16a34a", icon: "💲" 
    },
    { 
      label: "Alertas", 
      value: formatNumber(data.alertas.total), 
      sub: `${formatNumber(data.alertas.semEstoque)} sem estoque • ${formatNumber(data.alertas.abaixoMinimo)} abaixo do mínimo`, 
      color: "#ea580c", icon: "⚠️" 
    },
  ];

  const purchaseKPIs = [
    { 
      label: "Compras (Últimos 30 dias)", 
      value: formatNumber(data.compras.quantidade), 
      color: "#2563eb", icon: "📄" 
    },
    { 
      label: "Valor Total de Compras (Últimos 30 dias)", 
      value: formatCurrency(data.compras.valorTotal), 
      color: "#16a34a", icon: "💲" 
    },
  ];

  return (
    <div className="dashboard-page">
      <Topbar
        titulo="Dashboard de Estoque"
        caminho="Dashboard / Estoque"
        subtitulo="Visão geral e monitoramento de inventário"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div style={{ textAlign: 'center', marginBottom: '24px', fontSize: '13px', color: 'var(--text-muted)' }}>
        Dados atualizados automaticamente a cada 5 minutos • Última atualização: {lastUpdate.toLocaleTimeString()}
        {loading && <span style={{ marginLeft: '10px', color: '#2563eb' }}>Atualizando...</span>}
        {error && <span style={{ marginLeft: '10px', color: '#ef4444' }}>{error}</span>}
      </div>

      <div className="cards-grid">
        {stockKPIs.map((kpi, idx) => (
          <div key={idx} className="card-kpi" style={{ backgroundColor: kpi.color, border: 'none', position: 'relative' }}>
            <h3 style={{ color: 'rgba(255,255,255,0.9)', marginBottom: '8px' }}>{kpi.label}</h3>
            <p style={{ color: '#fff', fontSize: isMobileOrTablet ? '22px' : '28px', marginBottom: '8px' }}>{kpi.value}</p>
            {kpi.sub && <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '12px' }}>{kpi.sub}</span>}
            <span style={{ position: 'absolute', right: '20px', bottom: '20px', fontSize: '24px', opacity: 0.5 }}>{kpi.icon}</span>
          </div>
        ))}
      </div>

      <div 
        className="dashboard-main-grid" 
        style={{ 
          gridTemplateColumns: isMobileOrTablet ? '1fr' : '1fr 1fr', 
          gap: '20px', 
          marginTop: '20px', 
          marginBottom: '20px' 
        }}
      >
        {purchaseKPIs.map((kpi, idx) => (
          <div key={idx} className="card-kpi" style={{ backgroundColor: kpi.color, border: 'none', position: 'relative', padding: '24px' }}>
            <h3 style={{ color: 'rgba(255,255,255,0.9)', marginBottom: '8px' }}>{kpi.label}</h3>
            <p style={{ color: '#fff', fontSize: isMobileOrTablet ? '22px' : '28px', marginBottom: '0' }}>{kpi.value}</p>
            <span style={{ position: 'absolute', right: '24px', top: '50%', transform: 'translateY(-50%)', fontSize: '28px', opacity: 0.5 }}>{kpi.icon}</span>
          </div>
        ))}
      </div>

      <div className="two-columns">
        <div className="chart-box premium-box" style={{ padding: '0' }}>
          <div style={{ padding: '24px 24px 12px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800 }}>Produtos por Maior Rotatividade (30 dias)</h3>
          </div>
          <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
            <table className="custom-table premium-table">
              <thead style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--bg-card)' }}>
                <tr>
                  <th style={{ paddingLeft: '24px' }}>Produto</th>
                  <th style={{ textAlign: 'right' }}>Qtd. Vendida</th>
                  <th style={{ textAlign: 'right', paddingRight: '24px' }}>Estoque Atual</th>
                </tr>
              </thead>
              <tbody>
                {data.rotatividade.length === 0 ? (
                   <tr>
                     <td colSpan="3" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>Nenhuma venda registrada nos últimos 30 dias</td>
                   </tr>
                ) : data.rotatividade.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ paddingLeft: '24px', fontSize: '12px', lineHeight: '1.4', maxWidth: isMobileOrTablet ? '180px' : '300px' }}>{item.produto}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatNumber(item.vendida)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, paddingRight: '24px' }}>{formatNumber(item.estoque)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: '16px 24px', fontSize: '12px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)' }}>
            Mostrando primeiros {data.rotatividade.length} itens
          </div>
        </div>

        <div className="chart-box premium-box" style={{ padding: '0' }}>
          <div style={{ padding: '24px 24px 12px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800 }}>Produtos com Estoque Zerado ou Abaixo do Mínimo</h3>
          </div>
          <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
            <table className="custom-table premium-table">
              <thead style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--bg-card)' }}>
                <tr>
                  <th style={{ paddingLeft: '24px' }}>Produto</th>
                  <th style={{ textAlign: 'right' }}>Estoque</th>
                  <th style={{ textAlign: 'right' }}>Mínimo</th>
                  <th style={{ width: '40px' }}></th>
                </tr>
              </thead>
              <tbody>
                {data.criticos.length === 0 ? (
                   <tr>
                     <td colSpan="4" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>Nenhum alerta de estoque</td>
                   </tr>
                ) : data.criticos.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ paddingLeft: '24px', fontSize: '12px', lineHeight: '1.4', maxWidth: isMobileOrTablet ? '180px' : '300px' }}>{item.produto}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: item.estoque <= 0 ? '#ef4444' : 'inherit' }}>{formatNumber(item.estoque)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatNumber(item.minimo)}</td>
                    <td style={{ paddingRight: '24px' }}>
                       <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', marginLeft: 'auto' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: '16px 24px', fontSize: '12px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)' }}>
            Mostrando primeiros {data.criticos.length} itens
          </div>
        </div>
      </div>
    </div>
  );
}

