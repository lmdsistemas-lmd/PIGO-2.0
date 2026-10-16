import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Topbar from "../components/Topbar";
import api from "../services/api";
import "../styles/dashboard.css";
import "../styles/topbar.css";
import "../styles/performance.css";

function obterDataHoje() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = String(hoje.getMonth() + 1).padStart(2, "0");
  const dia = String(hoje.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function obterPrimeiroDiaMesAtual() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = String(hoje.getMonth() + 1).padStart(2, "0");
  return `${ano}-${mes}-01`;
}

function formatarData(valor) {
  if (!valor) return "-";

  const texto = String(valor).slice(0, 10);
  const partes = texto.split("-");
  if (partes.length !== 3) return valor;

  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

function formatarHora(valor) {
  if (!valor) return "-";
  return String(valor).slice(0, 8);
}

function obterCodigoTipo(tipo) {
  if (tipo === "inclusoes") return "I";
  if (tipo === "alteracoes") return "A";
  if (tipo === "exclusoes") return "E";
  if (tipo === "cancelamentos") return "C";
  return "";
}

function obterTitulo(tipo) {
  if (tipo === "inclusoes") return "Inclusões";
  if (tipo === "alteracoes") return "Alterações";
  if (tipo === "exclusoes") return "Exclusões";
  if (tipo === "cancelamentos") return "Cancelamentos";
  return "Performance";
}

function obterDescricao(tipo) {
  if (tipo === "inclusoes") {
    return "Consulta detalhada das inclusões registradas no ERP.";
  }

  if (tipo === "alteracoes") {
    return "Consulta detalhada das alterações registradas no ERP.";
  }

  if (tipo === "exclusoes") {
    return "Consulta detalhada das exclusões registradas no ERP.";
  }

  if (tipo === "cancelamentos") {
    return "Consulta detalhada dos cancelamentos registrados no ERP.";
  }

  return "Consulta detalhada dos eventos operacionais.";
}

function obterClasseTag(tipo) {
  if (tipo === "inclusoes") return "kpi-inclusao";
  if (tipo === "alteracoes") return "kpi-alteracao";
  if (tipo === "exclusoes") return "kpi-exclusao";
  return "kpi-cancelamento";
}

function PerformanceDetalhePage({ tipo, theme, toggleTheme, onToggleSidebar, isMobileOrTablet }) {
  const navigate = useNavigate();

  const hoje = obterDataHoje();
  const primeiroDiaMesAtual = obterPrimeiroDiaMesAtual();

  const [filtroUsuario, setFiltroUsuario] = useState("");
  const [filtroTabela, setFiltroTabela] = useState("");
  const [dataInicial, setDataInicial] = useState(primeiroDiaMesAtual);
  const [dataFinal, setDataFinal] = useState(hoje);

  const [usuarios, setUsuarios] = useState([]);
  const [tabelas, setTabelas] = useState([]);
  const [registros, setRegistros] = useState([]);

  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  const titulo = obterTitulo(tipo);
  const descricao = obterDescricao(tipo);
  const codigoTipo = obterCodigoTipo(tipo);

  const totalRegistros = useMemo(() => registros.length, [registros]);

  async function carregarFiltros() {
    try {
      const response = await api.get("/performance/filtros", {
        params: { tipo: codigoTipo },
      });

      setUsuarios(Array.isArray(response.data?.usuarios) ? response.data.usuarios : []);
      setTabelas(Array.isArray(response.data?.tabelas) ? response.data.tabelas : []);
    } catch (error) {
      console.error("Erro ao carregar filtros de performance:", error);
      setUsuarios([]);
      setTabelas([]);
    }
  }

  async function carregarRegistros() {
    try {
      setCarregando(true);
      setErro("");

      const params = {
        tipo: codigoTipo,
      };

      if (filtroUsuario) params.usuario = filtroUsuario;
      if (filtroTabela) params.tabela = filtroTabela;
      if (dataInicial) params.data_inicial = dataInicial;
      if (dataFinal) params.data_final = dataFinal;

      const response = await api.get("/performance/registros", { params });

      setRegistros(
      Array.isArray(response.data?.registros) ? response.data.registros : []
      );
    } catch (error) {
      console.error("Erro ao carregar registros de performance:", error);
      setErro("Não foi possível carregar os registros.");
      setRegistros([]);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarFiltros();
  }, [codigoTipo]);

  useEffect(() => {
    carregarRegistros();
  }, [codigoTipo]);

  function limparFiltros() {
    setFiltroUsuario("");
    setFiltroTabela("");
    setDataInicial(primeiroDiaMesAtual);
    setDataFinal(hoje);
    setErro("");
  }

  function aplicarFiltros() {
    setErro("");

    if (dataInicial && !/^\d{4}-\d{2}-\d{2}$/.test(dataInicial)) {
      setErro("A data inicial está inválida.");
      return;
    }

    if (dataFinal && !/^\d{4}-\d{2}-\d{2}$/.test(dataFinal)) {
      setErro("A data final está inválida.");
      return;
    }

    if (dataInicial && dataFinal && dataFinal < dataInicial) {
      setErro("A data final não pode ser menor que a data inicial.");
      return;
    }

    carregarRegistros();
  }

  return (
    <div className="dashboard-page performance-page">
      <Topbar
        titulo={titulo}
        caminho={`Performance / ${titulo}`}
        theme={theme}
        toggleTheme={toggleTheme}
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
      />

      <section className="performance-hero">
        <div className="performance-hero-content">
          <span className="performance-eyebrow">Auditoria operacional</span>
          <h1 className="performance-title">Registros de {titulo.toLowerCase()}</h1>
          <p className="performance-subtitle">{descricao}</p>
        </div>

        <div className="performance-hero-mini-grid">
          <div className="mini-stat-card">
            <span>Tipo selecionado</span>
            <strong>{titulo}</strong>
          </div>

          <div className="mini-stat-card">
            <span>Total listado</span>
            <strong>{totalRegistros}</strong>
          </div>

          <div className="mini-stat-card">
            <span>Período inicial</span>
            <strong>{formatarData(dataInicial)}</strong>
          </div>

          <div className="mini-stat-card">
            <span>Período final</span>
            <strong>{formatarData(dataFinal)}</strong>
          </div>
        </div>
      </section>

      <section className="performance-panel">
        <div className="performance-panel-top">
          <div>
            <h3>Filtros de consulta</h3>
            <p>Use os filtros para localizar registros específicos do ERP.</p>
          </div>

          <div style={{ display: "flex", gap: "12px" }}>
            <button
              className="btn-clear"
              type="button"
              onClick={() => navigate("/performance")}
            >
              Voltar ao painel
            </button>

            <button
              className="btn-refresh"
              onClick={aplicarFiltros}
              type="button"
              disabled={carregando}
            >
              {carregando ? "Carregando..." : "Atualizar registros"}
            </button>
          </div>
        </div>

        <div className="performance-filters-grid">
          <div className="performance-filter-group">
            <label>Usuário</label>
            <select
              value={filtroUsuario}
              onChange={(e) => setFiltroUsuario(e.target.value)}
            >
              <option value="">Todos</option>
              {usuarios.map((usuario, index) => (
                <option key={`${usuario}-${index}`} value={usuario}>
                  {usuario}
                </option>
              ))}
            </select>
          </div>

          <div className="performance-filter-group">
            <label>Tabela</label>
            <select
              value={filtroTabela}
              onChange={(e) => setFiltroTabela(e.target.value)}
            >
              <option value="">Todas</option>
              {tabelas.map((tabela, index) => (
                <option key={`${tabela}-${index}`} value={tabela}>
                  {tabela}
                </option>
              ))}
            </select>
          </div>

          <div className="performance-filter-group">
            <label>Data inicial</label>
            <input
              type="date"
              value={dataInicial}
              onChange={(e) =>
                setDataInicial(String(e.target.value || "").slice(0, 10))
              }
            />
          </div>

          <div className="performance-filter-group">
            <label>Data final</label>
            <input
              type="date"
              value={dataFinal}
              onChange={(e) =>
                setDataFinal(String(e.target.value || "").slice(0, 10))
              }
            />
          </div>

          <div className="performance-filter-group">
            <label>Tipo</label>
            <input type="text" value={titulo} disabled />
          </div>

          <div className="performance-filter-actions">
            <button className="btn-clear" onClick={limparFiltros} type="button">
              Limpar filtros
            </button>
          </div>
        </div>

        {carregando && (
          <div className="performance-status info-message">
            Carregando registros...
          </div>
        )}

        {erro && !carregando && (
          <div className="performance-status error-message">{erro}</div>
        )}
      </section>

      <section className="performance-kpi-secondary-grid">
        <div className={`performance-soft-card ${obterClasseTag(tipo)}`}>
          <h3>Tipo do evento</h3>
          <p>{titulo}</p>
          <span>Categoria atual da auditoria</span>
        </div>

        <div className="performance-soft-card">
          <h3>Quantidade</h3>
          <p>{totalRegistros}</p>
          <span>Total de linhas retornadas</span>
        </div>

        <div className="performance-soft-card">
          <h3>Usuário filtrado</h3>
          <p>{filtroUsuario || "Todos"}</p>
          <span>Filtro atual do usuário</span>
        </div>

        <div className="performance-soft-card">
          <h3>Tabela filtrada</h3>
          <p className="performance-soft-card-text">{filtroTabela || "Todas"}</p>
          <span>Filtro atual da tabela</span>
        </div>
      </section>

      <section className="performance-box">
        <div className="performance-section-title">
          <div>
            <h3>Lista de registros</h3>
            <p>Auditoria detalhada dos eventos encontrados.</p>
          </div>
        </div>

        {registros.length === 0 && !carregando ? (
          <div className="performance-empty-state">
            Nenhum registro encontrado com os filtros aplicados.
          </div>
        ) : (
          <div className="performance-table-wrapper">
            <table className="performance-table">
              <thead>
                <tr>
                  <th>Usuário</th>
                  <th>Tabela</th>
                  <th>Registro afetado</th>
                  <th>Data</th>
                  <th>Hora</th>
                  <th>Tipo operação</th>
                </tr>
              </thead>

             <tbody>
  {registros.map((item, index) => (
    <tr key={`${item.usuario || "sem-usuario"}-${index}`}>
      <td>{item.usuario || "-"}</td>
      <td>{item.tabela_desc || item.tabela || "-"}</td>
      <td>{item.id_registro ?? "-"}</td>
      <td>
        {item.data_lancamento
          ? String(item.data_lancamento).slice(0, 10).split("-").reverse().join("/")
          : "-"}
      </td>
      <td>
        {item.data_lancamento
          ? String(item.data_lancamento).slice(11, 19) || "-"
          : "-"}
      </td>
      <td>{item.acao || "-"}</td>
    </tr>
  ))}
</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default PerformanceDetalhePage;