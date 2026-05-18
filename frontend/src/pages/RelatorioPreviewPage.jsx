import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Topbar from "../components/Topbar";
import {
  inspecionarRelatorio,
  obterOpcoesRelatorio,
  executarPreviewRelatorio,
} from "../services/relatoriosService";
import FastReportRenderer from "../components/relatorios/FastReportRenderer.jsx";
import "../styles/relatorios.css";
import "../styles/topbar.css";
import "../styles/relatorio-preview.css";
import "../styles/relatorio-table.css";

const OPCOES_ANALISE = [
  { VALUE: "GRUPO", LABEL: "Grupo" },
  { VALUE: "MARCA", LABEL: "Marca" },
  { VALUE: "PRODUTO", LABEL: "Produto" },
  { VALUE: "VENDEDOR", LABEL: "Vendedor" },
  { VALUE: "CLIENTE", LABEL: "Cliente" },
];

const OPCOES_TIPO_DATA = [
  { VALUE: "EMISSAO", LABEL: "Emissão" },
  { VALUE: "FATURAMENTO", LABEL: "Faturamento" },
  { VALUE: "MOVIMENTO", LABEL: "Movimento" },
  { VALUE: "ENTRADA", LABEL: "Entrada" },
  { VALUE: "SAIDA", LABEL: "Saída" },
];

function inferirMetadataParametro(nomeOriginal, datatype = "") {
  const chave = String(nomeOriginal || "").toUpperCase().trim();
  const tipo = String(datatype || "").toLowerCase().trim();

  let inferredType = "str";
  let semanticKey = chave.toLowerCase();
  let defaultValue = "";

  if (tipo.includes("date")) {
    inferredType = "date";

    const hoje = new Date();
    const yyyy = hoje.getFullYear();
    const mm = String(hoje.getMonth() + 1).padStart(2, "0");
    const dd = String(hoje.getDate()).padStart(2, "0");

    const primeiroDia = `${yyyy}-${mm}-01`;
    const hojeIso = `${yyyy}-${mm}-${dd}`;

    if (chave.includes("INICIAL") || chave.includes("INICIO")) {
      semanticKey = "data_inicial";
      defaultValue = primeiroDia;
    } else if (chave.includes("FINAL") || chave.includes("FIM")) {
      semanticKey = "data_final";
      defaultValue = hojeIso;
    } else {
      semanticKey = "data";
      defaultValue = hojeIso;
    }
  } else if (
    tipo.includes("integer") ||
    tipo.includes("smallint") ||
    tipo.includes("bigint") ||
    tipo.includes("int")
  ) {
    inferredType = "int";
    defaultValue = 0;
  } else if (
    tipo.includes("numeric") ||
    tipo.includes("float") ||
    tipo.includes("double") ||
    tipo.includes("decimal")
  ) {
    inferredType = "number";
    defaultValue = 0;
  }

  if (chave.includes("EMPRESA")) {
    semanticKey = "empresa";
    if (defaultValue === "") defaultValue = 1;
  } else if (chave.includes("VENDEDOR")) {
    semanticKey = "vendedor";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("CLIENTE")) {
    semanticKey = "cliente";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("NATUREZA")) {
    semanticKey = "natureza";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("GRUPO")) {
    semanticKey = "grupo";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("MARCA")) {
    semanticKey = "marca";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("CIDADE")) {
    semanticKey = "cidade";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("REGIAO") || chave.includes("REGIÃO")) {
    semanticKey = "regiao";
    if (defaultValue === "") defaultValue = 0;
  } else if (chave.includes("FORNECEDOR")) {
    semanticKey = "fornecedor";
    if (defaultValue === "") defaultValue = 0;
  }

  if (chave === "PANALISE") {
    semanticKey = "analise";
    inferredType = "str";
    defaultValue = "GRUPO";
  }

  if (chave === "TIPODATA") {
    semanticKey = "tipo_data";
    inferredType = "str";
    defaultValue = "EMISSAO";
  }

  return {
    original_name: nomeOriginal,
    inferred_type: inferredType,
    semantic_key: semanticKey,
    default_value: defaultValue,
  };
}

function normalizarParametrosDetectados(lista = []) {
  if (!Array.isArray(lista)) return [];

  return lista.map((param) => {
    const nomeOriginal = param?.original_name || param?.name || "";
    const datatype = param?.datatype || param?.inferred_type || "";
    const inferido = inferirMetadataParametro(nomeOriginal, datatype);

    return {
      ...inferido,
      ...param,
      original_name: nomeOriginal,
      inferred_type: param?.inferred_type || inferido.inferred_type,
      semantic_key: inferido.semantic_key,
      default_value:
        param?.default_value !== undefined ? param.default_value : inferido.default_value,
    };
  });
}

function extrairParametrosDoDetalhe(detalhe) {
  const queries = Array.isArray(detalhe?.queries) ? detalhe.queries : [];
  const unicos = new Map();

  for (const query of queries) {
    const parametros = Array.isArray(query?.parametros) ? query.parametros : [];

    for (const param of parametros) {
      const nomeOriginal = param?.name;
      const datatype = String(param?.datatype || "").toLowerCase();

      if (!nomeOriginal) continue;

      const chave = String(nomeOriginal).toUpperCase();

      if (!unicos.has(chave)) {
        unicos.set(chave, inferirMetadataParametro(nomeOriginal, datatype));
      }
    }
  }

  return Array.from(unicos.values());
}

function formatarDataParaExibicao(valor) {
  if (!valor) return "Não informado";

  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) {
    const [ano, mes, dia] = valor.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  return String(valor);
}

function normalizarListaOpcoes(lista = []) {
  if (!Array.isArray(lista)) return [];

  return lista.map((item, index) => {
    if (item && typeof item === "object") {
      const value =
        item.VALUE ??
        item.value ??
        item.EMP_ID ??
        item.emp_id ??
        item.id ??
        Object.values(item)[0] ??
        index;

      const label =
        item.LABEL ??
        item.label ??
        item.EMP_FANTASIA ??
        item.emp_fantasia ??
        item.EMP_RAZAO_SOCIAL ??
        item.emp_razao_social ??
        Object.values(item)[1] ??
        Object.values(item)[0] ??
        `Opção ${index + 1}`;

      return {
        ...item,
        VALUE: value,
        LABEL: String(label),
      };
    }

    return {
      VALUE: item,
      LABEL: String(item),
    };
  });
}

function buscarLabelOpcao(lista, valor, textoPadraoZero = null) {
  const listaNormalizada = normalizarListaOpcoes(lista);
  const encontrado = listaNormalizada.find(
    (item) => String(item.VALUE) === String(valor)
  );

  if (encontrado) {
    return encontrado.LABEL;
  }

  if (Number(valor) === 0 && textoPadraoZero) {
    return textoPadraoZero;
  }

  return String(valor);
}

function formatarFiltroParaExibicao(chave, valor, opcoes) {
  if (valor === null || valor === undefined || valor === "") {
    return "Não informado";
  }

  const chaveNormalizada = String(chave).toUpperCase();

  if (chaveNormalizada.includes("DATA")) {
    return formatarDataParaExibicao(valor);
  }

  if (chaveNormalizada === "PANALISE") {
    return buscarLabelOpcao(opcoes?.analises, valor);
  }

  if (chaveNormalizada === "TIPODATA") {
    return buscarLabelOpcao(opcoes?.tiposData, valor);
  }

  if (chaveNormalizada.includes("EMPRESA")) {
    return buscarLabelOpcao(opcoes?.empresas, valor);
  }

  if (chaveNormalizada.includes("VENDEDOR")) {
    return buscarLabelOpcao(opcoes?.vendedores, valor, "Todos");
  }

  if (chaveNormalizada.includes("CLIENTE")) {
    return buscarLabelOpcao(opcoes?.clientes, valor, "Todos");
  }

  if (chaveNormalizada.includes("NATUREZA")) {
    return buscarLabelOpcao(opcoes?.naturezas, valor, "Todas");
  }

  if (chaveNormalizada.includes("GRUPO")) {
    return buscarLabelOpcao(opcoes?.grupos, valor, "Todos");
  }

  if (chaveNormalizada.includes("MARCA")) {
    return buscarLabelOpcao(opcoes?.marcas, valor, "Todas");
  }

  if (chaveNormalizada.includes("CIDADE")) {
    return buscarLabelOpcao(opcoes?.cidades, valor, "Todas");
  }

  if (chaveNormalizada.includes("REGIAO") || chaveNormalizada.includes("REGIÃO")) {
    return buscarLabelOpcao(opcoes?.regioes, valor, "Todas");
  }

  if (chaveNormalizada.includes("FORNECEDOR")) {
    return buscarLabelOpcao(opcoes?.fornecedores, valor, "Todos");
  }

  return String(valor);
}

export default function RelatorioPreviewPage({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const [searchParams] = useSearchParams();

  const cdarquivo = searchParams.get("cdarquivo");
  const nome = searchParams.get("nome") || "Preview do relatório";

  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [erro, setErro] = useState("");

  const [detalhe, setDetalhe] = useState(null);
  const [parametros, setParametros] = useState([]);
  const [opcoes, setOpcoes] = useState({
    empresas: [],
    vendedores: [],
    naturezas: [],
    clientes: [],
    grupos: [],
    marcas: [],
    cidades: [],
    regioes: [],
    fornecedores: [],
    analises: OPCOES_ANALISE,
    tiposData: OPCOES_TIPO_DATA,
  });
  const [form, setForm] = useState({});
  const [previewData, setPreviewData] = useState(null);

  useEffect(() => {
    async function carregarMetadados() {
      try {
        setLoadingMeta(true);
        setErro("");

        if (!cdarquivo) {
          setErro("CDARQUIVO não informado.");
          return;
        }

        const detalheResp = await inspecionarRelatorio(cdarquivo);
        const opcoesResp = await obterOpcoesRelatorio(cdarquivo);

        const paramsBrutos =
          detalheResp?.parameters_detected ||
          detalheResp?.parametros_detectados ||
          extrairParametrosDoDetalhe(detalheResp);

        const params = normalizarParametrosDetectados(paramsBrutos);

        const opcoesNormalizadas = {
          empresas: normalizarListaOpcoes(opcoesResp?.empresas),
          vendedores: normalizarListaOpcoes(opcoesResp?.vendedores),
          naturezas: normalizarListaOpcoes(opcoesResp?.naturezas),
          clientes: normalizarListaOpcoes(opcoesResp?.clientes),
          grupos: normalizarListaOpcoes(opcoesResp?.grupos),
          marcas: normalizarListaOpcoes(opcoesResp?.marcas),
          cidades: normalizarListaOpcoes(opcoesResp?.cidades),
          regioes: normalizarListaOpcoes(opcoesResp?.regioes),
          fornecedores: normalizarListaOpcoes(opcoesResp?.fornecedores),
          analises: OPCOES_ANALISE,
          tiposData: OPCOES_TIPO_DATA,
          ...opcoesResp,
        };

        const valoresIniciais = {};

        for (const param of params) {
          const chave = param.original_name;
          let valorInicial = param.default_value ?? "";

          if (param.semantic_key === "empresa") {
            const primeiraEmpresa = opcoesNormalizadas.empresas?.[0];
            if (
              valorInicial === "" ||
              valorInicial === null ||
              valorInicial === undefined
            ) {
              valorInicial = primeiraEmpresa?.VALUE ?? "";
            }
          }

          if (param.semantic_key === "analise") {
            if (
              valorInicial === "" ||
              valorInicial === null ||
              valorInicial === undefined
            ) {
              valorInicial = "GRUPO";
            }
          }

          if (param.semantic_key === "tipo_data") {
            if (
              valorInicial === "" ||
              valorInicial === null ||
              valorInicial === undefined
            ) {
              valorInicial = "EMISSAO";
            }
          }

          valoresIniciais[chave] = valorInicial;
        }

        setDetalhe(detalheResp);
        setParametros(params);
        setOpcoes(opcoesNormalizadas);
        setForm(valoresIniciais);
      } catch (error) {
        console.error(error);
        setErro(
          error?.response?.data?.detail ||
            error?.message ||
            "Erro ao carregar metadados do relatório."
        );
      } finally {
        setLoadingMeta(false);
      }
    }

    carregarMetadados();
  }, [cdarquivo]);

  const tituloPagina = useMemo(() => {
    return detalhe?.nome || nome;
  }, [detalhe, nome]);

  const filtrosAplicados = useMemo(() => {
    return parametros.map((param) => ({
      nome: param.original_name,
      semanticKey: param.semantic_key,
      valor: formatarFiltroParaExibicao(
        param.original_name,
        form[param.original_name],
        opcoes
      ),
    }));
  }, [parametros, form, opcoes]);

  function atualizarCampo(nomeCampo, valor) {
    setForm((prev) => ({
      ...prev,
      [nomeCampo]: valor,
    }));
  }

  function renderSelect(lista = [], valor, onChange, placeholder = "Selecione") {
    const listaNormalizada = normalizarListaOpcoes(lista);

    return (
      <select value={valor} onChange={onChange} className="preview-select">
        {listaNormalizada.length === 0 ? (
          <option value="">{placeholder}</option>
        ) : null}

        {listaNormalizada.map((item, index) => (
          <option key={`${item.VALUE}-${index}`} value={item.VALUE}>
            {item.LABEL}
          </option>
        ))}
      </select>
    );
  }

  function renderCampo(param) {
    const valor = form[param.original_name] ?? "";

    if (param.inferred_type === "date") {
      return (
        <input
          type="date"
          className="preview-input"
          value={valor}
          onChange={(e) => atualizarCampo(param.original_name, e.target.value)}
        />
      );
    }

    if (param.semantic_key === "empresa") {
      return renderSelect(opcoes.empresas, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "vendedor") {
      return renderSelect(opcoes.vendedores, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "cliente") {
      return renderSelect(opcoes.clientes, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "natureza") {
      return renderSelect(opcoes.naturezas, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "grupo") {
      return renderSelect(opcoes.grupos, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "marca") {
      return renderSelect(opcoes.marcas, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "cidade") {
      return renderSelect(opcoes.cidades, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "regiao") {
      return renderSelect(opcoes.regioes, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "fornecedor") {
      return renderSelect(opcoes.fornecedores, valor, (e) =>
        atualizarCampo(param.original_name, Number(e.target.value))
      );
    }

    if (param.semantic_key === "analise") {
      return renderSelect(opcoes.analises, valor, (e) =>
        atualizarCampo(param.original_name, e.target.value)
      );
    }

    if (param.semantic_key === "tipo_data") {
      return renderSelect(opcoes.tiposData, valor, (e) =>
        atualizarCampo(param.original_name, e.target.value)
      );
    }

    if (param.inferred_type === "int" || param.inferred_type === "number") {
      return (
        <input
          type="number"
          className="preview-input"
          value={valor}
          onChange={(e) =>
            atualizarCampo(
              param.original_name,
              e.target.value === "" ? "" : Number(e.target.value)
            )
          }
        />
      );
    }

    return (
      <input
        type="text"
        className="preview-input"
        value={valor}
        onChange={(e) => atualizarCampo(param.original_name, e.target.value)}
      />
    );
  }

  async function gerarPreview() {
    try {
      setLoadingPreview(true);
      setErro("");

      const payload = {};

      for (const param of parametros) {
        payload[param.original_name] = form[param.original_name];
      }

      const resposta = await executarPreviewRelatorio(cdarquivo, payload);
      setPreviewData(resposta);
    } catch (error) {
      console.error(error);
      setPreviewData(null);
      setErro(
        error?.response?.data?.detail ||
          error?.message ||
          "Erro ao gerar preview do relatório."
      );
    } finally {
      setLoadingPreview(false);
    }
  }

  function limparPreview() {
    setPreviewData(null);
    setErro("");
  }

  return (
    <div className="page-content">
      <Topbar
        titulo="Relatórios"
        subtitulo="Visualização e prévia de relatórios FastReport"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div className="preview-page">
        <div className="preview-hero-card">
          <div className="preview-hero-content">
            <div>
              <h1 className="preview-page-title">{tituloPagina}</h1>
              <p className="preview-page-subtitle">
                Configure os parâmetros e gere o preview do relatório na mesma
                tela.
              </p>
            </div>

            <div className="preview-page-actions no-print">
              {previewData ? (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={limparPreview}
                >
                  Limpar
                </button>
              ) : null}
            </div>
          </div>

          {loadingMeta ? (
            <div className="preview-loading-card">Carregando parâmetros...</div>
          ) : (
            <>
              <div className="preview-filtros-card">
                <div className="preview-grid">
                  {parametros.map((param) => (
                    <div className="preview-field" key={param.original_name}>
                      <label className="preview-label">{param.original_name}</label>
                      {renderCampo(param)}
                      <small className="preview-field-helper">
                        {param.semantic_key}
                      </small>
                    </div>
                  ))}
                </div>

                <div className="preview-actions-row no-print">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={gerarPreview}
                    disabled={loadingPreview}
                  >
                    {loadingPreview ? "Gerando preview..." : "Gerar preview"}
                  </button>
                </div>
              </div>
            </>
          )}

          {erro ? (
            <div
              style={{
                marginTop: 16,
                padding: "12px 14px",
                borderRadius: 12,
                background: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#991b1b",
              }}
            >
              {erro}
            </div>
          ) : null}
        </div>

        <div className="preview-page-card">
          {previewData ? (
            <FastReportRenderer
              layout={detalhe?.layout_visual}
              linhas={previewData?.linhas || []}
              filtrosAplicados={filtrosAplicados}
              tituloRelatorio={tituloPagina}
              totalRegistros={previewData?.total_registros || 0}
              detalhe={detalhe}
            />
          ) : (
            <div className="preview-filtros-card">
              <div className="preview-hint">
                Gere o preview para visualizar o relatório.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}