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

function formatarNumero(valor) {
  return Number(valor || 0).toLocaleString("pt-BR");
}

function calcularPercentual(valor, total) {
  if (!total) return 0;
  return Number(((Number(valor || 0) / Number(total || 0)) * 100).toFixed(1));
}

function classeKpiPorChave(chave) {
  if (chave === "total") return "kpi-total";
  if (chave === "inclusoes") return "kpi-inclusao";
  if (chave === "alteracoes") return "kpi-alteracao";
  if (chave === "exclusoes") return "kpi-exclusao";
  return "kpi-cancelamento";
}

function corDistribuicao(chave) {
  if (chave === "inclusoes") return "#16a34a";
  if (chave === "alteracoes") return "#f59e0b";
  if (chave === "exclusoes") return "#dc2626";
  return "#7c3aed";
}

function Performance({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const navigate = useNavigate();

  const hoje = obterDataHoje();
  const primeiroDiaMesAtual = obterPrimeiroDiaMesAtual();

  const [filtroAcao, setFiltroAcao] = useState("");
  const [filtroDepartamento, setFiltroDepartamento] = useState("");
  const [dataInicial, setDataInicial] = useState(primeiroDiaMesAtual);
  const [dataFinal, setDataFinal] = useState(hoje);
  const [buscaRapida, setBuscaRapida] = useState("");
  const [filtroResumoAtivo, setFiltroResumoAtivo] = useState("total");

  const [departamentos, setDepartamentos] = useState([]);
  const [dadosPerformance, setDadosPerformance] = useState({
    resumo: {
      total: 0,
      inclusoes: 0,
      alteracoes: 0,
      exclusoes: 0,
      cancelamentos: 0,
    },
    produtividade: {
      dias_com_atividade: 0,
      media_por_dia: 0,
      hora_mais_ativa: "-",
      tabela_mais_movimentada: "-",
    },
    acoes_por_dia: [],
    acoes_por_horario: [],
    ranking_funcionarios: [],
    tabela_resumo: [],
    registros: [],
  });

  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  const maiorDia = useMemo(() => {
    if (!dadosPerformance.acoes_por_dia.length) return 1;
    return Math.max(
      ...dadosPerformance.acoes_por_dia.map((item) => Number(item.total || 0))
    );
  }, [dadosPerformance.acoes_por_dia]);

  const maiorHora = useMemo(() => {
    if (!dadosPerformance.acoes_por_horario.length) return 1;
    return Math.max(
      ...dadosPerformance.acoes_por_horario.map((item) => Number(item.total || 0))
    );
  }, [dadosPerformance.acoes_por_horario]);

  const maiorRanking = useMemo(() => {
    if (!dadosPerformance.ranking_funcionarios.length) return 1;
    return Math.max(
      ...dadosPerformance.ranking_funcionarios.map((item) =>
        Number(item.total || 0)
      )
    );
  }, [dadosPerformance.ranking_funcionarios]);

  const distribuicaoAcoes = useMemo(() => {
    const total = Number(dadosPerformance.resumo.total || 0);

    return [
      {
        key: "inclusoes",
        label: "Inclusões",
        valor: Number(dadosPerformance.resumo.inclusoes || 0),
        percentual: calcularPercentual(dadosPerformance.resumo.inclusoes, total),
      },
      {
        key: "alteracoes",
        label: "Alterações",
        valor: Number(dadosPerformance.resumo.alteracoes || 0),
        percentual: calcularPercentual(dadosPerformance.resumo.alteracoes, total),
      },
      {
        key: "exclusoes",
        label: "Exclusões",
        valor: Number(dadosPerformance.resumo.exclusoes || 0),
        percentual: calcularPercentual(dadosPerformance.resumo.exclusoes, total),
      },
      {
        key: "cancelamentos",
        label: "Cancelamentos",
        valor: Number(dadosPerformance.resumo.cancelamentos || 0),
        percentual: calcularPercentual(
          dadosPerformance.resumo.cancelamentos,
          total
        ),
      },
    ];
  }, [dadosPerformance.resumo]);

  const leituraExecutiva = useMemo(() => {
    const resumo = dadosPerformance.resumo;
    const produtividade = dadosPerformance.produtividade;

    const mapa = [
      { nome: "Inclusões", valor: Number(resumo.inclusoes || 0) },
      { nome: "Alterações", valor: Number(resumo.alteracoes || 0) },
      { nome: "Exclusões", valor: Number(resumo.exclusoes || 0) },
      { nome: "Cancelamentos", valor: Number(resumo.cancelamentos || 0) },
    ].sort((a, b) => b.valor - a.valor);

    const tipoPredominante =
      mapa[0] && mapa[0].valor > 0 ? mapa[0].nome : "Sem predominância";

    const topFuncionario =
      dadosPerformance.ranking_funcionarios.length > 0
        ? dadosPerformance.ranking_funcionarios[0]
        : null;

    const total = Number(resumo.total || 0);
    const media = Number(produtividade.media_por_dia || 0);

    return {
      tipoPredominante,
      topFuncionario,
      mensagemVolume:
        total > 0
          ? `Foram identificadas ${formatarNumero(total)} ações no período analisado.`
          : "Nenhuma ação foi encontrada no período analisado.",
      mensagemProdutividade:
        Number(produtividade.dias_com_atividade || 0) > 0
          ? `A operação apresentou atividade em ${formatarNumero(
              produtividade.dias_com_atividade
            )} dias, com média de ${formatarNumero(media)} ações por dia.`
          : "Não houve dias com atividade no período filtrado.",
    };
  }, [dadosPerformance]);

  const indicadoresTopo = useMemo(() => {
    const total = Number(dadosPerformance.resumo.total || 0);

    return [
      {
        key: "total",
        titulo: "Total de ações",
        valor: Number(dadosPerformance.resumo.total || 0),
        subtitulo: "Indicador principal do painel",
      },
      {
        key: "inclusoes",
        titulo: "Inclusões",
        valor: Number(dadosPerformance.resumo.inclusoes || 0),
        subtitulo: `${calcularPercentual(
          dadosPerformance.resumo.inclusoes,
          total
        )}% do total`,
      },
      {
        key: "alteracoes",
        titulo: "Alterações",
        valor: Number(dadosPerformance.resumo.alteracoes || 0),
        subtitulo: `${calcularPercentual(
          dadosPerformance.resumo.alteracoes,
          total
        )}% do total`,
      },
      {
        key: "exclusoes",
        titulo: "Exclusões",
        valor: Number(dadosPerformance.resumo.exclusoes || 0),
        subtitulo: `${calcularPercentual(
          dadosPerformance.resumo.exclusoes,
          total
        )}% do total`,
      },
      {
        key: "cancelamentos",
        titulo: "Cancelamentos",
        valor: Number(dadosPerformance.resumo.cancelamentos || 0),
        subtitulo: `${calcularPercentual(
          dadosPerformance.resumo.cancelamentos,
          total
        )}% do total`,
      },
    ];
  }, [dadosPerformance.resumo]);

  const rankingFiltrado = useMemo(() => {
    const texto = String(buscaRapida || "").trim().toLowerCase();
    const base = Array.isArray(dadosPerformance.ranking_funcionarios)
      ? dadosPerformance.ranking_funcionarios
      : [];

    const filtradoPorResumo =
      filtroResumoAtivo === "total"
        ? base
        : base.filter((item) => {
            if (filtroResumoAtivo === "inclusoes") {
              return Number(item.inclusoes || 0) > 0;
            }
            if (filtroResumoAtivo === "alteracoes") {
              return Number(item.alteracoes || 0) > 0;
            }
            if (filtroResumoAtivo === "exclusoes") {
              return Number(item.exclusoes || 0) > 0;
            }
            if (filtroResumoAtivo === "cancelamentos") {
              return Number(item.cancelamentos || 0) > 0;
            }
            return true;
          });

    if (!texto) return filtradoPorResumo;

    return filtradoPorResumo.filter((item) => {
      const nome = String(item.nome || "").toLowerCase();
      const departamento = String(item.departamento || "").toLowerCase();
      return nome.includes(texto) || departamento.includes(texto);
    });
  }, [dadosPerformance.ranking_funcionarios, buscaRapida, filtroResumoAtivo]);

  const tabelaResumoFiltrada = useMemo(() => {
    const texto = String(buscaRapida || "").trim().toLowerCase();
    const base = Array.isArray(dadosPerformance.tabela_resumo)
      ? dadosPerformance.tabela_resumo
      : [];

    const filtradoPorResumo =
      filtroResumoAtivo === "total"
        ? base
        : base.filter((item) => {
            if (filtroResumoAtivo === "inclusoes") {
              return Number(item.inclusoes || 0) > 0;
            }
            if (filtroResumoAtivo === "alteracoes") {
              return Number(item.alteracoes || 0) > 0;
            }
            if (filtroResumoAtivo === "exclusoes") {
              return Number(item.exclusoes || 0) > 0;
            }
            if (filtroResumoAtivo === "cancelamentos") {
              return Number(item.cancelamentos || 0) > 0;
            }
            return true;
          });

    if (!texto) return filtradoPorResumo;

    return filtradoPorResumo.filter((item) => {
      const funcionario = String(item.funcionario || "").toLowerCase();
      const departamento = String(item.departamento || "").toLowerCase();
      return funcionario.includes(texto) || departamento.includes(texto);
    });
  }, [dadosPerformance.tabela_resumo, buscaRapida, filtroResumoAtivo]);

  const rankingTop10 = useMemo(() => {
    return rankingFiltrado.slice(0, 10);
  }, [rankingFiltrado]);

  async function carregarDepartamentos() {
    try {
      const response = await api.get("/departamentos/");
      setDepartamentos(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error("Erro ao carregar departamentos:", error);
    }
  }

  async function carregarPerformance() {
    try {
      setCarregando(true);
      setErro("");

      const params = {};

      if (filtroAcao) params.acao = filtroAcao;
      if (filtroDepartamento) params.departamento_id = filtroDepartamento;
      if (dataInicial) params.data_inicial = dataInicial;
      if (dataFinal) params.data_final = dataFinal;

      const response = await api.get("/performance/visao-geral", { params });

      setDadosPerformance({
        resumo: response.data?.resumo || {
          total: 0,
          inclusoes: 0,
          alteracoes: 0,
          exclusoes: 0,
          cancelamentos: 0,
        },
        produtividade: response.data?.produtividade || {
          dias_com_atividade: 0,
          media_por_dia: 0,
          hora_mais_ativa: "-",
          tabela_mais_movimentada: "-",
        },
        acoes_por_dia: Array.isArray(response.data?.acoes_por_dia)
          ? response.data.acoes_por_dia
          : [],
        acoes_por_horario: Array.isArray(response.data?.acoes_por_horario)
          ? response.data.acoes_por_horario
          : [],
        ranking_funcionarios: Array.isArray(response.data?.ranking_funcionarios)
          ? response.data.ranking_funcionarios
          : [],
        tabela_resumo: Array.isArray(response.data?.tabela_resumo)
          ? response.data.tabela_resumo
          : [],
        registros: [],
      });
    } catch (error) {
      console.error("Erro ao carregar performance:", error);
      setErro("Não foi possível carregar os dados de performance.");
      setDadosPerformance({
        resumo: {
          total: 0,
          inclusoes: 0,
          alteracoes: 0,
          exclusoes: 0,
          cancelamentos: 0,
        },
        produtividade: {
          dias_com_atividade: 0,
          media_por_dia: 0,
          hora_mais_ativa: "-",
          tabela_mais_movimentada: "-",
        },
        acoes_por_dia: [],
        acoes_por_horario: [],
        ranking_funcionarios: [],
        tabela_resumo: [],
        registros: [],
      });
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarDepartamentos();
  }, []);

  useEffect(() => {
    carregarPerformance();
  }, []);

  function limparFiltros() {
    setFiltroAcao("");
    setFiltroDepartamento("");
    setDataInicial(primeiroDiaMesAtual);
    setDataFinal(hoje);
    setBuscaRapida("");
    setFiltroResumoAtivo("total");
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

    carregarPerformance();
  }

 function lidarCliqueCard(itemKey) {
  setFiltroResumoAtivo(itemKey);

  if (itemKey === "inclusoes") {
    navigate("/performance/inclusoes");
    return;
  }

  if (itemKey === "alteracoes") {
    navigate("/performance/alteracoes");
    return;
  }

  if (itemKey === "exclusoes") {
    navigate("/performance/exclusoes");
    return;
  }

  if (itemKey === "cancelamentos") {
    navigate("/performance/cancelamentos");
  }
}
  return (
    <div className="dashboard-page performance-page">
      <Topbar titulo="Performance" caminho="Performance" onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet} theme={theme} toggleTheme={toggleTheme} />

      <section className="performance-hero">
        <div className="performance-hero-content">
          <span className="performance-eyebrow">Painel gerencial</span>
          <h1 className="performance-title">Performance operacional</h1>
          <p className="performance-subtitle">
            Visão consolidada do mês atual com volume, tendência, distribuição,
            ranking e resumo executivo da operação.
          </p>
        </div>

        <div className="performance-hero-mini-grid">
          <div className="mini-stat-card">
            <span>Total monitorado</span>
            <strong>{formatarNumero(dadosPerformance.resumo.total)}</strong>
          </div>

          <div className="mini-stat-card">
            <span>Dias com atividade</span>
            <strong>
              {formatarNumero(dadosPerformance.produtividade.dias_com_atividade)}
            </strong>
          </div>

          <div className="mini-stat-card">
            <span>Hora mais ativa</span>
            <strong>{dadosPerformance.produtividade.hora_mais_ativa}</strong>
          </div>

          <div className="mini-stat-card">
            <span>Tabela líder</span>
            <strong>
              {dadosPerformance.produtividade.tabela_mais_movimentada || "-"}
            </strong>
          </div>
        </div>
      </section>

      <section className="performance-panel">
        <div className="performance-panel-top">
          <div>
            <h3>Filtros de análise</h3>
            <p>Por padrão, o painel abre sempre com o mês atual.</p>
          </div>

          <button
            className="btn-refresh"
            onClick={aplicarFiltros}
            type="button"
            disabled={carregando}
          >
            {carregando ? "Atualizando..." : "Atualizar painel"}
          </button>
        </div>

        <div className="performance-filters-grid">
          <div className="performance-filter-group">
            <label>Tipo de ação</label>
            <select
              value={filtroAcao}
              onChange={(e) => setFiltroAcao(e.target.value)}
            >
              <option value="">Todas</option>
              <option value="I">Inclusão</option>
              <option value="A">Alteração</option>
              <option value="E">Exclusão</option>
              <option value="C">Cancelamento</option>
            </select>
          </div>

          <div className="performance-filter-group">
            <label>Departamento</label>
            <select
              value={filtroDepartamento}
              onChange={(e) => setFiltroDepartamento(e.target.value)}
            >
              <option value="">Todos</option>
              {departamentos.map((departamento) => (
                <option key={departamento.id} value={departamento.id}>
                  {departamento.nome}
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
            <label>Busca rápida</label>
            <input
              type="text"
              placeholder="Nome ou departamento"
              value={buscaRapida}
              onChange={(e) => setBuscaRapida(e.target.value)}
            />
          </div>

          <div className="performance-filter-actions">
            <button className="btn-clear" onClick={limparFiltros} type="button">
              Limpar filtros
            </button>
          </div>
        </div>

        {carregando && (
          <div className="performance-status info-message">
            Carregando dados de performance...
          </div>
        )}

        {erro && !carregando && (
          <div className="performance-status error-message">{erro}</div>
        )}
      </section>

      <section className="performance-kpi-grid">
        {indicadoresTopo.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => lidarCliqueCard(item.key)}
            className={`performance-kpi-card ${classeKpiPorChave(item.key)} ${
              filtroResumoAtivo === item.key ? "performance-kpi-card-active" : ""
            }`}
          >
            <h3>{item.titulo}</h3>
            <p>{formatarNumero(item.valor)}</p>
            <span>{item.subtitulo}</span>
          </button>
        ))}
      </section>

      <section className="performance-kpi-secondary-grid">
        <div className="performance-soft-card">
          <h3>Dias com atividade</h3>
          <p>{formatarNumero(dadosPerformance.produtividade.dias_com_atividade)}</p>
          <span>Quantidade de dias com movimentação</span>
        </div>

        <div className="performance-soft-card">
          <h3>Média por dia</h3>
          <p>{formatarNumero(dadosPerformance.produtividade.media_por_dia)}</p>
          <span>Média de ações por dia com atividade</span>
        </div>

        <div className="performance-soft-card">
          <h3>Hora mais ativa</h3>
          <p>{dadosPerformance.produtividade.hora_mais_ativa}</p>
          <span>Faixa com maior concentração de ações</span>
        </div>

        <div className="performance-soft-card">
          <h3>Tabela mais movimentada</h3>
          <p className="performance-soft-card-text">
            {dadosPerformance.produtividade.tabela_mais_movimentada || "-"}
          </p>
          <span>Maior incidência operacional no período</span>
        </div>
      </section>

      <section className="performance-main-grid">
        <div className="performance-box performance-box-large">
          <div className="performance-section-title">
            <div>
              <h3>Evolução das ações por dia</h3>
              <p>Tendência diária da movimentação operacional</p>
            </div>
          </div>

          {dadosPerformance.acoes_por_dia.length === 0 ? (
            <div className="performance-empty-state">
              Nenhum dado encontrado com os filtros aplicados.
            </div>
          ) : (
            <div className="performance-chart-scroll">
              <div className="performance-chart-bars performance-chart-bars-tall">
                {dadosPerformance.acoes_por_dia.map((item) => {
                  const valor = Number(item.total || 0);
                  const altura =
                    maiorDia > 0 ? Math.max(18, (valor / maiorDia) * 220) : 18;

                  return (
                    <div
                      className="performance-bar-column"
                      key={item.data_iso || item.dia}
                      title={`${item.dia} - ${formatarNumero(valor)} ações`}
                    >
                      <div className="performance-bar-value">
                        {formatarNumero(valor)}
                      </div>
                      <div
                        className="performance-bar performance-bar-primary"
                        style={{ height: `${altura}px` }}
                      />
                      <div className="performance-bar-label">{item.dia}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="performance-box">
          <div className="performance-section-title">
            <div>
              <h3>Distribuição por tipo</h3>
              <p>Participação percentual no volume total</p>
            </div>
          </div>

          <div className="performance-distribution-list">
            {distribuicaoAcoes.map((item) => (
              <div className="performance-distribution-item" key={item.key}>
                <div className="performance-distribution-header">
                  <span>{item.label}</span>
                  <strong>{item.percentual}%</strong>
                </div>

                <div className="performance-distribution-track">
                  <div
                    className="performance-distribution-fill"
                    style={{
                      width: `${item.percentual}%`,
                      background: corDistribuicao(item.key),
                    }}
                  />
                </div>

                <small>{formatarNumero(item.valor)} registros</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="performance-two-columns">
        <div className="performance-box">
          <div className="performance-section-title">
            <div>
              <h3>Concentração por horário</h3>
              <p>Distribuição das ações ao longo do expediente</p>
            </div>
          </div>

          {dadosPerformance.acoes_por_horario.length === 0 ? (
            <div className="performance-empty-state">
              Nenhum dado encontrado com os filtros aplicados.
            </div>
          ) : (
            <div className="performance-chart-scroll">
              <div className="performance-chart-bars">
                {dadosPerformance.acoes_por_horario.map((item) => {
                  const valor = Number(item.total || 0);
                  const altura =
                    maiorHora > 0 ? Math.max(18, (valor / maiorHora) * 180) : 18;

                  return (
                    <div
                      className="performance-bar-column"
                      key={item.hora}
                      title={`${item.hora} - ${formatarNumero(valor)} ações`}
                    >
                      <div className="performance-bar-value">
                        {formatarNumero(valor)}
                      </div>
                      <div
                        className="performance-bar performance-bar-secondary"
                        style={{ height: `${altura}px` }}
                      />
                      <div className="performance-bar-label">{item.hora}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="performance-box">
          <div className="performance-section-title">
            <div>
              <h3>Leitura executiva</h3>
              <p>Resumo analítico para leitura gerencial rápida</p>
            </div>
          </div>

          <div className="performance-executive-grid">
            <div className="performance-executive-card">
              <span>Volume operacional</span>
              <strong>{leituraExecutiva.mensagemVolume}</strong>
            </div>

            <div className="performance-executive-card">
              <span>Produtividade</span>
              <strong>{leituraExecutiva.mensagemProdutividade}</strong>
            </div>

            <div className="performance-executive-card">
              <span>Tipo predominante</span>
              <strong>{leituraExecutiva.tipoPredominante}</strong>
            </div>

            <div className="performance-executive-card">
              <span>Destaque do período</span>
              <strong>
                {leituraExecutiva.topFuncionario
                  ? `${leituraExecutiva.topFuncionario.nome} lidera com ${formatarNumero(
                      leituraExecutiva.topFuncionario.total
                    )} ações.`
                  : "Sem colaborador de destaque no recorte atual."}
              </strong>
            </div>
          </div>
        </div>
      </section>

      <section className="performance-two-columns">
        <div className="performance-box">
          <div className="performance-section-title">
            <div>
              <h3>Top 10 colaboradores</h3>
              <p>Comparativo visual do volume por colaborador</p>
            </div>
          </div>

          {rankingTop10.length === 0 ? (
            <div className="performance-empty-state">
              Nenhum funcionário encontrado com os filtros aplicados.
            </div>
          ) : (
            <div className="performance-ranking-list">
              {rankingTop10.map((item, index) => (
                <div className="performance-ranking-item" key={`${item.nome}-${index}`}>
                  <div className="performance-ranking-top">
                    <div>
                      <strong>{item.nome}</strong>
                      <span>{item.departamento || "-"}</span>
                    </div>
                    <div className="performance-ranking-value">
                      {formatarNumero(item.total)} ações
                    </div>
                  </div>

                  <div className="performance-ranking-track">
                    <div
                      className="performance-ranking-fill"
                      style={{
                        width: `${Math.max(
                          2,
                          (Number(item.total || 0) / maiorRanking) * 100
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="performance-box">
          <div className="performance-section-title">
            <div>
              <h3>Resumo consolidado por colaborador</h3>
              <p>Visão executiva dos indicadores individuais</p>
            </div>
          </div>

          {tabelaResumoFiltrada.length === 0 ? (
            <div className="performance-empty-state">
              Nenhum dado encontrado para montar a tabela.
            </div>
          ) : (
            <div className="performance-table-wrapper">
              <table className="performance-table">
                <thead>
                  <tr>
                    <th>Funcionário</th>
                    <th>Total</th>
                    <th>Inclusões</th>
                    <th>Alterações</th>
                    <th>Exclusões</th>
                    <th>Cancelamentos</th>
                  </tr>
                </thead>

                <tbody>
                  {tabelaResumoFiltrada.map((item) => (
                    <tr key={`${item.funcionario}-${item.departamento || "-"}`}>
                      <td>{item.funcionario}</td>
                      <td>{formatarNumero(item.acoes)}</td>
                      <td>{formatarNumero(item.inclusoes)}</td>
                      <td>{formatarNumero(item.alteracoes)}</td>
                      <td>{formatarNumero(item.exclusoes)}</td>
                      <td>{formatarNumero(item.cancelamentos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default Performance;
