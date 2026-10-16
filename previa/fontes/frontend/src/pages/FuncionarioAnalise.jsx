import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useEmpresa } from "../context/EmpresaContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import Topbar from "../components/Topbar";
import api from "../services/api";
import "../styles/dashboard.css";
import "../styles/topbar.css";
import "../styles/funcionario-analise.css";

const REGISTROS_POR_PAGINA = 500;

function FuncionarioAnalise({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const { pes_id } = useParams();
  const funcionarioId = pes_id;
  const [searchParams] = useSearchParams();
  const origem = searchParams.get('origem') || undefined;
  const { empresaAtual, loadingEmpresas } = useEmpresa();
  const empresaId = resolveEmpresaErpId(empresaAtual) || undefined;

  function obterDataHoje() {
    const hoje = new Date();
    const ano = hoje.getFullYear();
    const mes = String(hoje.getMonth() + 1).padStart(2, "0");
    const dia = String(hoje.getDate()).padStart(2, "0");
    return `${ano}-${mes}-${dia}`;
  }

  function formatarDataHora(valor) {
    if (!valor) {
      return "-";
    }

    const texto = String(valor).trim();

    const match = texto.match(
      /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?)?$/
    );

    if (!match) {
      return texto;
    }

    const [, ano, mes, dia, hora, minuto, segundo] = match;

    if (hora && minuto && segundo) {
      return `${dia}/${mes}/${ano} ${hora}:${minuto}:${segundo}`;
    }

    return `${dia}/${mes}/${ano}`;
  }

  function obterLabelFiltroCard(valor) {
    const mapa = {
      TOTAL: "Todos os registros",
      Inclusão: "Somente inclusões",
      Alteração: "Somente alterações",
      Exclusão: "Somente exclusões",
      Cancelamento: "Somente cancelamentos",
    };

    return mapa[valor] || "Todos os registros";
  }

  function dataEhValida(valor) {
    return /^\d{4}-\d{2}-\d{2}$/.test(String(valor || "").trim());
  }

  const hoje = obterDataHoje();

  const [funcionario, setFuncionario] = useState(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [ordemSelecionada, setOrdemSelecionada] = useState("Horário");

  const [dataInicial, setDataInicial] = useState(hoje);
  const [dataFinal, setDataFinal] = useState(hoje);
  const [limitSelecionado, setLimitSelecionado] = useState("100");

  const [filtroTabelaSelecionada, setFiltroTabelaSelecionada] = useState("");
  const [filtroCardSelecionado, setFiltroCardSelecionado] = useState("TOTAL");
  const [paginaAtual, setPaginaAtual] = useState(1);

  const [filtrosAplicados, setFiltrosAplicados] = useState({
    dataInicial: hoje,
    dataFinal: hoje,
    limit: "100",
  });

  const [auditoria, setAuditoria] = useState([]);
  const [loadingAuditoria, setLoadingAuditoria] = useState(false);
  const [erroAuditoria, setErroAuditoria] = useState("");
  const [auditoriaInfo, setAuditoriaInfo] = useState('');

  const limitesAuditoria = [
    { label: "100 registros", value: "100" },
    { label: "200 registros", value: "200" },
    { label: "500 registros", value: "500" },
    { label: "1000 registros", value: "1000" },
    { label: "2000 registros", value: "2000" },
    { label: "3000 registros", value: "3000" },
    { label: "5000 registros", value: "5000" },
  ];

  useEffect(() => {
    const controller = new AbortController();
    async function carregarDadosIniciais() {
      if (loadingEmpresas) return;
      if (!funcionarioId) {
        setErro("ID do funcionário não foi encontrado na rota.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setErro("");

        const funcionarioResponse = await api.get(`/funcionarios/${funcionarioId}`, { signal: controller.signal, params: { empresa_id: empresaId, origem } });
        if (!controller.signal.aborted) setFuncionario(funcionarioResponse.data);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Erro ao carregar análise do funcionário:", error);
        setErro(error?.response?.data?.detail || "Não foi possível carregar os dados do funcionário.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    carregarDadosIniciais();
    return () => controller.abort();
  }, [funcionarioId, empresaId, origem, loadingEmpresas]);

  useEffect(() => {
    const controller = new AbortController();
    async function carregarAuditoria() {
      if (loadingEmpresas) return;
      if (!funcionarioId) {
        return;
      }

      try {
        setLoadingAuditoria(true);
        setErroAuditoria("");
        setAuditoriaInfo('');

        const queryParams = {
          empresa_id: empresaId,
          origem,
          limit: Number(filtrosAplicados.limit || 100),
        };

        if (filtrosAplicados.dataInicial) {
          queryParams.data_inicial = filtrosAplicados.dataInicial;
        }

        if (filtrosAplicados.dataFinal) {
          queryParams.data_final = filtrosAplicados.dataFinal;
        }

        const response = await api.get(`/funcionarios/${funcionarioId}/auditoria`, {
          params: queryParams, signal: controller.signal,
        });

        if (controller.signal.aborted) return;
        const registros = Array.isArray(response.data?.registros)
          ? response.data.registros
          : [];

        setAuditoria(registros);
        setAuditoriaInfo(response.data?.available === false ? response.data.message : '');
        setFiltroCardSelecionado("TOTAL");
        setFiltroTabelaSelecionada("");
        setPaginaAtual(1);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Erro ao carregar auditoria:", error);
        const mensagem =
          error?.response?.data?.detail ||
          "Não foi possível carregar a auditoria do funcionário.";
        setErroAuditoria(String(mensagem));
        setAuditoria([]);
        setPaginaAtual(1);
      } finally {
        if (!controller.signal.aborted) setLoadingAuditoria(false);
      }
    }

    carregarAuditoria();
    return () => controller.abort();
  }, [funcionarioId, filtrosAplicados, empresaId, origem, loadingEmpresas]);

  useEffect(() => {
    setPaginaAtual(1);
  }, [filtroCardSelecionado, filtroTabelaSelecionada, ordemSelecionada]);

  function pesquisarAuditoria() {
    setErroAuditoria("");

    const dataInicialLimpa = String(dataInicial || "").trim();
    const dataFinalLimpa = String(dataFinal || "").trim();

    if (!dataEhValida(dataInicialLimpa)) {
      setErroAuditoria("A data inicial está inválida. Use o formato AAAA-MM-DD.");
      return;
    }

    if (!dataEhValida(dataFinalLimpa)) {
      setErroAuditoria("A data final está inválida. Use o formato AAAA-MM-DD.");
      return;
    }

    if (dataFinalLimpa < dataInicialLimpa) {
      setErroAuditoria("A data final não pode ser menor que a data inicial.");
      return;
    }

    setFiltrosAplicados({
      dataInicial: dataInicialLimpa,
      dataFinal: dataFinalLimpa,
      limit: limitSelecionado,
    });
    setPaginaAtual(1);
  }

  function limparFiltros() {
    const dataHoje = obterDataHoje();

    setDataInicial(dataHoje);
    setDataFinal(dataHoje);
    setLimitSelecionado("100");
    setErroAuditoria("");

    setFiltrosAplicados({
      dataInicial: dataHoje,
      dataFinal: dataHoje,
      limit: "100",
    });

    setFiltroCardSelecionado("TOTAL");
    setFiltroTabelaSelecionada("");
    setPaginaAtual(1);
  }

  const tabelasDisponiveis = useMemo(() => {
    const lista = auditoria
      .map((item) => String(item.tabela_desc || "").trim())
      .filter((valor) => valor !== "");

    const unicas = [...new Set(lista)];
    return unicas.sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [auditoria]);

  const resumoAuditoria = useMemo(() => {
    const total = auditoria.length;
    const inclusoes = auditoria.filter((item) => item.acao === "Inclusão").length;
    const alteracoes = auditoria.filter((item) => item.acao === "Alteração").length;
    const exclusoes = auditoria.filter((item) => item.acao === "Exclusão").length;
    const cancelamentos = auditoria.filter(
      (item) => item.acao === "Cancelamento"
    ).length;

    return {
      total,
      inclusoes,
      alteracoes,
      exclusoes,
      cancelamentos,
    };
  }, [auditoria]);

  const auditoriaFiltradaPorTabela = useMemo(() => {
    if (!filtroTabelaSelecionada) {
      return auditoria;
    }

    return auditoria.filter(
      (item) => String(item.tabela_desc || "").trim() === filtroTabelaSelecionada
    );
  }, [auditoria, filtroTabelaSelecionada]);

  const auditoriaFiltradaPorCard = useMemo(() => {
    if (filtroCardSelecionado === "TOTAL") {
      return auditoriaFiltradaPorTabela;
    }

    return auditoriaFiltradaPorTabela.filter(
      (item) => item.acao === filtroCardSelecionado
    );
  }, [auditoriaFiltradaPorTabela, filtroCardSelecionado]);

  const auditoriaOrdenada = useMemo(() => {
    const resultado = [...auditoriaFiltradaPorCard];

    if (ordemSelecionada === "Horário") {
      resultado.sort((a, b) => {
        const dataA = a.data_lancamento ? String(a.data_lancamento) : "";
        const dataB = b.data_lancamento ? String(b.data_lancamento) : "";
        return dataB.localeCompare(dataA);
      });
    }

    if (ordemSelecionada === "Ação") {
      resultado.sort((a, b) =>
        String(a.acao || "").localeCompare(String(b.acao || ""), "pt-BR")
      );
    }

    if (ordemSelecionada === "Status") {
      resultado.sort((a, b) =>
        String(a.tabela_desc || "").localeCompare(
          String(b.tabela_desc || ""),
          "pt-BR"
        )
      );
    }

    return resultado;
  }, [auditoriaFiltradaPorCard, ordemSelecionada]);

  const totalPaginas = useMemo(() => {
    return Math.max(1, Math.ceil(auditoriaOrdenada.length / REGISTROS_POR_PAGINA));
  }, [auditoriaOrdenada.length]);

  const paginaAtualAjustada = Math.min(paginaAtual, totalPaginas);

  const indiceInicial = (paginaAtualAjustada - 1) * REGISTROS_POR_PAGINA;
  const indiceFinal = indiceInicial + REGISTROS_POR_PAGINA;

  const auditoriaPaginaAtual = useMemo(() => {
    return auditoriaOrdenada.slice(indiceInicial, indiceFinal);
  }, [auditoriaOrdenada, indiceInicial, indiceFinal]);

  const inicioExibicao = auditoriaOrdenada.length === 0 ? 0 : indiceInicial + 1;
  const fimExibicao = Math.min(indiceFinal, auditoriaOrdenada.length);

  const paginasVisiveis = useMemo(() => {
    const maximo = 5;
    let inicio = Math.max(1, paginaAtualAjustada - 2);
    let fim = Math.min(totalPaginas, inicio + maximo - 1);

    if (fim - inicio + 1 < maximo) {
      inicio = Math.max(1, fim - maximo + 1);
    }

    const paginas = [];
    for (let pagina = inicio; pagina <= fim; pagina += 1) {
      paginas.push(pagina);
    }

    return paginas;
  }, [paginaAtualAjustada, totalPaginas]);

  function classeCardAtivo(valor) {
    return filtroCardSelecionado === valor ? "auditoria-card-active" : "";
  }

  function classeTabelaAtiva(valor) {
    return filtroTabelaSelecionada === valor ? "active" : "";
  }

  function irParaPagina(pagina) {
    if (pagina < 1 || pagina > totalPaginas) {
      return;
    }
    setPaginaAtual(pagina);
  }

  if (loading) {
    return (
      <div className="dashboard-page">
        <Topbar
          titulo="Análise de Produtividade"
          subtitulo={funcionario?.nome ? `${funcionario.nome} · ERP ${funcionarioId}` : "Dados do funcionário"}
          caminho="Dashboard / Auditoria"
          onToggleSidebar={onToggleSidebar}
          isMobileOrTablet={isMobileOrTablet}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        <div className="analise-box">Carregando funcionário...</div>
      </div>
    );
  }

  if (erro && !funcionario) {
    return (
      <div className="dashboard-page">
        <Topbar
          titulo="Análise de Produtividade"
          subtitulo={funcionario?.nome ? `${funcionario.nome} · ERP ${funcionarioId}` : "Dados do funcionário"}
          caminho="Dashboard / Auditoria"
          onToggleSidebar={onToggleSidebar}
          isMobileOrTablet={isMobileOrTablet}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        <div className="analise-box analise-erro">{erro}</div>
      </div>
    );
  }

  if (!funcionario) {
    return (
      <div className="dashboard-page">
        <Topbar
          titulo="Análise de Produtividade"
          subtitulo={funcionario?.nome ? `${funcionario.nome} · ERP ${funcionarioId}` : "Dados do funcionário"}
          caminho="Dashboard / Auditoria"
          onToggleSidebar={onToggleSidebar}
          isMobileOrTablet={isMobileOrTablet}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        <div className="analise-box">Funcionário não encontrado.</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <Topbar
        titulo="Análise de Produtividade"
          subtitulo={funcionario?.nome ? `${funcionario.nome} · ERP ${funcionarioId}` : "Dados do funcionário"}
        caminho="Dashboard / Auditoria"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div className="analise-toolbar">
        <div className="analise-tipos">
          <button
            className={`analise-tipo-btn ${!filtroTabelaSelecionada ? "active" : ""}`}
            onClick={() => setFiltroTabelaSelecionada("")}
          >
            Todas as tabelas
          </button>

          {tabelasDisponiveis.map((tabela) => (
            <button
              key={tabela}
              className={`analise-tipo-btn ${classeTabelaAtiva(tabela)}`}
              onClick={() => setFiltroTabelaSelecionada(tabela)}
            >
              {tabela}
            </button>
          ))}
        </div>

        <div className="analise-ordem-box">
          <span>Ordem:</span>
          <select
            className="analise-select analise-select-small"
            value={ordemSelecionada}
            onChange={(e) => setOrdemSelecionada(e.target.value)}
          >
            <option value="Horário">Horário</option>
            <option value="Ação">Ação</option>
            <option value="Status">Status</option>
          </select>
        </div>
      </div>

      <div className="analise-box analise-box-filtros">
        <div className="analise-filtros-topo">
          <h3 className="analise-titulo-box sem-margem">Filtros</h3>

          <div className="analise-acoes-filtros">
            <button className="analise-limpar-btn" onClick={limparFiltros}>
              Limpar filtros
            </button>

            <button className="analise-salvar-btn" onClick={pesquisarAuditoria}>
              Pesquisar
            </button>
          </div>
        </div>

        <div className="analise-filtros-data-inline">
          <div className="analise-filtro-data-item">
            <label className="analise-label">Data inicial</label>
            <input
              type="date"
              className="analise-select"
              value={dataInicial}
              onChange={(e) => setDataInicial(String(e.target.value || "").slice(0, 10))}
            />
          </div>

          <div className="analise-filtro-data-item">
            <label className="analise-label">Data final</label>
            <input
              type="date"
              className="analise-select"
              value={dataFinal}
              onChange={(e) => setDataFinal(String(e.target.value || "").slice(0, 10))}
            />
          </div>

          <div className="analise-filtro-data-item">
            <label className="analise-label">Quantidade de registros</label>
            <select
              className="analise-select"
              value={limitSelecionado}
              onChange={(e) => setLimitSelecionado(e.target.value)}
            >
              {limitesAuditoria.map((limite) => (
                <option key={limite.value} value={limite.value}>
                  {limite.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="auditoria-cards-grid">
        <button
          type="button"
          className={`auditoria-card auditoria-card-total ${classeCardAtivo("TOTAL")}`}
          onClick={() => setFiltroCardSelecionado("TOTAL")}
        >
          <span className="auditoria-card-label">Total de ações</span>
          <strong className="auditoria-card-value">{resumoAuditoria.total}</strong>
        </button>

        <button
          type="button"
          className={`auditoria-card auditoria-card-inclusao ${classeCardAtivo("Inclusão")}`}
          onClick={() => setFiltroCardSelecionado("Inclusão")}
        >
          <span className="auditoria-card-label">Inclusões</span>
          <strong className="auditoria-card-value">{resumoAuditoria.inclusoes}</strong>
        </button>

        <button
          type="button"
          className={`auditoria-card auditoria-card-alteracao ${classeCardAtivo("Alteração")}`}
          onClick={() => setFiltroCardSelecionado("Alteração")}
        >
          <span className="auditoria-card-label">Alterações</span>
          <strong className="auditoria-card-value">{resumoAuditoria.alteracoes}</strong>
        </button>

        <button
          type="button"
          className={`auditoria-card auditoria-card-exclusao ${classeCardAtivo("Exclusão")}`}
          onClick={() => setFiltroCardSelecionado("Exclusão")}
        >
          <span className="auditoria-card-label">Exclusões</span>
          <strong className="auditoria-card-value">{resumoAuditoria.exclusoes}</strong>
        </button>

        <button
          type="button"
          className={`auditoria-card auditoria-card-cancelamento ${classeCardAtivo("Cancelamento")}`}
          onClick={() => setFiltroCardSelecionado("Cancelamento")}
        >
          <span className="auditoria-card-label">Cancelamentos</span>
          <strong className="auditoria-card-value">{resumoAuditoria.cancelamentos}</strong>
        </button>
      </div>

      <div className="analise-box">
        <div className="analise-tabela-topo">
          <div className="analise-tabela-titulos">
            <h3 className="analise-titulo-box sem-margem">Análise Funcionário</h3>
            <span className="analise-filtro-ativo">
              {obterLabelFiltroCard(filtroCardSelecionado)}
              {filtroTabelaSelecionada ? ` • Tabela: ${filtroTabelaSelecionada}` : ""}
            </span>
          </div>

          <div className="analise-badges-topo">
            <span className="analise-total-badge">
              {auditoriaOrdenada.length} registro(s)
            </span>
            <span className="analise-pagina-badge">
              Página {paginaAtualAjustada} de {totalPaginas}
            </span>
          </div>
        </div>

        {auditoriaInfo && <p className="analise-feedback" role="status">{auditoriaInfo}</p>}
        {loadingAuditoria && (
          <div className="analise-feedback">Carregando auditoria...</div>
        )}

        {!loadingAuditoria && erroAuditoria && (
          <div className="analise-feedback analise-erro">{erroAuditoria}</div>
        )}

        {!loadingAuditoria && !erroAuditoria && auditoriaOrdenada.length === 0 && (
          <div className="analise-feedback">
            Nenhum registro de auditoria encontrado para este funcionário.
          </div>
        )}

        {!loadingAuditoria && !erroAuditoria && auditoriaOrdenada.length > 0 && (
          <>
            <div className="analise-table-wrapper">
              <table className="analise-table">
                <thead>
                  <tr>
                    <th className="col-data">Data e Hora</th>
                    <th className="col-acao">Ação</th>
                    <th className="col-tabela">Tabela</th>
                    <th className="col-campo">Campo</th>
                    <th className="col-registro">Registro</th>
                  </tr>
                </thead>
                <tbody>
                  {auditoriaPaginaAtual.map((item, index) => (
                    <tr key={`${item.aud_sequencia || index}-${index}`}>
                      <td className="td-data">
                        {formatarDataHora(item.data_lancamento)}
                      </td>
                      <td>
                        <span
                          className={`acao-pill ${
                            item.acao === "Inclusão"
                              ? "acao-inclusao"
                              : item.acao === "Alteração"
                              ? "acao-alteracao"
                              : item.acao === "Exclusão"
                              ? "acao-exclusao"
                              : item.acao === "Cancelamento"
                              ? "acao-cancelamento"
                              : ""
                          }`}
                        >
                          {item.acao || "-"}
                        </span>
                      </td>
                      <td>{item.tabela_desc || "-"}</td>
                      <td>{item.campo_desc || "-"}</td>
                      <td>{item.descricao_registro || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="analise-footer">
              <div className="analise-footer-info">
                Mostrando {inicioExibicao} até {fimExibicao} de{" "}
                {auditoriaOrdenada.length} registro(s)
              </div>

              <div className="analise-paginacao">
                <button
                  className="pagina-btn"
                  type="button"
                  onClick={() => irParaPagina(paginaAtualAjustada - 1)}
                  disabled={paginaAtualAjustada === 1}
                >
                  ‹
                </button>

                {paginasVisiveis.map((pagina) => (
                  <button
                    key={pagina}
                    className={`pagina-btn ${
                      pagina === paginaAtualAjustada ? "active" : ""
                    }`}
                    type="button"
                    onClick={() => irParaPagina(pagina)}
                  >
                    {pagina}
                  </button>
                ))}

                <button
                  className="pagina-btn"
                  type="button"
                  onClick={() => irParaPagina(paginaAtualAjustada + 1)}
                  disabled={paginaAtualAjustada === totalPaginas}
                >
                  ›
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default FuncionarioAnalise;
