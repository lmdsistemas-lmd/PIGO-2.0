import "../../styles/relatorio-table.css";

const ORDEM_PREFERENCIAL = [
  "pev_id",
  "nf_numero",
  "pev_dt_emissao",
  "nf_dt_emissao",
  "pev_nome_cliente",
  "reg_descricao",
  "pev_vendedor",
  "formas",
  "nop_id",
  "nop_descricao",
  "nf_modelo",
  "nf_serie",
  "nf_status",
  "pev_sub_total",
  "pev_valor_desconto",
  "pev_valor_acrescimo",
  "pev_valor_total",
  "nf_valor_total",
  "nf_valor_st",
  "nf_valor_ipi",
  "nf_valor_fcp",
  "cli_regiao",
];

const LABELS_COLUNAS = {
  pev_id: "N. Ped.",
  nf_numero: "N. NFE",
  pev_dt_emissao: "Emissão Pedido",
  nf_dt_emissao: "Emissão NFE",
  pev_nome_cliente: "Cliente",
  reg_descricao: "Rota",
  pev_vendedor: "Vendedor",
  formas: "Forma Pagamento",
  nop_id: "Cód. Natureza",
  nop_descricao: "Natureza",
  nf_modelo: "Modelo",
  nf_serie: "Série",
  nf_status: "Status NFE",
  pev_sub_total: "Subtotal",
  pev_valor_desconto: "Desconto",
  pev_valor_acrescimo: "Acréscimo",
  pev_valor_total: "Total Bruto",
  nf_valor_total: "Total NFE",
  nf_valor_st: "Valor ST",
  nf_valor_ipi: "Valor IPI",
  nf_valor_fcp: "Valor FCP",
  cli_regiao: "Cód. Região",
};

const COLUNAS_VALOR = new Set([
  "pev_sub_total",
  "pev_valor_desconto",
  "pev_valor_acrescimo",
  "pev_valor_total",
  "nf_valor_total",
  "nf_valor_st",
  "nf_valor_ipi",
  "nf_valor_fcp",
]);

const COLUNAS_DATA = new Set([
  "pev_dt_emissao",
  "nf_dt_emissao",
]);

function limparValorVariavel(valor) {
  if (valor === null || valor === undefined) return "";
  return String(valor).replace(/^'+|'+$/g, "").trim();
}

function extrairVariaveisEmpresa(detalhe) {
  const variables = Array.isArray(detalhe?.variables) ? detalhe.variables : [];

  function get(nome) {
    const item = variables.find(
      (variavel) =>
        String(variavel?.name || "").trim().toLowerCase() ===
        String(nome).trim().toLowerCase()
    );
    return limparValorVariavel(item?.value);
  }

  return {
    razaoSocial: get("RazaoSocial"),
    nomeFantasia: get("NomeFantasia"),
    cnpj: get("CNPJ"),
    endereco: get("Endereco"),
    numero: get("Numero"),
    bairro: get("Bairro"),
    cidade: get("Cidade"),
    uf: get("Uf"),
    telefone: get("Telefone"),
  };
}

function formatarData(valor) {
  if (!valor) return "-";

  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) {
    const [ano, mes, dia] = valor.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  return String(valor);
}

function formatarMoeda(valor) {
  const numero = Number(valor);

  if (Number.isNaN(numero)) {
    return valor === null || valor === undefined || valor === "" ? "-" : String(valor);
  }

  return numero.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatarValorPorColuna(coluna, valor) {
  if (valor === null || valor === undefined || valor === "") {
    return "-";
  }

  if (COLUNAS_DATA.has(coluna)) {
    return formatarData(valor);
  }

  if (COLUNAS_VALOR.has(coluna)) {
    return formatarMoeda(valor);
  }

  return String(valor);
}

function isColunaTotalmenteVazia(coluna, linhas) {
  return linhas.every((linha) => {
    const valor = linha?.[coluna];
    return valor === null || valor === undefined || valor === "";
  });
}

function ordenarColunas(colunas) {
  return [...colunas].sort((a, b) => {
    const indexA = ORDEM_PREFERENCIAL.indexOf(a);
    const indexB = ORDEM_PREFERENCIAL.indexOf(b);

    const pesoA = indexA === -1 ? 999 : indexA;
    const pesoB = indexB === -1 ? 999 : indexB;

    if (pesoA !== pesoB) return pesoA - pesoB;
    return a.localeCompare(b);
  });
}

function obterLabelColuna(coluna) {
  return LABELS_COLUNAS[coluna] || coluna;
}

function obterPeriodo(filtrosAplicados) {
  const dataInicial = filtrosAplicados.find((item) =>
    ["DATAINICIAL", "DTINICIAL", "INICIAL"].includes(
      String(item.nome).toUpperCase()
    )
  );

  const dataFinal = filtrosAplicados.find((item) =>
    ["DATAFINAL", "DTFINAL", "FINAL"].includes(
      String(item.nome).toUpperCase()
    )
  );

  if (dataInicial && dataFinal) {
    return `${dataInicial.valor} até ${dataFinal.valor}`;
  }

  if (dataInicial) return dataInicial.valor;
  if (dataFinal) return dataFinal.valor;

  return "Não informado";
}

function obterNaturezaPrincipal(linhas) {
  if (!Array.isArray(linhas) || linhas.length === 0) return "";

  const primeiraLinha = linhas[0];
  const id = primeiraLinha?.nop_id;
  const descricao = primeiraLinha?.nop_descricao;

  if (id && descricao) return `${id} - ${descricao}`;
  if (descricao) return String(descricao);
  if (id) return String(id);

  return "";
}

export default function RelatorioPreviewTable({
  colunas = [],
  linhas = [],
  totalRegistros = 0,
  detalhe = null,
  filtrosAplicados = [],
  tituloRelatorio = "Preview do relatório",
}) {
  const linhasSeguras = Array.isArray(linhas) ? linhas : [];
  const colunasSeguras = Array.isArray(colunas) ? colunas : [];

  if (!colunasSeguras.length) {
    return <div className="preview-empty">Nenhum dado para exibir.</div>;
  }

  const empresa = extrairVariaveisEmpresa(detalhe);

  const colunasVisiveis = ordenarColunas(
    colunasSeguras.filter((coluna) => !isColunaTotalmenteVazia(coluna, linhasSeguras))
  );

  const periodo = obterPeriodo(filtrosAplicados);
  const naturezaPrincipal = obterNaturezaPrincipal(linhasSeguras);

  const filtrosDestaque = filtrosAplicados.filter((item) => {
    const nome = String(item.nome).toUpperCase();
    return !["DATAINICIAL", "DATAFINAL"].includes(nome);
  });

  const totalBruto = linhasSeguras.reduce((acc, linha) => {
    const valor = Number(linha?.pev_valor_total || 0);
    return acc + (Number.isNaN(valor) ? 0 : valor);
  }, 0);

  return (
    <div className="report-preview">
      <div className="report-sheet">
        <div className="report-header">
          <div className="report-company-line">
            <div>
              <h2 className="report-company-name">
                {empresa.razaoSocial || empresa.nomeFantasia || "Empresa não identificada"}
              </h2>
              <div className="report-company-meta">
                {empresa.cnpj ? <span>CNPJ: {empresa.cnpj}</span> : null}
                {empresa.telefone ? <span>Telefone: {empresa.telefone}</span> : null}
              </div>
              {(empresa.endereco || empresa.numero || empresa.bairro || empresa.cidade || empresa.uf) && (
                <div className="report-company-address">
                  {[empresa.endereco, empresa.numero, empresa.bairro, empresa.cidade, empresa.uf]
                    .filter(Boolean)
                    .join(" • ")}
                </div>
              )}
            </div>

            <div className="report-header-side">
              <div className="report-header-badge">Preview Web</div>
            </div>
          </div>

          <div className="report-title-block">
            <h1 className="report-title">{tituloRelatorio}</h1>
            <div className="report-subtitle">
              Relatório gerado a partir da estrutura do FastReport
            </div>
          </div>

          <div className="report-context-grid">
            <div className="report-context-card">
              <span className="report-context-label">Período</span>
              <strong>{periodo}</strong>
            </div>

            <div className="report-context-card">
              <span className="report-context-label">Natureza</span>
              <strong>{naturezaPrincipal || "Não informada"}</strong>
            </div>

            <div className="report-context-card">
              <span className="report-context-label">Total de registros</span>
              <strong>{totalRegistros}</strong>
            </div>

            <div className="report-context-card">
              <span className="report-context-label">Total bruto</span>
              <strong>{formatarMoeda(totalBruto)}</strong>
            </div>
          </div>

          {filtrosDestaque.length > 0 && (
            <div className="report-filters-box">
              <div className="report-filters-title">Filtros aplicados</div>

              <div className="report-filters-list">
                {filtrosDestaque.map((filtro) => (
                  <div className="report-filter-chip" key={filtro.nome}>
                    <span>{filtro.nome}</span>
                    <strong>{filtro.valor}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="preview-summary">
          Total de registros: <strong>{totalRegistros}</strong>
        </div>

        <div className="preview-table-wrap">
          <table className="preview-table report-table">
            <thead>
              <tr>
                {colunasVisiveis.map((coluna) => (
                  <th
                    key={coluna}
                    className={COLUNAS_VALOR.has(coluna) ? "is-number" : ""}
                  >
                    {obterLabelColuna(coluna)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {linhasSeguras.map((linha, index) => (
                <tr key={index}>
                  {colunasVisiveis.map((coluna) => (
                    <td
                      key={coluna}
                      className={COLUNAS_VALOR.has(coluna) ? "is-number" : ""}
                    >
                      {formatarValorPorColuna(coluna, linha[coluna])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}