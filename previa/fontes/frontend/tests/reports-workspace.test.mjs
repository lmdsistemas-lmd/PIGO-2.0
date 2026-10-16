import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { CHARTS, DEFAULT_WHITE_LABEL, REPORT_CATEGORIES } from "../src/components/reports/reportConfig.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const app = read("src/App.jsx");
const page = read("src/pages/Reports.jsx");
const editor = read("src/components/reports/ReportEditor.jsx");
const preview = read("src/components/reports/ReportPreview.jsx");
const assistant = read("src/components/reports/ReportAssistantPanel.jsx");
const css = read("src/styles/reports-workspace.css");

test("declara páginas próprias para biblioteca, criação, edição e preview", () => {
  for (const route of ["/relatorios/:categoria", "/relatorios/:categoria/novo", "/relatorios/:categoria/:reportId/editar", "/relatorios/:categoria/:reportId/preview", "/relatorios/:categoria/preview-temporario"]) assert.match(app, new RegExp(route.replace(/[/:]/g, (value) => `\\${value}`)));
});

test("mantém quatro categorias e preferência após refresh", () => {
  assert.deepEqual(Object.keys(REPORT_CATEGORIES), ["vendas", "financeiro", "contabilidade", "outros"]);
  assert.match(page, /pigo_reports_category/);
  assert.match(page, /localStorage\.setItem/);
});

test("editor expõe dez seções e White Label", () => {
  for (const section of ["general", "source", "fields", "filters", "grouping", "totals", "sorting", "visual", "branding", "permissions"]) assert.match(editor, new RegExp(`report-${section}`));
  assert.equal(DEFAULT_WHITE_LABEL.paperSize, "A4");
  assert.match(editor, /Usar identidade da empresa/);
  assert.match(editor, /Ordem das colunas/);
});

test("preview concentra exportações e não executa automaticamente", () => {
  for (const format of ["pdf", "excel", "csv"]) assert.match(preview, new RegExp(`exportAs\\("${format}"\\)`));
  assert.match(preview, /Preview ainda não gerado/);
  assert.match(preview, /window\.print/);
  assert.deepEqual(Object.keys(CHARTS), ["table", "cards", "bar", "line", "pie", "area"]);
});

test("assistente apenas interpreta e abre o Builder", () => {
  assert.match(assistant, /interpretReportPrompt/);
  assert.match(assistant, /Nada será executado automaticamente/);
  assert.match(assistant, /Abrir no Builder/);
  assert.doesNotMatch(assistant, /previewReport/);
});

test("layout contempla desktop, tablet, mobile, impressão e temas", () => {
  assert.match(css, /grid-template-columns:minmax\(0,1fr\) 350px/);
  assert.match(css, /@media\(max-width:1200px\)/);
  assert.match(css, /@media\(max-width:800px\)/);
  assert.match(css, /@media\(max-width:520px\)/);
  assert.match(css, /@media print/);
  assert.match(css, /var\(--bg-main\)/);
});
