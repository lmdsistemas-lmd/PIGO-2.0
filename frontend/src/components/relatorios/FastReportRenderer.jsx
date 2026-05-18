import React, { Fragment, useMemo } from "react";

function limparValorVariavel(valor) {
  if (valor === null || valor === undefined) return "";
  return String(valor).replace(/^'+|'+$/g, "").trim();
}

function obterVariavel(variables = [], nome) {
  const item = variables.find(
    (variavel) =>
      String(variavel?.name || "").trim().toLowerCase() ===
      String(nome).trim().toLowerCase()
  );

  return limparValorVariavel(item?.value);
}

function formatarData(valor) {
  if (!valor) return "";

  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) {
    const [ano, mes, dia] = valor.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  return String(valor);
}

function formatarMoeda(valor) {
  const numero = Number(valor);

  if (Number.isNaN(numero)) {
    return valor === null || valor === undefined ? "" : String(valor);
  }

  return numero.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatarNumero(valor) {
  const numero = Number(valor);

  if (Number.isNaN(numero)) {
    return valor === null || valor === undefined ? "" : String(valor);
  }

  return numero.toLocaleString("pt-BR");
}

function formatarPercentual(valor) {
  const numero = Number(valor);

  if (Number.isNaN(numero)) {
    return valor === null || valor === undefined ? "" : String(valor);
  }

  return `${numero.toFixed(2)}%`;
}

function formatarValor(campo, valor) {
  if (valor === null || valor === undefined) return "";

  const campoNormalizado = String(campo || "").toLowerCase();

  if (
    campoNormalizado.includes("data") ||
    campoNormalizado.includes("dt_") ||
    campoNormalizado.endsWith("_dt") ||
    campoNormalizado.endsWith("date")
  ) {
    return formatarData(valor);
  }

  if (
    campoNormalizado.includes("percentual") ||
    campoNormalizado === "perc" ||
    campoNormalizado.endsWith("_perc")
  ) {
    return formatarPercentual(valor);
  }

  if (
    campoNormalizado.includes("valor") ||
    campoNormalizado.includes("total") ||
    campoNormalizado.includes("desconto") ||
    campoNormalizado.includes("acrescimo") ||
    campoNormalizado.includes("preco") ||
    campoNormalizado.includes("vlr") ||
    campoNormalizado.includes("lucro") ||
    campoNormalizado.includes("custo") ||
    campoNormalizado.includes("venda") ||
    campoNormalizado.includes("devolucao") ||
    campoNormalizado.includes("faturamento")
  ) {
    return formatarMoeda(valor);
  }

  if (typeof valor === "number") {
    return formatarNumero(valor);
  }

  return String(valor);
}

function normalizarNumeroFastReport(valor, fallback = 0) {
  if (valor === null || valor === undefined || valor === "") return fallback;

  if (typeof valor === "number") {
    return Number.isNaN(valor) ? fallback : valor;
  }

  const textoOriginal = String(valor).trim();
  if (!textoOriginal) return fallback;

  let texto = textoOriginal;

  const temVirgula = texto.includes(",");
  const temPonto = texto.includes(".");

  if (temVirgula && temPonto) {
    texto = texto.replace(/\./g, "").replace(",", ".");
  } else if (temVirgula) {
    texto = texto.replace(",", ".");
  }

  const numero = Number(texto);
  return Number.isNaN(numero) ? fallback : numero;
}

function fastReportColorToCss(color) {
  if (!color) return null;

  const mapa = {
    clBlack: "#000000",
    clWhite: "#ffffff",
    clRed: "#ff0000",
    clBlue: "#0000ff",
    clGreen: "#008000",
    clYellow: "#ffff00",
    clGray: "#808080",
    clSilver: "#c0c0c0",
    clMaroon: "#800000",
    clNavy: "#000080",
    clOlive: "#808000",
    clPurple: "#800080",
    clTeal: "#008080",
    clLime: "#00ff00",
    clAqua: "#00ffff",
    clFuchsia: "#ff00ff",
  };

  if (mapa[color]) {
    return mapa[color];
  }

  if (/^\$[0-9a-fA-F]{6,8}$/.test(color)) {
    const hex = color.replace("$", "");
    const semAlpha = hex.length === 8 ? hex.slice(2) : hex;

    if (semAlpha.length === 6) {
      const bb = semAlpha.slice(0, 2);
      const gg = semAlpha.slice(2, 4);
      const rr = semAlpha.slice(4, 6);
      return `#${rr}${gg}${bb}`;
    }
  }

  return null;
}

function buildMemoStyle(memo, options = {}) {
  const { absolute = true, leftOverride = null, topOverride = null } = options;

  const height = normalizarNumeroFastReport(memo?.height, 12);
  const fontSize = normalizarNumeroFastReport(memo?.font_size, 0);
  const width = normalizarNumeroFastReport(memo?.width, 0);

  const style = {
    boxSizing: "border-box",
    whiteSpace: "pre-wrap",
    lineHeight: 1.15,
    padding: "0",
    overflow: "visible",
    fontSize: fontSize > 0 ? `${fontSize}px` : "11px",
    minHeight: `${height}px`,
  };

  if (absolute) {
    style.position = "absolute";
    style.left = `${leftOverride ?? normalizarNumeroFastReport(memo?.left)}px`;
    style.top = `${topOverride ?? normalizarNumeroFastReport(memo?.top)}px`;
    if (width > 0) {
      style.width = `${width}px`;
    }
  }

  if (memo?.h_align === "haRight") {
    style.textAlign = "right";
  } else if (memo?.h_align === "haCenter") {
    style.textAlign = "center";
  } else if (memo?.h_align === "haBlock") {
    style.textAlign = "justify";
  } else {
    style.textAlign = "left";
  }

  if (memo?.v_align === "vaCenter") {
    style.display = "flex";
    style.alignItems = "center";
  } else if (memo?.v_align === "vaBottom") {
    style.display = "flex";
    style.alignItems = "flex-end";
  }

  style.fontFamily = memo?.font_name || "Arial, sans-serif";

  const fontStyle = String(memo?.font_style || "");

  if (fontStyle.includes("fsBold")) {
    style.fontWeight = 700;
  }

  if (fontStyle.includes("fsItalic")) {
    style.fontStyle = "italic";
  }

  if (fontStyle.includes("fsUnderline")) {
    style.textDecoration = "underline";
  }

  const color = fastReportColorToCss(memo?.color);
  if (color) {
    style.color = color;
  }

  const fillColor = fastReportColorToCss(memo?.fill_color);
  if (fillColor) {
    style.backgroundColor = fillColor;
  }

  const borderColor = fastReportColorToCss(memo?.border_color);
  const borderWidth = normalizarNumeroFastReport(memo?.border_width);
  if (borderColor && borderWidth > 0) {
    style.border = `${Math.max(borderWidth, 1)}px solid ${borderColor}`;
  }

  return style;
}

function ordenarPorPosicao(items = []) {
  return [...items].sort((a, b) => {
    const topA = normalizarNumeroFastReport(a?.top, 0);
    const topB = normalizarNumeroFastReport(b?.top, 0);

    if (topA !== topB) {
      return topA - topB;
    }

    const leftA = normalizarNumeroFastReport(a?.left, 0);
    const leftB = normalizarNumeroFastReport(b?.left, 0);

    return leftA - leftB;
  });
}

function calcularTopMinimo(memos = []) {
  if (!memos.length) return 0;
  return Math.min(
    ...memos.map((memo) => normalizarNumeroFastReport(memo?.top, 0))
  );
}

function calcularAlturaBloco(memos = [], minimo = 48, topBase = 0) {
  if (!memos.length) return minimo;

  const maiorBottom = Math.max(
    ...memos.map((memo) => {
      const top = normalizarNumeroFastReport(memo?.top, 0) - topBase;
      const height = normalizarNumeroFastReport(memo?.height, 12);
      return top + height;
    })
  );

  return Math.max(maiorBottom + 12, minimo);
}

function obterMemosDaBanda(layout, bandName) {
  const memos = Array.isArray(layout?.memos) ? layout.memos : [];
  return memos.filter((memo) => memo?.band_name === bandName);
}

function obterBandasPorTipo(layout, bandType) {
  const bands = Array.isArray(layout?.bands) ? layout.bands : [];
  return ordenarPorPosicao(bands.filter((band) => band?.type === bandType));
}

function limparTexto(texto) {
  return String(texto || "").trim();
}

function memoTemExpressaoDeCampo(memo) {
  const texto = limparTexto(memo?.text);
  if (!texto) return false;

  return (
    /\[[A-Za-z0-9_]+\."[^"]+"\]/.test(texto) ||
    /<\s*[A-Za-z0-9_]+\."[^"]+"\s*>/.test(texto) ||
    /\[[A-Za-z0-9_]+\]/.test(texto)
  );
}

function extrairReferenciaCampo(texto) {
  const valor = limparTexto(texto);

  let match = valor.match(/\[([A-Za-z0-9_]+)\."([^"]+)"\]/);
  if (match) {
    return {
      dataset: match[1],
      field: match[2],
    };
  }

  match = valor.match(/<\s*([A-Za-z0-9_]+)\."([^"]+)"\s*>/);
  if (match) {
    return {
      dataset: match[1],
      field: match[2],
    };
  }

  match = valor.match(/\[([A-Za-z0-9_]+)\]/);
  if (match) {
    const token = match[1];

    if (
      [
        "Date",
        "Time",
        "Page",
        "Page#",
        "TotalPages",
        "TotalPages#",
        "Line",
      ].includes(token)
    ) {
      return null;
    }

    return {
      dataset: null,
      field: token,
    };
  }

  return null;
}

function extrairAgregacao(texto) {
  const valor = limparTexto(texto);

  // Suporta SUM(<Dataset."Campo">, Banda) ou SUM([Campo], Banda) ou SUM(Campo)
  const match = valor.match(
    /(SUM|COUNT|AVG|MIN|MAX)\s*\(\s*(?:<|\[)?(?:([A-Za-z0-9_]+)\.)?"?([A-Za-z0-9_]+)"?(?:>|\])?(?:\s*,\s*([A-Za-z0-9_]+))?\s*\)/i
  );

  if (!match) return null;

  return {
    func: String(match[1]).toUpperCase(),
    dataset: match[2] || null,
    field: match[3] || null,
    band: match[4] || null,
  };
}

function normalizarNomeCampo(nome) {
  return String(nome || "").trim().toLowerCase();
}

function obterValorCampo(row, fieldName) {
  if (!row || !fieldName) return undefined;

  const alvo = normalizarNomeCampo(fieldName);

  for (const [chave, valor] of Object.entries(row)) {
    if (normalizarNomeCampo(chave) === alvo) {
      return valor;
    }
  }

  return undefined;
}

function calcularAgregacao(rows = [], agg) {
  if (!agg) return "";

  const linhas = Array.isArray(rows) ? rows : [];
  const campo = agg.field;

  if (agg.func === "COUNT") {
    return String(linhas.length);
  }

  const valores = linhas
    .map((row) => normalizarNumeroFastReport(obterValorCampo(row, campo), NaN))
    .filter((numero) => !Number.isNaN(numero));

  if (!valores.length) {
    return "";
  }

  if (agg.func === "SUM") {
    return formatarMoeda(valores.reduce((acc, valor) => acc + valor, 0));
  }

  if (agg.func === "AVG") {
    return formatarMoeda(
      valores.reduce((acc, valor) => acc + valor, 0) / valores.length
    );
  }

  if (agg.func === "MIN") {
    return formatarValor(campo, Math.min(...valores));
  }

  if (agg.func === "MAX") {
    return formatarValor(campo, Math.max(...valores));
  }

  return "";
}

function obterFiltroPorNome(filtrosAplicados = [], nomesAceitos = []) {
  return filtrosAplicados.find((item) =>
    nomesAceitos.includes(String(item?.nome || "").trim().toUpperCase())
  );
}

function deveOcultarMemoDoTopo(memo) {
  const texto = limparTexto(memo?.text).toUpperCase();

  if (!texto) return true;
  if (texto.includes("RELATORIOS GO UP SISTEMAS")) return true;
  if (texto === "[(&LT;DATE&GT;)]" || texto === "[(<DATE>)]") return true;
  if (texto === "[(&LT;TIME&GT;)]" || texto === "[(<TIME>)]") return true;

  return false;
}

function resolverTextoMemo(textoOriginal, context = {}) {
  if (!textoOriginal) return "";

  const {
    row = null,
    variables = [],
    filtrosAplicados = [],
    rowsForTotals = [],
    pageNumber = 1,
    totalPages = 1,
    tituloRelatorio = "",
  } = context;

  let texto = String(textoOriginal);

  // 1. Processar Agregações (SUM, COUNT, etc) - Suporta vírgulas e bandas
  const regexAgg = /(SUM|COUNT|AVG|MIN|MAX)\s*\(\s*(?:<|\[)?(?:([A-Za-z0-9_]+)\.)?"?([A-Za-z0-9_]+)"?(?:>|\])?(?:\s*,\s*([A-Za-z0-9_]+))?\s*\)/gi;
  texto = texto.replace(regexAgg, (matchFull) => {
    const agg = extrairAgregacao(matchFull);
    if (agg) {
      return calcularAgregacao(rowsForTotals, agg);
    }
    return matchFull;
  });

  // 2. Propriedades de Componentes (Ex: [cbbAnalise.Text])
  texto = texto.replace(/\[([A-Za-z0-9_]+)\.Text\]/gi, (_, componente) => {
    const nomeBusca = String(componente).toUpperCase();
    const filtro = filtrosAplicados.find(f => 
      String(f.nome || "").toUpperCase() === nomeBusca || 
      String(f.semanticKey || "").toUpperCase() === nomeBusca
    );
    return filtro?.valor || "";
  });

  // 3. Campos do Dataset com notação [Dataset."Campo"]
  texto = texto.replace(/\[([A-Za-z0-9_]+)\."([^"]+)"\]/g, (_, dataset, campo) => {
    const valor = obterValorCampo(row, campo);
    return formatarValor(campo, valor);
  });

  // 4. Campos do Dataset com notação <Dataset."Campo">
  texto = texto.replace(/<\s*([A-Za-z0-9_]+)\."([^"]+)"\s*>/g, (_, dataset, campo) => {
    const valor = obterValorCampo(row, campo);
    return formatarValor(campo, valor);
  });

  // 5. Parâmetros de Data Específicos
  texto = texto.replace(/\[DateEdit1\.date\]/gi, () => {
    const inicial = obterFiltroPorNome(filtrosAplicados, [
      "DATAINICIAL",
      "DTINICIAL",
      "INICIAL",
      "DATA_INICIAL"
    ]);
    return inicial?.valor || "";
  });

  texto = texto.replace(/\[DateEdit2\.date\]/gi, () => {
    const final = obterFiltroPorNome(filtrosAplicados, [
      "DATAFINAL",
      "DTFINAL",
      "FINAL",
      "DATA_FINAL"
    ]);
    return final?.valor || "";
  });

  // 6. Variáveis de Sistema do FastReport
  texto = texto.replace(/\[\(<Date>\)\]/gi, () => new Date().toLocaleDateString("pt-BR"));
  texto = texto.replace(/\[\(<Time>\)\]/gi, () => new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }));
  texto = texto.replace(/\[Page#\]/gi, () => String(pageNumber));
  texto = texto.replace(/\[TotalPages#\]/gi, () => String(totalPages));
  texto = texto.replace(/\[Page\]/gi, () => String(pageNumber));
  texto = texto.replace(/\[TotalPages\]/gi, () => String(totalPages));

  // 7. Variáveis Genéricas ou Campos Simples [TOKEN]
  texto = texto.replace(/\[([A-Za-z0-9_]+)\]/g, (fullMatch, token) => {
    const tokenUpper = String(token).toUpperCase();

    if (tokenUpper === "TITULORELATORIO") return tituloRelatorio;

    // Tentar filtros/parâmetros primeiro
    const filtro = filtrosAplicados.find(f => String(f.nome || "").toUpperCase() === tokenUpper);
    if (filtro) return filtro.valor;

    // Tentar variáveis injetadas
    const valorVariavel = obterVariavel(variables, token);
    if (valorVariavel) return valorVariavel;

    // Tentar campos da linha atual
    const valorLinha = obterValorCampo(row, token);
    if (valorLinha !== undefined) return formatarValor(token, valorLinha);

    return token; // Retorna apenas o nome sem os colchetes se não achar valor
  });

  // 8. Ajustes finais de texto sugeridos pelo usuário
  texto = texto.replace(/Total do cbbAnalise/gi, "Total do Período");
  texto = texto.replace(/Total do \./gi, "Total do Período");

  // Limpeza final: remove qualquer colchete que tenha sobrado no texto
  texto = texto.replace(/[\[\]]/g, "");

  return texto.replace(/\s+-\s+-\s*$/g, "").trim();
}

function construirColunasDetalhe(masterMemos = [], headerMemos = []) {
  const colunas = ordenarPorPosicao(
    masterMemos.filter((memo) => memoTemExpressaoDeCampo(memo))
  );

  return colunas.map((memo, index) => {
    const ref = extrairReferenciaCampo(memo?.text) || {
      dataset: memo?.data_set || null,
      field: memo?.data_field || memo?.name || `coluna_${index + 1}`,
    };

    const headerMemo = headerMemos[index];
    const titulo =
      limparTexto(headerMemo?.text) ||
      limparTexto(ref.field) ||
      limparTexto(memo?.name) ||
      `Coluna ${index + 1}`;

    return {
      key: `${ref.dataset || "row"}:${ref.field || memo?.name || index}`,
      field: ref.field || memo?.name || `coluna_${index + 1}`,
      dataset: ref.dataset,
      memo,
      headerMemo,
      title: titulo,
    };
  });
}

function extrairCampoAgrupamento(groupBand, groupMemos = []) {
  const conditionRef = extrairReferenciaCampo(groupBand?.condition);
  if (conditionRef?.field) {
    return conditionRef;
  }

  const memoComCampo = groupMemos.find((memo) => memoTemExpressaoDeCampo(memo));
  if (memoComCampo) {
    return extrairReferenciaCampo(memoComCampo?.text);
  }

  return null;
}

function agruparLinhas(linhas = [], groupRef = null) {
  if (!groupRef?.field) {
    return [
      {
        key: "default-group",
        label: "",
        rows: Array.isArray(linhas) ? linhas : [],
      },
    ];
  }

  const mapa = new Map();

  for (const row of linhas) {
    const valor = obterValorCampo(row, groupRef.field);
    const chave =
      valor === null || valor === undefined || valor === ""
        ? "__vazio__"
        : String(valor);

    if (!mapa.has(chave)) {
      mapa.set(chave, {
        key: chave,
        label: valor,
        rows: [],
      });
    }

    mapa.get(chave).rows.push(row);
  }

  return Array.from(mapa.values());
}

function larguraRelatorio(layout) {
  const memos = Array.isArray(layout?.memos) ? layout.memos : [];
  const bands = Array.isArray(layout?.bands) ? layout.bands : [];
  const pages = Array.isArray(layout?.pages) ? layout.pages : [];

  const larguraMemos = memos.map((memo) => {
    const left = normalizarNumeroFastReport(memo?.left, 0);
    const width = normalizarNumeroFastReport(memo?.width, 0);
    return left + width;
  });

  const larguraBandas = bands.map((band) => {
    const left = normalizarNumeroFastReport(band?.left, 0);
    const width = normalizarNumeroFastReport(band?.width, 0);
    return left + width;
  });

  const larguraPaginas = pages.map((page) =>
    normalizarNumeroFastReport(page?.width, 0)
  );

  const larguraCalculada = Math.max(
    900,
    ...larguraMemos,
    ...larguraBandas,
    ...larguraPaginas
  );

  return Math.min(larguraCalculada, 1600);
}

function renderizarColecaoAbsoluta({
  memos = [],
  context,
  largura,
  keyPrefix = "memo",
  minimo = 24,
}) {
  if (!memos.length) return null;

  const topBase = calcularTopMinimo(memos);
  const altura = calcularAlturaBloco(memos, minimo, topBase);

  return (
    <div
      style={{
        position: "relative",
        width: `${largura}px`,
        minHeight: `${altura}px`,
        margin: "0 auto",
      }}
    >
      {memos.map((memo, index) => (
        <div
          key={`${keyPrefix}-${memo?.name || index}-${memo?.left}-${memo?.top}`}
          style={buildMemoStyle(memo, {
            topOverride: normalizarNumeroFastReport(memo?.top, 0) - topBase,
          })}
        >
          {resolverTextoMemo(memo?.text || "", context)}
        </div>
      ))}
    </div>
  );
}

function renderizarBandaAbsoluta({ band, memos, context, largura }) {
  if (!band || !memos.length) return null;

  return renderizarColecaoAbsoluta({
    memos,
    context,
    largura,
    keyPrefix: band?.name || "band",
    minimo: normalizarNumeroFastReport(band?.height, 24),
  });
}

function renderizarBandasAbsolutasMultiplas({
  bands = [],
  layout,
  context,
  largura,
  filterFn = null,
}) {
  return bands.map((band) => {
    let memos = obterMemosDaBanda(layout, band?.name);
    memos = ordenarPorPosicao(memos);

    if (filterFn) {
      memos = memos.filter(filterFn);
    }

    if (!memos.length) return null;

    return (
      <div key={band?.name} style={{ marginBottom: "8px" }}>
        {renderizarBandaAbsoluta({
          band,
          memos,
          context,
          largura,
        })}
      </div>
    );
  });
}

function extrairPeriodo(filtrosAplicados = []) {
  const dataInicial = filtrosAplicados.find(
    (item) => String(item?.semanticKey || "") === "data_inicial"
  );
  const dataFinal = filtrosAplicados.find(
    (item) => String(item?.semanticKey || "") === "data_final"
  );

  return {
    inicial: dataInicial?.valor || "",
    final: dataFinal?.valor || "",
  };
}

function agruparLinhasAnaliticas(linhas = []) {
  const mapa = new Map();

  for (const item of linhas) {
    const codigo = item?.plano_conta_principal || "SEM_GRUPO";

    if (!mapa.has(codigo)) {
      mapa.set(codigo, {
        codigo,
        descricao: item?.descricao_principal || "",
        totalPorGrupo: Number(item?.total_por_grupo || 0),
        percentualGrupo: Number(item?.percentual_grupo || 0),
        totalGastos: Number(item?.total_gastos || 0),
        itens: [],
      });
    }

    mapa.get(codigo).itens.push({
      planoContaFilho: item?.plano_conta_filho || "",
      descricaoFilho: item?.descricao_filho || "",
      valorFilho: Number(item?.valor_filho || 0),
      percentualFilho: Number(item?.percentual_filho || 0),
      raw: item,
    });
  }

  return Array.from(mapa.values());
}

function LinhaResumo({ label, valor, classe = "" }) {
  return (
    <div className={`dre-resumo-linha ${classe}`}>
      <span className="dre-resumo-label">{label}</span>
      <strong className="dre-resumo-value">{formatarMoeda(valor)}</strong>
    </div>
  );
}

function DreCompostoRenderer({
  previewData,
  filtrosAplicados = [],
  tituloRelatorio = "Preview do relatório",
}) {
  const linhas = Array.isArray(previewData?.linhas) ? previewData.linhas : [];
  const grupos = useMemo(() => agruparLinhasAnaliticas(linhas), [linhas]);
  const periodo = extrairPeriodo(filtrosAplicados);
  const resumo = previewData?.resumo || {};

  return (
    <div className="report-preview">
      <div className="report-sheet report-sheet-dre">
        <div className="dre-header no-print">
          <h2 className="dre-title">{tituloRelatorio}</h2>
          <p className="dre-periodo">
            Data Inicial: {periodo.inicial || "-"} / Data Final: {periodo.final || "-"}
          </p>
        </div>

        <div className="dre-resumo-bloco">
          <LinhaResumo
            label="FATURAMENTO BRUTO"
            valor={resumo.faturamento_bruto}
            classe="dre-resumo-verde"
          />
          <LinhaResumo
            label="DEVOLUÇÕES DE PRODUTOS"
            valor={resumo.devolucoes}
            classe="dre-resumo-vermelho"
          />
          <LinhaResumo
            label="CUSTO DE MERCADORIA DEVOLVIDA"
            valor={resumo.custo_mercadoria_devolvida}
            classe="dre-resumo-vermelho-forte"
          />
          <LinhaResumo
            label="CUSTO MERCADORIA VENDIDA"
            valor={resumo.custo_mercadoria_vendida}
            classe="dre-resumo-laranja"
          />
          <LinhaResumo
            label="LUCRO BRUTO"
            valor={resumo.lucro_bruto}
            classe="dre-resumo-preto"
          />
        </div>

        <div className="dre-analitico-lista">
          {grupos.map((grupo) => (
            <section className="dre-grupo" key={grupo.codigo}>
              <div className="dre-grupo-header">
                <span className="dre-grupo-titulo">
                  {grupo.codigo} - {grupo.descricao}
                </span>
                <strong className="dre-grupo-total">
                  {formatarMoeda(grupo.totalPorGrupo)}
                </strong>
              </div>

              <div className="dre-grupo-itens">
                {grupo.itens.map((item, index) => (
                  <div
                    className="dre-grupo-item"
                    key={`${grupo.codigo}-${item.planoContaFilho}-${index}`}
                  >
                    <span className="dre-grupo-item-label">
                      {item.planoContaFilho} - {item.descricaoFilho}
                    </span>
                    <strong className="dre-grupo-item-value">
                      {formatarMoeda(item.valorFilho)}
                    </strong>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="dre-footer-resumo">
          <LinhaResumo
            label="DESPESAS TOTAIS"
            valor={resumo.despesas_totais}
            classe="dre-resumo-vermelho-total"
          />
          <LinhaResumo
            label="LUCRO LIQUIDO //// PREJUIZO"
            valor={resumo.lucro_liquido_prejuizo}
            classe="dre-resumo-oliva"
          />
          <div className="dre-resumo-linha dre-resumo-vermelho-total">
            <span className="dre-resumo-label">RELAÇÃO DESP X RECEITAS</span>
            <strong className="dre-resumo-value">
              {formatarPercentual(resumo.relacao_despesa_receita)}
            </strong>
          </div>
          <div className="dre-resumo-linha dre-resumo-verde-final">
            <span className="dre-resumo-label">RENTABILIDADE SOBRE VENDAS</span>
            <strong className="dre-resumo-value">
              {formatarPercentual(resumo.rentabilidade_sobre_vendas)}
            </strong>
          </div>
        </div>

        <div className="preview-summary no-print">
          Total de registros: <strong>{previewData?.total_registros || linhas.length}</strong>
        </div>
      </div>
    </div>
  );
}

export default function FastReportRenderer({
  layout,
  linhas = [],
  filtrosAplicados = [],
  tituloRelatorio = "Preview do relatório",
  totalRegistros = 0,
  detalhe = null,
  previewData = null,
}) {
  if (previewData?.modo_relatorio === "dre_composto") {
    return (
      <DreCompostoRenderer
        previewData={previewData}
        filtrosAplicados={filtrosAplicados}
        tituloRelatorio={tituloRelatorio}
      />
    );
  }

  const linhasSeguras = Array.isArray(linhas) ? linhas : [];
  const variables = Array.isArray(detalhe?.variables) ? detalhe.variables : [];
  const memos = Array.isArray(layout?.memos) ? layout.memos : [];
  const bands = Array.isArray(layout?.bands) ? layout.bands : [];

  if (!layout || !memos.length || !bands.length) {
    return (
      <div className="preview-empty">
        Layout visual não disponível para este relatório.
      </div>
    );
  }

  const largura = larguraRelatorio(layout);

  const reportTitleBands = obterBandasPorTipo(layout, "TfrxReportTitle");
  const pageHeaderBands = obterBandasPorTipo(layout, "TfrxPageHeader");
  const groupHeaderBands = obterBandasPorTipo(layout, "TfrxGroupHeader");
  const masterBands = obterBandasPorTipo(layout, "TfrxMasterData");
  const groupFooterBands = obterBandasPorTipo(layout, "TfrxGroupFooter");
  const reportSummaryBands = obterBandasPorTipo(layout, "TfrxReportSummary");
  const pageFooterBands = obterBandasPorTipo(layout, "TfrxPageFooter");

  const mainMasterBand = masterBands[0] || null;
  const mainGroupHeaderBand = groupHeaderBands[0] || null;
  const mainGroupFooterBand = groupFooterBands[0] || null;

  const titleMemos = reportTitleBands.flatMap((band) =>
    obterMemosDaBanda(layout, band?.name)
  );

  const titleMemosVisiveis = ordenarPorPosicao(titleMemos).filter(
    (memo) => !deveOcultarMemoDoTopo(memo)
  );

  const pageHeaderMemos = pageHeaderBands.slice(0, 1).flatMap((band) =>
    obterMemosDaBanda(layout, band?.name)
  );

  const groupHeaderMemos = mainGroupHeaderBand
    ? ordenarPorPosicao(obterMemosDaBanda(layout, mainGroupHeaderBand?.name))
    : [];

  const masterMemos = mainMasterBand
    ? ordenarPorPosicao(obterMemosDaBanda(layout, mainMasterBand?.name))
    : [];

  const headerMemosBase =
    pageHeaderMemos.length > 0
      ? ordenarPorPosicao(pageHeaderMemos).filter(
          (memo) => !memoTemExpressaoDeCampo(memo)
        )
      : groupHeaderMemos.filter((memo) => !memoTemExpressaoDeCampo(memo));

  const groupLabelMemos = groupHeaderMemos.filter((memo) =>
    memoTemExpressaoDeCampo(memo)
  );

  const colunas = construirColunasDetalhe(masterMemos, headerMemosBase);
  const groupRef = extrairCampoAgrupamento(mainGroupHeaderBand, groupHeaderMemos);
  const grupos = agruparLinhas(linhasSeguras, groupRef);

  const summaryContext = {
    row: null,
    variables,
    filtrosAplicados,
    rowsForTotals: linhasSeguras,
    pageNumber: 1,
    totalPages: 1,
    tituloRelatorio,
  };

  return (
    <div className="report-preview">
      <div className="report-sheet">
        {titleMemosVisiveis.length > 0 && (
          <div style={{ marginBottom: "12px" }}>
            {renderizarBandaAbsoluta({
              band: reportTitleBands[0] || { name: "report-title" },
              memos: titleMemosVisiveis,
              context: summaryContext,
              largura,
            })}
          </div>
        )}

        {pageHeaderBands.length > 0 &&
          renderizarBandasAbsolutasMultiplas({
            bands: pageHeaderBands.slice(0, 1),
            layout,
            context: summaryContext,
            largura,
            filterFn: (memo) => limparTexto(memo?.text) !== "",
          })}

        {colunas.length > 0 ? (
          <div className="preview-table-wrap">
            <table
              className="preview-table report-table"
              style={{ minWidth: `${largura}px` }}
            >
              <thead>
                <tr>
                  {colunas.map((coluna) => (
                    <th
                      key={coluna.key}
                      style={{
                        textAlign:
                          coluna.memo?.h_align === "haRight" ? "right" : "left",
                        backgroundColor:
                          fastReportColorToCss(coluna.headerMemo?.fill_color) ||
                          fastReportColorToCss(coluna.memo?.fill_color) ||
                          undefined,
                        color:
                          fastReportColorToCss(coluna.headerMemo?.color) ||
                          fastReportColorToCss(coluna.memo?.color) ||
                          undefined,
                        fontWeight: String(
                          coluna.headerMemo?.font_style ||
                            coluna.memo?.font_style ||
                            ""
                        ).includes("fsBold")
                          ? 700
                          : undefined,
                        width: coluna.memo?.width
                          ? `${normalizarNumeroFastReport(coluna.memo?.width)}px`
                          : undefined,
                        fontSize: coluna.memo?.font_size
                          ? `${normalizarNumeroFastReport(
                              coluna.memo?.font_size,
                              11
                            )}px`
                          : "11px",
                      }}
                    >
                      {coluna.title}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {grupos.map((grupo, grupoIndex) => {
                  const contextoGrupo = {
                    ...summaryContext,
                    rowsForTotals: grupo.rows,
                  };

                  return (
                    <Fragment key={grupo.key || grupoIndex}>
                      {groupRef?.field && groupLabelMemos.length > 0 && (
                        <tr className="report-group-row">
                          <td colSpan={Math.max(colunas.length, 1)}>
                            <div style={{ padding: "6px 2px", fontWeight: 700 }}>
                              {groupLabelMemos
                                .map((memo) =>
                                  resolverTextoMemo(memo?.text || "", {
                                    ...contextoGrupo,
                                    row: grupo.rows[0] || null,
                                  })
                                )
                                .filter(Boolean)
                                .join(" ")}
                            </div>
                          </td>
                        </tr>
                      )}

                      {groupRef?.field && groupLabelMemos.length === 0 && (
                        <tr className="report-group-row">
                          <td colSpan={Math.max(colunas.length, 1)}>
                            <div style={{ padding: "6px 2px", fontWeight: 700 }}>
                              {String(grupo.label ?? "")}
                            </div>
                          </td>
                        </tr>
                      )}

                      {grupo.rows.map((linha, indexLinha) => (
                        <tr key={`${grupo.key}-${indexLinha}`}>
                          {colunas.map((coluna) => (
                            <td
                              key={`${grupo.key}-${indexLinha}-${coluna.key}`}
                              className={
                                coluna.memo?.h_align === "haRight"
                                  ? "is-number"
                                  : ""
                              }
                              style={{
                                textAlign:
                                  coluna.memo?.h_align === "haRight"
                                    ? "right"
                                    : "left",
                                backgroundColor:
                                  fastReportColorToCss(coluna.memo?.fill_color) ||
                                  undefined,
                                color:
                                  fastReportColorToCss(coluna.memo?.color) ||
                                  undefined,
                                fontWeight: String(
                                  coluna.memo?.font_style || ""
                                ).includes("fsBold")
                                  ? 700
                                  : undefined,
                                fontStyle: String(
                                  coluna.memo?.font_style || ""
                                ).includes("fsItalic")
                                  ? "italic"
                                  : undefined,
                                width: coluna.memo?.width
                                  ? `${normalizarNumeroFastReport(
                                      coluna.memo?.width
                                    )}px`
                                  : undefined,
                                fontSize: coluna.memo?.font_size
                                  ? `${normalizarNumeroFastReport(
                                      coluna.memo?.font_size,
                                      11
                                    )}px`
                                  : "11px",
                              }}
                            >
                              {resolverTextoMemo(coluna.memo?.text || "", {
                                ...summaryContext,
                                row: linha,
                                rowsForTotals: grupo.rows,
                              })}
                            </td>
                          ))}
                        </tr>
                      ))}

                      {mainGroupFooterBand &&
                        (() => {
                          const footerMemos = ordenarPorPosicao(
                            obterMemosDaBanda(layout, mainGroupFooterBand?.name)
                          );

                          if (!footerMemos.length) return null;

                          return (
                            <tr className="report-group-total-row">
                              <td colSpan={Math.max(colunas.length, 1)}>
                                {renderizarColecaoAbsoluta({
                                  memos: footerMemos,
                                  context: {
                                    ...summaryContext,
                                    row: grupo.rows[0] || null,
                                    rowsForTotals: grupo.rows,
                                  },
                                  largura,
                                  keyPrefix: `${grupo.key}-group-footer`,
                                  minimo: 28,
                                })}
                              </td>
                            </tr>
                          );
                        })()}
                    </Fragment>
                  );
                })}
              </tbody>

              <tfoot>
                {reportSummaryBands.length > 0 ? (
                  <tr>
                    <td colSpan={Math.max(colunas.length, 1)}>
                      {reportSummaryBands.map((band) => {
                        const summaryMemos = ordenarPorPosicao(
                          obterMemosDaBanda(layout, band?.name)
                        );

                        if (!summaryMemos.length) return null;

                        return (
                          <div key={band?.name}>
                            {renderizarColecaoAbsoluta({
                              memos: summaryMemos,
                              context: summaryContext,
                              largura,
                              keyPrefix: `${band?.name}-summary`,
                              minimo: 32,
                            })}
                          </div>
                        );
                      })}
                    </td>
                  </tr>
                ) : null}
              </tfoot>
            </table>
          </div>
        ) : (
          <div className="preview-empty">
            Nenhuma banda MasterData com colunas reconhecíveis foi encontrada.
          </div>
        )}

        {pageFooterBands.length > 0 && (
          <div style={{ marginTop: "12px" }}>
            {pageFooterBands.slice(0, 1).map((band) => {
              const footerMemos = ordenarPorPosicao(
                obterMemosDaBanda(layout, band?.name)
              ).filter((memo) => !deveOcultarMemoDoTopo(memo));

              if (!footerMemos.length) return null;

              return (
                <div key={band?.name} style={{ marginBottom: "8px" }}>
                  {renderizarColecaoAbsoluta({
                    memos: footerMemos,
                    context: summaryContext,
                    largura,
                    keyPrefix: `${band?.name}-page-footer`,
                    minimo: normalizarNumeroFastReport(band?.height, 24),
                  })}
                </div>
              );
            })}
          </div>
        )}

        <div className="preview-summary no-print">
          Total de registros: <strong>{totalRegistros}</strong>
        </div>
      </div>
    </div>
  );
}