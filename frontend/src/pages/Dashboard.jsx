import Topbar from "../components/Topbar";
import DashboardFilters from "../components/DashboardFilters";
import "../styles/dashboard.css";
import "../styles/topbar.css";

function Dashboard({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  return (
    <div className="dashboard-page">
      <Topbar 
        onToggleSidebar={onToggleSidebar} 
        isMobileOrTablet={isMobileOrTablet} 
        theme={theme} 
        toggleTheme={toggleTheme} 
      />
      <DashboardFilters />

      <div className="cards-grid">
        <div className="card-kpi">
          <h3>Vendas</h3>
          <p>R$ 0,00</p>
          <span>Hoje</span>
        </div>

        <div className="card-kpi">
          <h3>Ticket Médio</h3>
          <p>R$ 0,00</p>
          <span>Hoje</span>
        </div>

        <div className="card-kpi">
          <h3>Pedidos</h3>
          <p>000</p>
          <span>Hoje</span>
        </div>

        <div className="card-kpi">
          <h3>Novos Clientes</h3>
          <p>000</p>
          <span>Hoje</span>
        </div>
      </div>

      <div className="chart-box large">
        <h3>Faturamento Anual</h3>
        <div className="placeholder">Área reservada para gráfico principal</div>
      </div>

      <div className="two-columns">
        <div className="chart-box">
          <h3>Média por Faixa Horária</h3>
          <div className="placeholder">Área reservada para gráfico</div>
        </div>

        <div className="chart-box">
          <h3>Média por Dia da Semana</h3>
          <div className="placeholder">Área reservada para gráfico</div>
        </div>
      </div>

      <div className="table-box">
        <h3>Produtos mais Vendidos</h3>
        <div className="placeholder">Área reservada para tabela</div>
      </div>

      <div className="two-columns">
        <div className="chart-box">
          <h3>Vendas por Grupo</h3>
          <div className="placeholder">Área reservada para gráfico</div>
        </div>

        <div className="chart-box">
          <h3>Vendas por Marcas</h3>
          <div className="placeholder">Área reservada para gráfico</div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;