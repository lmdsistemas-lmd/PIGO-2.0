import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api from "../services/api";
import Topbar from "../components/Topbar";
import DashboardFilters from "../components/DashboardFilters";
import { useEmpresa } from "../context/EmpresaContext";
import "../styles/dashboard.css";

export default function DetalhesPedidos({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { empresaAtual } = useEmpresa();

  const [pedidos, setPedidos] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Parâmetros de Filtro e Paginação
  const period = searchParams.get("period") || "month";
  const start = searchParams.get("start");
  const end = searchParams.get("end");
  const status = searchParams.get("status") || "TODOS";
  const page = parseInt(searchParams.get("page") || "1");
  const pageSize = 10;
  const [selectedPedido, setSelectedPedido] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('itens');
  const [pedidoInfo, setPedidoInfo] = useState(null);
  const [loadingModal, setLoadingModal] = useState(false);

  useEffect(() => {
    async function fetchPedidos() {
      try {
        setLoading(true);
        const params = new URLSearchParams(searchParams);
        if (!params.get("page")) params.set("page", "1");
        if (!params.get("empresa_id") && empresaAtual?.id) params.set("empresa_id", empresaAtual.id);

        const response = await api.get(`/api/dashboard/vendas/pedidos?${params.toString()}`);
        setPedidos(response.data.data);
        setTotal(response.data.total);
      } catch (err) {
        console.error("Erro ao carregar detalhes dos pedidos:", err);
        setError("Não foi possível carregar os dados.");
      } finally {
        setLoading(false);
      }
    }
    fetchPedidos();
  }, [searchParams, empresaAtual?.id]);

  const fetchPedidoDetalhes = async (pedidoId) => {
    try {
      setLoadingModal(true);
      setModalOpen(true);
      setActiveTab('itens');
      const response = await api.get(`/api/dashboard/vendas/pedido/${pedidoId}?empresa_id=${empresaAtual.id}`);
      setPedidoInfo(response.data);
    } catch (err) {
      console.error("Erro ao buscar detalhes do pedido:", err);
    } finally {
      setLoadingModal(false);
    }
  };

  const handleFilters = (newFilters) => {
    const params = new URLSearchParams(searchParams);
    params.set("period", newFilters.period);
    params.set("status", newFilters.status);
    if (newFilters.start) params.set("start", newFilters.start);
    else params.delete("start");
    if (newFilters.end) params.set("end", newFilters.end);
    else params.delete("end");
    
    params.set("page", "1"); 
    setSearchParams(params);
  };

  const handlePageChange = (newPage) => {
    const params = new URLSearchParams(searchParams);
    params.set("page", newPage.toString());
    setSearchParams(params);
  };

  const formatCurrency = (val) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(val || 0);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="dashboard-page">
      <Topbar 
        titulo="Detalhes das Vendas" 
        caminho="Vendas / Detalhes" 
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div style={{ marginTop: '16px' }}>
        <DashboardFilters onChange={handleFilters} />
      </div>

      <div style={{ marginTop: '24px' }}>
        {loading ? (
          <div className="status-message info-message">Buscando dados no ERP...</div>
        ) : error ? (
          <div className="status-message error-message">{error}</div>
        ) : (
          <>
            <div className="chart-box premium-box" style={{ padding: '0', overflow: 'hidden' }}>
              <div className="table-responsive">
                <table className="custom-table premium-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-main)' }}>
                      <th style={{ padding: '20px 24px' }}>ID</th>
                      <th>Data</th>
                      <th>Cliente</th>
                      <th style={{ textAlign: 'right' }}>Valor Total</th>
                      <th style={{ textAlign: 'center' }}>Status</th>
                      <th style={{ textAlign: 'center' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pedidos.length === 0 ? (
                      <tr>
                        <td colSpan="6" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
                          Nenhum pedido encontrado para os filtros selecionados.
                        </td>
                      </tr>
                    ) : pedidos.map((item) => (
                      <tr key={item.id}>
                        <td style={{ padding: '18px 24px', fontWeight: 700, color: 'var(--primary)' }}>#{item.id}</td>
                        <td style={{ fontSize: '13px' }}>{new Date(item.data).toLocaleDateString('pt-BR')}</td>
                        <td style={{ fontWeight: 600 }}>{item.cliente}</td>
                        <td style={{ textAlign: 'right', fontWeight: 800, color: 'var(--text-main)' }}>{formatCurrency(item.valor)}</td>
                        <td style={{ textAlign: 'center' }}>
                          <span className={`status-badge ${item.status.toLowerCase()}`} style={{
                            padding: '6px 14px',
                            borderRadius: '99px',
                            fontSize: '11px',
                            fontWeight: 800,
                            textTransform: 'uppercase',
                            background: item.status.toLowerCase() === 'faturado' || item.status.toLowerCase() === 'concluido' ? '#dcfce7' : 
                                       item.status.toLowerCase() === 'cancelado' ? '#fee2e2' : '#fef9c3',
                            color: item.status.toLowerCase() === 'faturado' || item.status.toLowerCase() === 'concluido' ? '#166534' : 
                                   item.status.toLowerCase() === 'cancelado' ? '#991b1b' : '#854d0e'
                          }}>
                            {item.status}
                          </span>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button 
                            className="action-btn-view" 
                            title="Ver Detalhes"
                            onClick={() => fetchPedidoDetalhes(item.id)}
                          >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                              <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Paginação */}
              <div style={{ 
                padding: '20px 32px', 
                borderTop: '1px solid var(--border-color)', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                background: 'var(--bg-card)'
              }}>
                <div style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
                  Mostrando <strong>{pedidos.length}</strong> de <strong>{total}</strong> registros
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button 
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page === 1}
                    className="pagination-btn"
                  >
                    Anterior
                  </button>
                  <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', fontWeight: 700, color: 'var(--text-main)' }}>
                    Página {page} de {totalPages || 1}
                  </div>
                  <button 
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= totalPages}
                    className="pagination-btn"
                  >
                    Próxima
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <button 
        onClick={() => navigate('/dashboard/vendas')}
        style={{
          marginTop: '24px',
          padding: '14px 28px',
          borderRadius: '14px',
          border: 'none',
          background: 'var(--primary)',
          color: '#fff',
          fontWeight: 700,
          cursor: 'pointer',
          boxShadow: '0 4px 12px rgba(37, 99, 235, 0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}
      >
        <span>&larr;</span> Voltar ao Dashboard
      </button>

      {/* Modal de Detalhes do Pedido */}
      {modalOpen && (
        <div className="modal-overlay">
          <div className="modal-content premium-box">
            <div className="modal-header">
              <div className="modal-header-title">
                <span className="modal-badge">#{pedidoInfo?.cabecalho?.ID}</span>
                <h3>Detalhes do Pedido</h3>
              </div>
              <button className="close-modal" onClick={() => setModalOpen(false)}>&times;</button>
            </div>
            
            <div className="modal-body">
              {loadingModal ? (
                <div className="modal-loader">
                  <div className="spinner"></div>
                  <p>Buscando detalhes do pedido...</p>
                </div>
              ) : (
                <>
                  <div className="modal-info-card">
                    <div className="info-grid">
                      <div className="info-block">
                        <label>Cliente</label>
                        <div className="info-value">{pedidoInfo?.cabecalho?.CLIENTE}</div>
                      </div>
                      <div className="info-block">
                        <label>Vendedor</label>
                        <div className="info-value">{pedidoInfo?.cabecalho?.VENDEDOR}</div>
                      </div>
                      <div className="info-block">
                        <label>Emissão</label>
                        <div className="info-value">{pedidoInfo?.cabecalho?.DATA ? new Date(pedidoInfo.cabecalho.DATA).toLocaleDateString('pt-BR') : '-'}</div>
                      </div>
                      <div className="info-block total-block">
                        <label>Total Geral</label>
                        <div className="info-value total-price">{formatCurrency(pedidoInfo?.cabecalho?.TOTAL)}</div>
                      </div>
                    </div>
                  </div>

                  <div className="modal-tabs">
                    <button 
                      className={`tab-btn ${activeTab === 'itens' ? 'active' : ''}`}
                      onClick={() => setActiveTab('itens')}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
                      Itens do Pedido
                    </button>
                    {(pedidoInfo?.pagamentos?.length > 0 || pedidoInfo?.cabecalho?.STATUS === 'FATURADO') && (
                      <button 
                        className={`tab-btn ${activeTab === 'pagamento' ? 'active' : ''}`}
                        onClick={() => setActiveTab('pagamento')}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                        Pagamento
                      </button>
                    )}
                  </div>

                  <div className="tab-content">
                    {activeTab === 'itens' ? (
                      <div className="items-container">
                        <table className="modal-table-modern">
                          <thead>
                            <tr>
                              <th>Produto</th>
                              <th style={{ textAlign: 'center' }}>Qtd</th>
                              <th style={{ textAlign: 'right' }}>Vunit.</th>
                              <th style={{ textAlign: 'right' }}>Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pedidoInfo?.itens?.map((item, idx) => (
                              <tr key={idx}>
                                <td>
                                  <div className="prod-desc">{item.DESCRICAO}</div>
                                  <div className="prod-id">ID: {item.ID}</div>
                                </td>
                                <td style={{ textAlign: 'center', fontWeight: 600 }}>{item.QTD}</td>
                                <td style={{ textAlign: 'right' }}>{formatCurrency(item.UNITARIO)}</td>
                                <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--text-main)' }}>{formatCurrency(item.TOTAL)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="payment-container">
                        {pedidoInfo?.pagamentos?.length > 0 ? (
                          <div className="payment-list">
                            {pedidoInfo.pagamentos.map((p, idx) => (
                              <div key={idx} className="payment-row">
                                <div className="pay-method">
                                  <div className="pay-icon">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                                  </div>
                                  <span>{p.FORMA}</span>
                                </div>
                                <div className="pay-amount">{formatCurrency(p.VALOR)}</div>
                              </div>
                            ))}
                            <div className="payment-footer">
                              <span>Total Pago</span>
                              <strong>{formatCurrency(pedidoInfo?.cabecalho?.TOTAL)}</strong>
                            </div>
                          </div>
                        ) : (
                          <div className="empty-state">
                            <p>Nenhuma informação de pagamento encontrada para este pedido.</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <style dangerouslySetInnerHTML={{ __html: `
        .pagination-btn {
          padding: 8px 16px;
          border-radius: 10px;
          border: 1px solid var(--border-color);
          background: var(--bg-card);
          cursor: pointer;
          font-weight: 600;
          color: var(--text-main);
          transition: all 0.2s;
        }
        .pagination-btn:disabled {
          cursor: not-allowed;
          opacity: 0.5;
        }
        .pagination-btn:not(:disabled):hover {
          background: var(--bg-main);
          border-color: var(--primary);
          color: var(--primary);
        }
        .action-btn-view {
          background: rgba(37, 99, 235, 0.1);
          color: var(--primary);
          border: none;
          padding: 8px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
        }
        .action-btn-view:hover {
          background: var(--primary);
          color: white;
          transform: scale(1.1);
        }
        
        /* Modal Styles Refined */
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(15, 23, 42, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(8px);
          padding: 20px;
        }
        .modal-content {
          background: var(--bg-card);
          width: 100%;
          max-width: 850px;
          max-height: 90vh;
          border-radius: 24px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
          display: flex;
          flex-direction: column;
          border: 1px solid var(--border-color);
          overflow: hidden;
        }
        .modal-header {
          padding: 20px 24px;
          background: var(--bg-card);
          border-bottom: 1px solid var(--border-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .modal-header-title { display: flex; align-items: center; gap: 12px; }
        .modal-badge {
          background: var(--primary);
          color: white;
          padding: 4px 10px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 800;
        }
        .modal-header h3 { margin: 0; font-size: 18px; font-weight: 800; color: var(--text-main); }
        .close-modal {
          width: 32px; height: 32px; border-radius: 50%; border: none;
          background: var(--bg-main); color: var(--text-muted);
          font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center;
          transition: all 0.2s;
        }
        .close-modal:hover { background: #fee2e2; color: #ef4444; }
        
        .modal-body { padding: 0; overflow-y: auto; }
        
        .modal-info-card { padding: 24px; background: var(--bg-main); border-bottom: 1px solid var(--border-color); }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
        .info-block label { display: block; font-size: 10px; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }
        .info-value { font-size: 14px; font-weight: 700; color: var(--text-main); line-height: 1.4; }
        .total-price { color: var(--primary); font-size: 18px; }
        
        .modal-tabs {
          display: flex;
          padding: 0 24px;
          background: var(--bg-card);
          border-bottom: 1px solid var(--border-color);
          gap: 24px;
        }
        .tab-btn {
          padding: 16px 4px;
          border: none;
          background: none;
          font-size: 14px;
          font-weight: 700;
          color: var(--text-muted);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          position: relative;
          transition: all 0.2s;
        }
        .tab-btn:hover { color: var(--primary); }
        .tab-btn.active { color: var(--primary); }
        .tab-btn.active::after {
          content: '';
          position: absolute;
          bottom: 0; left: 0; right: 0;
          height: 3px;
          background: var(--primary);
          border-radius: 3px 3px 0 0;
        }
        
        .tab-content { padding: 24px; }
        
        .modal-table-modern { width: 100%; border-collapse: collapse; }
        .modal-table-modern th {
          text-align: left; padding: 12px; font-size: 11px;
          text-transform: uppercase; color: var(--text-muted);
          border-bottom: 2px solid var(--bg-main);
        }
        .modal-table-modern td { padding: 16px 12px; border-bottom: 1px solid var(--bg-main); }
        .prod-desc { font-weight: 700; color: var(--text-main); margin-bottom: 4px; font-size: 13px; }
        .prod-id { font-size: 11px; color: var(--text-muted); font-weight: 600; }
        
        .payment-list { display: flex; flex-direction: column; gap: 12px; max-width: 400px; margin: 0 auto; }
        .payment-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 16px; background: var(--bg-main); border-radius: 16px;
          border: 1px solid var(--border-color);
        }
        .pay-method { display: flex; align-items: center; gap: 12px; font-weight: 700; color: var(--text-main); }
        .pay-icon {
          width: 36px; height: 36px; border-radius: 10px;
          background: white; border: 1px solid var(--border-color);
          display: flex; align-items: center; justify-content: center; color: var(--primary);
        }
        .pay-amount { font-weight: 800; color: var(--primary); font-size: 16px; }
        .payment-footer {
          margin-top: 12px; padding: 16px; display: flex; justify-content: space-between;
          border-top: 2px dashed var(--border-color);
        }
        
        .modal-loader { padding: 60px; text-align: center; }
        .spinner {
          width: 40px; height: 40px; border: 4px solid var(--bg-main);
          border-top: 4px solid var(--primary); border-radius: 50%;
          margin: 0 auto 16px; animation: spin 1s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .empty-state { text-align: center; padding: 40px; color: var(--text-muted); font-weight: 600; }
      `}} />
    </div>
  );
}

