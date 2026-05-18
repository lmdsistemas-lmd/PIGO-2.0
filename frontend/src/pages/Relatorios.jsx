import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Topbar from "../components/Topbar";
import "../styles/relatorios.css";
import "../styles/topbar.css";

function Relatorios({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const navigate = useNavigate();

  const [solicitacaoIa, setSolicitacaoIa] = useState(
    "Analise as tendências de vendas dos últimos meses e projete as vendas para o próximo trimestre."
  );
  const [mostrarModalIa, setMostrarModalIa] = useState(false);

  const relatoriosRecentes = useMemo(
    () => [
      {
        id: 1,
        nome: "Resumo de vendas por período",
        periodo: "Últimos 7 dias",
        data: "Hoje",
        acao: "PDF",
      },
      {
        id: 2,
        nome: "Contas a receber em aberto",
        periodo: "Agosto",
        data: "Hoje",
        acao: "PDF",
      },
      {
        id: 3,
        nome: "Fluxo financeiro consolidado",
        periodo: "Mês passado",
        data: "Hoje",
        acao: "PDF",
      },
      {
        id: 4,
        nome: "Notas fiscais emitidas",
        periodo: "Setembro",
        data: "Ontem",
        acao: "PDF",
      },
      {
        id: 5,
        nome: "Produtos com maior giro",
        periodo: "Últimos 30 dias",
        data: "Ontem",
        acao: "PDF",
      },
      {
        id: 6,
        nome: "Lucratividade por categoria",
        periodo: "Últimos 7 dias",
        data: "22/04",
        acao: "PDF",
      },
      {
        id: 7,
        nome: "Análise de inadimplência",
        periodo: "Últimos 7 dias",
        data: "14/02",
        acao: "PDF",
      },
      {
        id: 8,
        nome: "Resumo contábil gerencial",
        periodo: "Últimos 7 dias",
        data: "10/02",
        acao: "PDF",
      },
    ],
    []
  );

  function abrirModalIa() {
    setMostrarModalIa(true);
  }

  function fecharModalIa() {
    setMostrarModalIa(false);
  }

  function preencherExemplo(texto) {
    setSolicitacaoIa(texto);
  }

  return (
    <div className="relatorios-page">
      <Topbar 
      titulo="Relatórios"
      caminho="Dashboard / Relatórios"
      onToggleSidebar={onToggleSidebar}
      isMobileOrTablet={isMobileOrTablet}
      theme={theme}
      toggleTheme={toggleTheme}
       />

      <div className="relatorios-layout">
        <div className="relatorios-left">
          <div className="relatorio-card">
            <div>
              <h3>Relatório de Vendas</h3>
              <p>Vendas e produtos mais vendidos.</p>
            </div>

            <button
              className="relatorio-btn"
              onClick={() => navigate("/relatorios/vendas")}
              type="button"
            >
              Ver Relatórios
            </button>
          </div>

          <div className="relatorio-card">
            <div>
              <h3>Relatório Financeiro</h3>
              <p>Contas a pagar e contas a receber.</p>
            </div>

            <button
              className="relatorio-btn"
              onClick={() => navigate("/relatorios/financeiro")}
              type="button"
            >
              Ver Relatórios
            </button>
          </div>

          <div className="relatorio-card">
            <div>
              <h3>Consultor / Contabilidade</h3>
              <p>Análises de notas fiscais e DREs.</p>
            </div>

            <button
              className="relatorio-btn"
              onClick={() => navigate("/relatorios/consultoria")}
              type="button"
            >
              Ver Relatórios
            </button>
          </div>

          <div className="relatorio-card">
            <div>
              <h3>Relatório Diversos</h3>
              <p>Relatórios extras.</p>
            </div>

            <button
              className="relatorio-btn"
              onClick={() => navigate("/relatorios/diversos")}
              type="button"
            >
              Ver Relatórios
            </button>
          </div>
        </div>

        <div className="relatorios-right">
          <div className="ia-card">
            <div className="ia-card-header">
              <h3>Relatórios com IA</h3>
              <div className="ia-icon">IA</div>
            </div>

            <label className="ia-label">Digite sua solicitação de relatório...</label>

            <textarea
              className="ia-textarea"
              value={solicitacaoIa}
              onChange={(e) => setSolicitacaoIa(e.target.value)}
              placeholder="Descreva o relatório que você deseja gerar..."
            />

            <button className="ia-btn" onClick={abrirModalIa} type="button">
              Gerar com IA
            </button>
          </div>

          <div className="ia-exemplos-card">
            <h4>Exemplos de Solicitação</h4>

            <button
              className="exemplo-item"
              onClick={() => preencherExemplo("Criar um resumo financeiro.")}
              type="button"
            >
              Criar um resumo financeiro
            </button>

            <button
              className="exemplo-item"
              onClick={() => preencherExemplo("Analisar contas em atraso.")}
              type="button"
            >
              Analisar contas em atraso
            </button>

            <button
              className="exemplo-item"
              onClick={() =>
                preencherExemplo("Avaliar lucratividade por produto.")
              }
              type="button"
            >
              Avaliar lucratividade por produto
            </button>
          </div>
        </div>
      </div>

      <div className="relatorios-table-box">
        <div className="relatorios-table-header">
          <h3>Relatórios Recentes</h3>
        </div>

        <div className="relatorios-table-responsive">
          <table className="relatorios-table">
            <thead>
              <tr>
                <th>Relatório</th>
                <th>Período</th>
                <th>Data</th>
                <th>Ações</th>
              </tr>
            </thead>

            <tbody>
              {relatoriosRecentes.map((item) => (
                <tr key={item.id}>
                  <td>{item.nome}</td>
                  <td>{item.periodo}</td>
                  <td>{item.data}</td>
                  <td>
                    <button className="pdf-link" type="button">
                      {item.acao}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {mostrarModalIa && (
        <div className="modal-overlay" onClick={fecharModalIa}>
          <div
            className="modal-box"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Função em desenvolvimento</h3>
            <p>
              A geração de relatórios com IA já está prevista no sistema, mas
              ainda não foi desenvolvida no backend.
            </p>
            <p>
              Por enquanto, esta tela está pronta apenas para simular a
              experiência do usuário.
            </p>

            <button className="modal-btn" onClick={fecharModalIa} type="button">
              Fechar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Relatorios;
