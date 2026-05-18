import { useEffect, useMemo, useState } from "react";
import {
  listarRelatorios,
  inspecionarRelatorio,
  obterOpcoesRelatorio,
  executarPreviewRelatorio,
} from "../services/relatoriosService";
import { useEmpresa } from "../context/EmpresaContext";
import FastReportRenderer from "./relatorios/FastReportRenderer.jsx";
import "../styles/relatorios-lista.css";
import "../styles/relatorio-preview.css";
import "../styles/relatorio-table.css";

const OPCOES_PANALISE = [
  { VALUE: "GRUPO", LABEL: "Grupo" },
  { VALUE: "MARCA", LABEL: "Marca" },
  { VALUE: "CIDADE", LABEL: "Cidade" },
  { VALUE: "CLIENTE", LABEL: "Cliente" },
  { VALUE: "VENDEDOR", LABEL: "Vendedor" },
  { VALUE: "REGIÃO", LABEL: "Região" },
  { VALUE: "FORNECEDOR", LABEL: "Fornecedor" },
];

const OPCOES_TIPODATA = [
  { VALUE: "EMISSAO", LABEL: "Emissão" },
  { VALUE: "FATURAMENTO", LABEL: "Faturamento" },
];

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
        let inferredType = "str";
        let semanticKey = chave.toLowerCase();
        let defaultValue = "";

        if (datatype.includes("date")) {
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
          datatype.includes("integer") ||
          datatype.includes("smallint") ||
          datatype.includes("bigint") ||
          datatype.includes("int")
        ) {
          inferredType = "int";
          defaultValue = 0;

          if (chave.includes("EMPRESA")) {
            semanticKey = "empresa";
            defaultValue = 1;
          } else if (chave.includes("VENDEDOR")) {
            semanticKey = "vendedor";
            defaultValue = 0;
          } else if (chave.includes("CLIENTE")) {
            semanticKey = "cliente";
            defaultValue = 0;
          } else if (chave.includes("NATUREZA")) {
            semanticKey = "natureza";
            defaultValue = 0;
          } else if (chave.includes("GRUPO")) {
            semanticKey = "grupo";
            defaultValue = 0;
          } else if (chave.includes("MARCA")) {
            semanticKey = "marca";
            defaultValue = 0;
          } else if (chave.includes("CIDADE")) {
            semanticKey = "cidade";
            defaultValue = 0;
          } else if (chave.includes("REGIAO") || chave.includes("REGIÃO")) {
            semanticKey = "regiao";
            defaultValue = 0;
          } else if (chave.includes("FORNECEDOR")) {
            semanticKey = "fornecedor";
            defaultValue = 0;
          }
        } else if (
          datatype.includes("numeric") ||
          datatype.includes("float") ||
          datatype.includes("double") ||
          datatype.includes("decimal")
        ) {
          inferredType = "number";
          defaultValue = 0;
        }

        if (chave === "PANALISE" || chave === "PTIPO") {
          semanticKey = "analise";
          inferredType = "str";
          defaultValue = "GRUPO";
        }

        if (chave === "TIPODATA") {
          semanticKey = "tipo_data";
          inferredType = "str";
          defaultValue = "EMISSAO";
        }

        unicos.set(chave, {
          original_name: nomeOriginal,
          inferred_type: inferredType,
          semantic_key: semanticKey,
          default_value: defaultValue,
        });
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

function isTextoUtil(valor) {
  if (valor === null || valor === undefined) return false;
  const texto = String(valor).trim();
  return Boolean(texto);
}

function isLabelRuim(valor) {
  if (!isTextoUtil(valor)) return true;

  const texto = String(valor).trim();

  if (texto.length <= 1) return true;
  if (/^[CJFSN]$/i.test(texto)) return true;

  return false;
}

function escolherCampoValue(item = {}) {
  const chaves = Object.keys(item);

  const candidatasFortes = [
    "VALUE",
    "value",
    "ID",
    "id",
    "EMP_ID",
    "emp_id",
    "CLI_ID",
    "cli_id",
    "PES_ID",
    "pes_id",
    "VEN_ID",
    "ven_id",
    "FUN_ID",
    "fun_id",
    "NOP_ID",
    "nop_id",
    "PGRU_ID",
    "pgru_id",
    "PMAR_ID",
    "pmar_id",
    "CID_ID",
    "cid_id",
    "REG_ID",
    "reg_id",
    "CODIGO",
    "codigo",
    "COD",
    "cod",
  ];

  for (const chave of candidatasFortes) {
    if (chave in item) return item[chave];
  }

  const chaveComId = chaves.find((chave) => /(^|_)(id|codigo|cod)$/i.test(chave));
  if (chaveComId) return item[chaveComId];

  return Object.values(item)[0];
}

function escolherCampoLabel(item = {}, semanticKey = "") {
  const chaves = Object.keys(item);

  const candidatasPorTipo = {
    empresa: [
      "EMP_FANTASIA",
      "emp_fantasia",
      "EMP_RAZAO_SOCIAL",
      "emp_razao_social",
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "LABEL",
      "label",
      "nome_exibicao",
    ],
    cliente: [
      "pes_fantasia_apelido",
      "PES_FANTASIA_APELIDO",
      "pes_rsocial_nome",
      "PES_RSOCIAL_NOME",
      "CLI_NOME",
      "cli_nome",
      "CLI_RAZAO_SOCIAL",
      "cli_razao_social",
      "CLI_FANTASIA",
      "cli_fantasia",
      "PES_NOME",
      "pes_nome",
      "PES_RAZAO_SOCIAL",
      "pes_razao_social",
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "LABEL",
      "label",
    ],
    vendedor: [
      "VEN_NOME",
      "ven_nome",
      "FUN_NOME",
      "fun_nome",
      "PES_NOME",
      "pes_nome",
      "pes_rsocial_nome",
      "PES_RSOCIAL_NOME",
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "LABEL",
      "label",
    ],
    natureza: [
      "NOP_DESCRICAO",
      "nop_descricao",
      "DESCRICAO",
      "descricao",
      "NOME",
      "nome",
      "LABEL",
      "label",
    ],
    grupo: [
      "PGRU_DESCRICAO",
      "pgru_descricao",
      "DESCRICAO",
      "descricao",
      "NOME",
      "nome",
      "LABEL",
      "label",
    ],
    marca: [
      "PMAR_DESCRICAO",
      "pmar_descricao",
      "DESCRICAO",
      "descricao",
      "NOME",
      "nome",
      "LABEL",
      "label",
    ],
    cidade: [
      "CID_NOME",
      "cid_nome",
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "LABEL",
      "label",
    ],
    regiao: [
      "REG_DESCRICAO",
      "reg_descricao",
      "DESCRICAO",
      "descricao",
      "NOME",
      "nome",
      "LABEL",
      "label",
    ],
    fornecedor: [
      "pes_fantasia_apelido",
      "PES_FANTASIA_APELIDO",
      "pes_rsocial_nome",
      "PES_RSOCIAL_NOME",
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "LABEL",
      "label",
    ],
    default: [
      "NOME",
      "nome",
      "DESCRICAO",
      "descricao",
      "RAZAO_SOCIAL",
      "razao_social",
      "FANTASIA",
      "fantasia",
      "LABEL",
      "label",
      "nome_exibicao",
    ],
  };

  const candidatas = candidatasPorTipo[semanticKey] || candidatasPorTipo.default;

  for (const chave of candidatas) {
    if (!(chave in item)) continue;

    const valor = item[chave];

    if (chave === "LABEL" || chave === "label") {
      if (!isLabelRuim(valor)) {
        return valor;
      }
      continue;
    }

    if (isTextoUtil(valor)) {
      return valor;
    }
  }

  const chaveNome = chaves.find((chave) =>
    /(nome|descricao|razao|fantasia|apelido|social)/i.test(chave)
  );

  if (chaveNome && isTextoUtil(item[chaveNome])) {
    return item[chaveNome];
  }

  const valoresTextuais = Object.values(item).filter((valor) => {
    const texto = String(valor ?? "").trim();
    return texto.length > 1 && /[A-Za-zÀ-ÿ]/.test(texto);
  });

  if (valoresTextuais.length > 0) {
    return valoresTextuais[0];
  }

  const labelOriginal = item.LABEL ?? item.label;
  if (isTextoUtil(labelOriginal)) {
    return labelOriginal;
  }

  const primeiro = Object.values(item)[0];
  return isTextoUtil(primeiro) ? primeiro : "Opção";
}

function normalizarListaOpcoes(lista = [], semanticKey = "") {
  if (!Array.isArray(lista)) return [];

  return lista.map((item) => {
    if (item && typeof item === "object") {
      const value = escolherCampoValue(item);
      const label = escolherCampoLabel(item, semanticKey);

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

function adicionarOpcaoTodos(lista = [], semanticKey = "") {
  const listaNormalizada = normalizarListaOpcoes(lista, semanticKey);

  if (
    ![
      "vendedor",
      "cliente",
      "natureza",
      "grupo",
      "marca",
      "cidade",
      "regiao",
      "fornecedor",
    ].includes(semanticKey)
  ) {
    return listaNormalizada;
  }

  const labelPadrao = semanticKey === "natureza" ? "Todas" : "Todos";

  const jaExisteZero = listaNormalizada.some(
    (item) => String(item.VALUE) === "0"
  );

  if (jaExisteZero) {
    return listaNormalizada;
  }

  return [
    {
      VALUE: 0,
      LABEL: labelPadrao,
    },
    ...listaNormalizada,
  ];
}

function formatarFiltroParaExibicao(chave, valor, opcoes) {
  if (valor === null || valor === undefined || valor === "") {
    return "Não informado";
  }

  const chaveNormalizada = String(chave).toUpperCase();

  if (chaveNormalizada.includes("DATA")) {
    return formatarDataParaExibicao(valor);
  }

  if (chaveNormalizada === "PANALISE" || chaveNormalizada === "PTIPO") {
    const encontrado = OPCOES_PANALISE.find(
      (item) => String(item.VALUE) === String(valor)
    );
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada === "TIPODATA") {
    const encontrado = OPCOES_TIPODATA.find(
      (item) => String(item.VALUE) === String(valor)
    );
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("EMPRESA")) {
    const lista = normalizarListaOpcoes(opcoes?.empresas, "empresa");
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("VENDEDOR")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "vendedor"),
      "vendedor"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("CLIENTE")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "cliente"),
      "cliente"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("NATUREZA")) {
    if (Number(valor) === 0) return "Todas";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "natureza"),
      "natureza"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("GRUPO")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "grupo"),
      "grupo"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("MARCA")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "marca"),
      "marca"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("CIDADE")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "cidade"),
      "cidade"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("REGIAO") || chaveNormalizada.includes("REGIÃO")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "regiao"),
      "regiao"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  if (chaveNormalizada.includes("FORNECEDOR")) {
    if (Number(valor) === 0) return "Todos";
    const lista = adicionarOpcaoTodos(
      obterListaOpcoesPorSemanticKey(opcoes, "fornecedor"),
      "fornecedor"
    );
    const encontrado = lista.find((item) => String(item.VALUE) === String(valor));
    return encontrado?.LABEL ?? String(valor);
  }

  return String(valor);
}

function formatarDataHora(valor) {
  if (!valor) return "Não informado";
  return String(valor);
}

function Modal({ aberto, titulo, subtitulo, onFechar, children, largura = "920px" }) {
  if (!aberto) return null;

  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div
        className="modal-card"
        style={{ maxWidth: largura }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header no-print">
          <div>
            <h2>{titulo}</h2>
            {subtitulo ? <p>{subtitulo}</p> : null}
          </div>

          <button type="button" className="modal-close-btn" onClick={onFechar}>
            ×
          </button>
        </div>

        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function obterListaOpcoesPorSemanticKey(opcoes = {}, semanticKey = "") {
  const mapa = {
    empresa: ["empresas"],
    vendedor: ["vendedores", "query_qryvendedor", "qryvendedor"],
    cliente: ["clientes", "query_qrycliente", "qrycliente"],
    natureza: ["naturezas", "query_qrynatureza", "qrynatureza"],
    grupo: ["grupos", "query_qrygrupo", "qrygrupo"],
    marca: ["marcas", "query_qrymarca", "qrymarca"],
    cidade: ["cidades", "query_qrycidade", "qrycidade"],
    regiao: ["regioes", "regiões", "query_qryregiao", "qryregiao"],
    fornecedor: ["fornecedores", "query_qryfornecedor", "qryfornecedor"],
  };

  const chaves = mapa[semanticKey] || [];

  for (const chave of chaves) {
    const valor = opcoes?.[chave];
    if (Array.isArray(valor) && valor.length >= 0) {
      return valor;
    }
  }

  return [];
}

export default function ListaRelatorios({ categoria, titulo }) {
  const { empresaAtual } = useEmpresa();

  const [loadingLista, setLoadingLista] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [busca, setBusca] = useState("");
  const [relatorios, setRelatorios] = useState([]);

  const [modalParametrosAberto, setModalParametrosAberto] = useState(false);
  const [modalPreviewAberto, setModalPreviewAberto] = useState(false);

  const [loadingMeta, setLoadingMeta] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [erroModal, setErroModal] = useState("");

  const [relatorioSelecionado, setRelatorioSelecionado] = useState(null);
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
  });
  const [form, setForm] = useState({});
  const [previewData, setPreviewData] = useState(null);

  useEffect(() => {
    async function carregarRelatorios() {
      try {
        setLoadingLista(true);
        setErroLista("");

        const data = await listarRelatorios(categoria);
        setRelatorios(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error(error);
        setErroLista(
          error?.response?.data?.detail ||
            error?.message ||
            "Erro ao carregar relatórios."
        );
      } finally {
        setLoadingLista(false);
      }
    }

    carregarRelatorios();
  }, [categoria]);

  const relatoriosFiltrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();

    if (!termo) return relatorios;

    return relatorios.filter((relatorio) => {
      const campos = [
        relatorio?.nome,
        relatorio?.descricao,
        relatorio?.pasta,
        relatorio?.pasta_pai,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return campos.includes(termo);
    });
  }, [relatorios, busca]);

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

  function fecharModalParametros() {
    setModalParametrosAberto(false);
    setErroModal("");
  }

  function fecharModalPreview() {
    setModalPreviewAberto(false);
  }

  function limparEstadoModal() {
    setDetalhe(null);
    setParametros([]);
    setOpcoes({
      empresas: [],
      vendedores: [],
      naturezas: [],
      clientes: [],
      grupos: [],
      marcas: [],
      cidades: [],
      regioes: [],
      fornecedores: [],
    });
    setForm({});
    setPreviewData(null);
    setErroModal("");
  }

  function montarPayloadBaseEmpresa() {
    const empresaId = Number(empresaAtual?.id || 0);

    if (!empresaId) return {};

    return {
      empresa: empresaId,
      EMPRESA: empresaId,
      empresa_id: empresaId,
      EMPRESA_ID: empresaId,
      pempresa: empresaId,
      PEMPRESA: empresaId,
      EMPRESA_PADRAO: empresaId,
      empresa_padrao: empresaId,
    };
  }

  async function abrirModalParametros(relatorio) {
    try {
      setLoadingMeta(true);
      setErroModal("");
      setRelatorioSelecionado(relatorio);
      setPreviewData(null);
      setModalPreviewAberto(false);

      const payloadBaseEmpresa = montarPayloadBaseEmpresa();

      const [detalheResp, opcoesResp] = await Promise.all([
        inspecionarRelatorio(relatorio.cdarquivo),
        obterOpcoesRelatorio(relatorio.cdarquivo, payloadBaseEmpresa),
      ]);

      const params =
        detalheResp?.parameters_detected ||
        detalheResp?.parametros_detectados ||
        extrairParametrosDoDetalhe(detalheResp);

      const opcoesNormalizadas = {
        empresas: normalizarListaOpcoes(opcoesResp?.empresas, "empresa"),
        vendedores: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "vendedor"),
          "vendedor"
        ),
        naturezas: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "natureza"),
          "natureza"
        ),
        clientes: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "cliente"),
          "cliente"
        ),
        grupos: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "grupo"),
          "grupo"
        ),
        marcas: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "marca"),
          "marca"
        ),
        cidades: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "cidade"),
          "cidade"
        ),
        regioes: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "regiao"),
          "regiao"
        ),
        fornecedores: adicionarOpcaoTodos(
          obterListaOpcoesPorSemanticKey(opcoesResp, "fornecedor"),
          "fornecedor"
        ),
        ...opcoesResp,
      };

      const valoresIniciais = {};

      for (const param of params) {
        const chave = param.original_name;
        let valorInicial = param.default_value ?? "";

        if (param.semantic_key === "empresa") {
          const empresaStorage = empresaAtual?.id ?? null;
          const primeiraEmpresa = opcoesNormalizadas.empresas?.[0];

          valorInicial =
            empresaStorage ??
            primeiraEmpresa?.VALUE ??
            valorInicial ??
            "";
        }

        if (param.semantic_key === "analise" && !valorInicial) {
          valorInicial = "GRUPO";
        }

        if (param.semantic_key === "tipo_data" && !valorInicial) {
          valorInicial = "EMISSAO";
        }

        if (
          [
            "vendedor",
            "cliente",
            "natureza",
            "grupo",
            "marca",
            "cidade",
            "regiao",
            "fornecedor",
          ].includes(param.semantic_key) &&
          (valorInicial === "" || valorInicial === null || valorInicial === undefined)
        ) {
          valorInicial = 0;
        }

        valoresIniciais[chave] = valorInicial;
      }

      setDetalhe(detalheResp);
      setParametros(params);
      setOpcoes(opcoesNormalizadas);
      setForm(valoresIniciais);
      setModalParametrosAberto(true);
    } catch (error) {
      console.error(error);
      setErroModal(
        error?.response?.data?.detail ||
          error?.message ||
          "Erro ao carregar parâmetros do relatório."
      );
      setModalParametrosAberto(true);
    } finally {
      setLoadingMeta(false);
    }
  }

  async function gerarPreview() {
    if (!relatorioSelecionado?.cdarquivo) return;

    try {
      setLoadingPreview(true);
      setErroModal("");

      const payload = {
        ...montarPayloadBaseEmpresa(),
      };

      for (const param of parametros) {
        let valor = form[param.original_name];

        if (
          [
            "vendedor",
            "cliente",
            "natureza",
            "grupo",
            "marca",
            "cidade",
            "regiao",
            "fornecedor",
          ].includes(param.semantic_key) &&
          (valor === "" || valor === null || valor === undefined)
        ) {
          valor = 0;
        }

        if (param.semantic_key === "analise" && !valor) {
          valor = "GRUPO";
        }

        if (param.semantic_key === "tipo_data" && !valor) {
          valor = "EMISSAO";
        }

        payload[param.original_name] = valor;
      }

      const resposta = await executarPreviewRelatorio(
        relatorioSelecionado.cdarquivo,
        payload
      );

      setPreviewData(resposta);
      setModalParametrosAberto(false);
      setModalPreviewAberto(true);
    } catch (error) {
      console.error(error);
      setErroModal(
        error?.response?.data?.detail ||
          error?.message ||
          "Erro ao gerar preview do relatório."
      );
    } finally {
      setLoadingPreview(false);
    }
  }

  function imprimirPreview() {
    window.print();
  }

  function renderSelect(
    lista = [],
    valor,
    onChange,
    placeholder = "Selecione",
    semanticKey = ""
  ) {
    const listaNormalizada = adicionarOpcaoTodos(lista, semanticKey);

    return (
      <select value={valor} onChange={onChange} className="preview-select">
        {semanticKey === "empresa" && listaNormalizada.length === 0 ? (
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

    if (param.semantic_key === "analise") {
      return renderSelect(
        OPCOES_PANALISE,
        valor,
        (e) => atualizarCampo(param.original_name, e.target.value),
        "Selecione",
        "analise"
      );
    }

    if (param.semantic_key === "tipo_data") {
      return renderSelect(
        OPCOES_TIPODATA,
        valor,
        (e) => atualizarCampo(param.original_name, e.target.value),
        "Selecione",
        "tipo_data"
      );
    }

    if (param.semantic_key === "empresa") {
      return renderSelect(
        opcoes.empresas,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Selecione a empresa",
        "empresa"
      );
    }

    if (param.semantic_key === "vendedor") {
      return renderSelect(
        opcoes.vendedores,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "vendedor"
      );
    }

    if (param.semantic_key === "cliente") {
      return renderSelect(
        opcoes.clientes,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "cliente"
      );
    }

    if (param.semantic_key === "natureza") {
      return renderSelect(
        opcoes.naturezas,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todas",
        "natureza"
      );
    }

    if (param.semantic_key === "grupo") {
      return renderSelect(
        opcoes.grupos,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "grupo"
      );
    }

    if (param.semantic_key === "marca") {
      return renderSelect(
        opcoes.marcas,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "marca"
      );
    }

    if (param.semantic_key === "cidade") {
      return renderSelect(
        opcoes.cidades,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "cidade"
      );
    }

    if (param.semantic_key === "regiao") {
      return renderSelect(
        opcoes.regioes,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "regiao"
      );
    }

    if (param.semantic_key === "fornecedor") {
      return renderSelect(
        opcoes.fornecedores,
        valor,
        (e) => atualizarCampo(param.original_name, Number(e.target.value)),
        "Todos",
        "fornecedor"
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

  const totalRelatorios = relatoriosFiltrados.length;

  return (
    <div className="relatorios-lista-page">
      <div className="relatorios-lista-hero no-print">
        <div className="relatorios-lista-hero-texto">
          <h1>{titulo}</h1>
          <p>
            Consulte os relatórios disponíveis, filtre pelo nome e abra o preview
            sem sair da tela.
          </p>
        </div>

        <div className="relatorios-lista-busca-box">
          <input
            type="text"
            className="relatorios-lista-busca"
            placeholder="Buscar relatório por nome, descrição ou pasta..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
      </div>

      <div className="relatorios-lista-resultado no-print">
        {loadingLista
          ? "Carregando relatórios..."
          : `${totalRelatorios} relatório(s) encontrado(s)`}
      </div>

      {erroLista ? <div className="status-box erro no-print">{erroLista}</div> : null}

      {!loadingLista && !erroLista && relatoriosFiltrados.length === 0 ? (
        <div className="status-box no-print">Nenhum relatório encontrado.</div>
      ) : null}

      <div className="relatorios-lista-grid no-print">
        {relatoriosFiltrados.map((relatorio) => (
          <div className="relatorio-lista-card" key={relatorio.cdarquivo}>
            <div className="relatorio-lista-card-topo">
              <div className="relatorio-lista-card-titulo-box">
                <h3>{relatorio.nome}</h3>

                <div className="relatorio-lista-tags">
                  {relatorio.pasta ? (
                    <span className="relatorio-lista-tag">
                      Pasta: {relatorio.pasta}
                    </span>
                  ) : null}

                  {relatorio.pasta_pai ? (
                    <span className="relatorio-lista-tag">
                      Grupo: {relatorio.pasta_pai}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="relatorio-lista-acoes">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => abrirModalParametros(relatorio)}
                >
                  Visualizar
                </button>
              </div>
            </div>

            <div className="relatorio-lista-card-corpo">
              <div className="relatorio-lista-info-grid">
                <div className="relatorio-lista-info-item">
                  <span className="relatorio-lista-info-label">Código</span>
                  <strong>{relatorio.cdarquivo}</strong>
                </div>

                <div className="relatorio-lista-info-item">
                  <span className="relatorio-lista-info-label">
                    Última alteração
                  </span>
                  <strong>{formatarDataHora(relatorio.ultima_alteracao)}</strong>
                </div>
              </div>

              {relatorio.descricao ? (
                <p className="relatorio-lista-descricao">{relatorio.descricao}</p>
              ) : (
                <p className="relatorio-lista-descricao relatorio-lista-descricao-vazia">
                  Relatório sem descrição cadastrada.
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <Modal
        aberto={modalParametrosAberto}
        onFechar={() => {
          fecharModalParametros();
          limparEstadoModal();
        }}
        titulo={relatorioSelecionado?.nome || "Parâmetros do relatório"}
        subtitulo="Preencha os parâmetros para gerar o preview."
        largura="920px"
      >
        {loadingMeta ? (
          <div className="preview-hint">Carregando parâmetros...</div>
        ) : (
          <>
            <div className="preview-fields-grid">
              {parametros.map((param) => (
                <div className="preview-field" key={param.original_name}>
                  <label className="preview-label">{param.original_name}</label>
                  {renderCampo(param)}
                  <span className="preview-hint">
                    {param.semantic_key || param.inferred_type}
                  </span>
                </div>
              ))}
            </div>

            {erroModal ? (
              <div className="modal-error-box">{erroModal}</div>
            ) : null}

            <div className="modal-actions no-print">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  fecharModalParametros();
                  limparEstadoModal();
                }}
              >
                Fechar
              </button>

              <button
                type="button"
                className="btn-primary"
                onClick={gerarPreview}
                disabled={loadingPreview}
              >
                {loadingPreview ? "Gerando preview..." : "Gerar preview"}
              </button>
            </div>
          </>
        )}
      </Modal>

      <Modal
        aberto={modalPreviewAberto}
        onFechar={() => {
          fecharModalPreview();
          limparEstadoModal();
        }}
        titulo={relatorioSelecionado?.nome || "Preview do relatório"}
        subtitulo="Visualização do relatório pronta para conferência e impressão."
        largura="1280px"
      >
        {erroModal ? <div className="modal-error-box">{erroModal}</div> : null}

        <div className="modal-preview-toolbar no-print">
          <button type="button" className="btn-secondary" onClick={imprimirPreview}>
            Imprimir
          </button>

          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setModalPreviewAberto(false);
              setModalParametrosAberto(true);
            }}
          >
            Alterar parâmetros
          </button>
        </div>

        {previewData ? (
          <FastReportRenderer
            layout={detalhe?.layout_visual}
            linhas={previewData?.linhas || []}
            filtrosAplicados={filtrosAplicados}
            tituloRelatorio={relatorioSelecionado?.nome || "Preview do relatório"}
            totalRegistros={previewData?.total_registros || 0}
            detalhe={detalhe}
            previewData={previewData}
          />
        ) : (
          <div className="preview-hint">Nenhum preview gerado.</div>
        )}
      </Modal>
    </div>
  );
}