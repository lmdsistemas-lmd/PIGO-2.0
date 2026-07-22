import { useCallback, useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { useEmpresa } from "../context/EmpresaContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import {
  createReport, deleteReport, duplicateReport, exportReport,
  getFilterOptions, getReadyTemplates, getReportCatalog, listReports, previewReport, updateReport,
} from "../services/reportsService";
import "../styles/report-builder.css";
import "../styles/report-builder-controls.css";

const CATEGORY_ORDER = ["sales", "finance", "accounting", "other"];
const CHARTS = { table: "Tabela", cards: "Cards", bar: "Barras", line: "Linha", pie: "Pizza", area: "Área" };
const ROLES = [["all", "Todos"], ["administrator", "Administrador"], ["supervisor", "Supervisor"], ["finance", "Financeiro"], ["sales", "Vendas"], ["user", "Usuário"]];
const EMPTY_FORM = { name: "", description: "", source: "", fields: [], filters: [], group_by: [], order_by: [], totals: [], chart: "table", permissions: ["all"] };

function ReportChart({ preview }) {
  if (!preview || preview.chart === "table" || !preview.rows.length) return null;
  if (preview.chart === "cards") return <div className="report-card-chart">{preview.columns.slice(0, 4).map((column) => <article key={column.key}><span>{column.label}</span><strong>{String(preview.rows[0][column.key] ?? "-")}</strong></article>)}</div>;
  const labelKey = preview.columns[0]?.key;
  const valueKey = preview.columns.find((column) => preview.rows.some((row) => Number.isFinite(Number(row[column.key]))))?.key;
  if (!labelKey || !valueKey) return null;
  const values = preview.rows.slice(0, 12).map((row) => ({ label: String(row[labelKey] ?? ""), value: Number(row[valueKey] || 0) }));
  const maximum = Math.max(...values.map((item) => Math.abs(item.value)), 1);
  return <div className={`report-visual report-visual--${preview.chart}`}>{values.map((item, index) => <div className="report-visual-item" key={`${item.label}-${index}`} title={`${item.label}: ${item.value}`}><div style={{ height: `${Math.max(8, Math.abs(item.value) / maximum * 160)}px` }} /><span>{item.label}</span></div>)}</div>;
}

function formatReportValue(value, type) {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "currency") return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
  if (type === "number") return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(Number(value));
  if (type === "date") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString("pt-BR");
  }
  return String(value);
}

export default function Reports(props) {
  const { empresaAtual } = useEmpresa();
  const empresaId = resolveEmpresaErpId(empresaAtual);
  const [category, setCategory] = useState("sales");
  const [catalog, setCatalog] = useState({});
  const [reports, setReports] = useState([]);
  const [readyTemplates, setReadyTemplates] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState("");
  const [builderOpen, setBuilderOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [draftFilter, setDraftFilter] = useState({ field: "", operator: "eq", value: "" });
  const [draftTotal, setDraftTotal] = useState({ field: "", aggregation: "sum" });
  const [filterOptions, setFilterOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const categoryMeta = catalog[category] || { label: "Relatórios", sources: {}, planned_sources: [] };
  const sourceMeta = categoryMeta.sources?.[form.source];
  const availableFields = sourceMeta ? Object.entries(sourceMeta.fields) : [];

  const reload = useCallback(async (selectedCategory = category) => {
    setLoading(true); setError("");
    try {
      const [saved, ready] = await Promise.all([listReports(selectedCategory), getReadyTemplates(selectedCategory)]);
      setReports(saved); setReadyTemplates(ready);
    }
    catch (err) { setError(err.message || "Não foi possível carregar os relatórios."); }
    finally { setLoading(false); }
  }, [category]);

  useEffect(() => {
    getReportCatalog().then(setCatalog).catch((err) => setError(err.message));
  }, []);
  useEffect(() => { reload(category); }, [category, reload]);

  function newReport() {
    const firstSource = Object.keys(categoryMeta.sources || {})[0] || "";
    setEditingId(""); setForm({ ...EMPTY_FORM, source: firstSource }); setPreview(null); setBuilderOpen(true);
  }

  function editReport(report) {
    setEditingId(report.id);
    setForm({ name: report.name, description: report.description, permissions: report.permissions, ...report.definition });
    setPreview(null); setBuilderOpen(true);
  }

  function applyReadyTemplate(template) {
    setCategory(template.definition.category);
    setEditingId("");
    setForm({ ...EMPTY_FORM, name: template.name, description: template.description, ...template.definition });
    setPreview(null); setBuilderOpen(true);
  }

  async function selectFilterField(field) {
    const operator = sourceMeta.filters[field]?.operators?.[0] || "eq";
    setDraftFilter({ field, operator, value: "" }); setFilterOptions([]);
    if (field && field !== "period" && empresaId) {
      try { setFilterOptions(await getFilterOptions(category, form.source, field, empresaId)); }
      catch { setFilterOptions([]); }
    }
  }

  function definition() {
    return { category, source: form.source, fields: form.fields, filters: form.filters, group_by: form.group_by, order_by: form.order_by, totals: form.totals, chart: form.chart };
  }

  async function save(event) {
    event.preventDefault(); setError("");
    const payload = { name: form.name, description: form.description, permissions: form.permissions, definition: definition() };
    try {
      if (editingId) await updateReport(editingId, payload); else await createReport(payload);
      setBuilderOpen(false); await reload();
    } catch (err) { setError(err.message); }
  }

  async function run(def = definition()) {
    if (!empresaId) return setError("Selecione uma empresa ERP antes de executar o relatório.");
    setLoading(true); setError("");
    try { setPreview(await previewReport({ definition: def, empresa_id: Number(empresaId), limit: 50 })); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  function toggleField(key) {
    setForm((current) => ({ ...current, fields: current.fields.includes(key) ? current.fields.filter((item) => item !== key) : [...current.fields, key] }));
  }

  function addFilter() {
    if (!draftFilter.field || !draftFilter.value) return;
    const value = ["between", "in"].includes(draftFilter.operator) ? draftFilter.value.split(",").map((item) => item.trim()).filter(Boolean) : draftFilter.value;
    setForm((current) => ({ ...current, filters: [...current.filters, { ...draftFilter, value }] }));
    setDraftFilter({ field: "", operator: "eq", value: "" });
  }

  function addTotal() {
    if (!draftTotal.field) return;
    setForm((current) => ({ ...current, totals: [...current.totals.filter((item) => item.field !== draftTotal.field), draftTotal] }));
  }

  const hasSources = Object.keys(categoryMeta.sources || {}).length > 0;
  const previewTitle = useMemo(() => editingId ? form.name : "Pré-visualização", [editingId, form.name]);

  return <div className="reports-engine-page">
    <Topbar titulo="Relatórios" caminho="Relatórios / Construtor White Label" {...props} />
    <main className="report-workspace">
      <header className="report-hero">
        <div><span className="report-eyebrow">Report Engine</span><h1>Relatórios que acompanham o seu negócio</h1><p>Escolha os dados, organize a visão e gere resultados sem escrever código.</p></div>
        <button className="report-primary" onClick={newReport} disabled={!hasSources}>+ Novo relatório</button>
      </header>

      <nav className="report-tabs" aria-label="Categorias">
        {CATEGORY_ORDER.map((key) => <button key={key} className={category === key ? "active" : ""} onClick={() => { setCategory(key); setBuilderOpen(false); setPreview(null); }}>{catalog[key]?.label || key}</button>)}
      </nav>

      {error && <div className="report-alert" role="alert">{error}<button onClick={() => reload()}>Tentar novamente</button></div>}

      <section className="report-catalog-header"><div><h2>{categoryMeta.label}</h2><p>{hasSources ? "Modelos criados pela sua equipe e fontes disponíveis." : "Catálogo preparado para a próxima conexão de dados."}</p></div><span>{reports.length} relatório(s)</span></section>

      {readyTemplates.length > 0 && <section><div className="report-catalog-header"><div><h2>Comece com um modelo</h2><p>Estruturas prontas que podem ser ajustadas antes de salvar.</p></div></div><div className="ready-template-strip">{readyTemplates.map((template) => <button key={template.key} onClick={() => applyReadyTemplate(template)}><span>{categoryMeta.sources?.[template.definition.source]?.label}</span><strong>{template.name}</strong><small>{template.description}</small></button>)}</div></section>}

      {loading && !preview ? <div className="report-empty">Carregando catálogo...</div> : reports.length ? <div className="report-grid">
        {reports.map((report) => <article className="report-card" key={report.id}><span>{categoryMeta.sources?.[report.source]?.label || report.source}</span><h3>{report.name}</h3><p>{report.description || "Sem descrição"}</p><div className="report-actions"><button onClick={() => run(report.definition)}>Executar</button><button onClick={() => editReport(report)}>Editar</button><button onClick={async () => { await duplicateReport(report.id); reload(); }}>Duplicar</button><button onClick={async () => { if (confirm("Excluir este relatório?")) { await deleteReport(report.id); reload(); } }}>Excluir</button></div></article>)}
      </div> : <div className="report-empty"><strong>Nenhum relatório criado em {categoryMeta.label}.</strong><p>{hasSources ? "Use o construtor para criar o primeiro modelo." : `Fontes previstas: ${categoryMeta.planned_sources.join(", ")}.`}</p></div>}

      {builderOpen && <form className="report-builder" onSubmit={save}>
        <div className="builder-title"><div><span>Construtor visual</span><h2>{editingId ? "Editar relatório" : "Novo relatório"}</h2></div><button type="button" onClick={() => setBuilderOpen(false)}>Fechar</button></div>
        <div className="builder-grid">
          <label>Nome<input required minLength="3" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Fonte<select required value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value, fields: [], filters: [], group_by: [], totals: [] })}><option value="">Selecione</option>{Object.entries(categoryMeta.sources).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label>
          <label className="wide">Descrição<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        </div>
        {sourceMeta && <><section className="builder-section"><h3>Campos</h3><p>Selecione o que será apresentado.</p><div className="field-picker">{availableFields.map(([key, field]) => <label key={key} className={form.fields.includes(key) ? "selected" : ""}><input type="checkbox" checked={form.fields.includes(key)} onChange={() => toggleField(key)} /><span>{field.label}</span><small>{field.type}</small></label>)}</div></section>
        <section className="builder-section builder-options">
          <label>Visualização<select value={form.chart} onChange={(e) => setForm({ ...form, chart: e.target.value })}>{Object.entries(CHARTS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label>Agrupar por<select value={form.group_by[0] || ""} onChange={(e) => setForm({ ...form, group_by: e.target.value ? [e.target.value] : [] })}><option value="">Sem agrupamento</option>{sourceMeta.groupings.map((key) => <option key={key} value={key}>{sourceMeta.fields[key]?.label || key}</option>)}</select></label>
          <label>Ordenar por<select value={form.order_by[0]?.field || ""} onChange={(e) => setForm({ ...form, order_by: e.target.value ? [{ field: e.target.value, direction: form.order_by[0]?.direction || "asc" }] : [] })}><option value="">Sem ordenação</option>{form.fields.map((key) => <option key={key} value={key}>{sourceMeta.fields[key]?.label || key}</option>)}</select></label>
          <label>Direção<select value={form.order_by[0]?.direction || "asc"} onChange={(e) => setForm({ ...form, order_by: form.order_by.length ? [{ ...form.order_by[0], direction: e.target.value }] : [] })}><option value="asc">Ascendente</option><option value="desc">Descendente</option></select></label>
        </section>
        <section className="builder-section"><h3>Filtros</h3><div className="builder-inline">
          <select value={draftFilter.field} onChange={(e) => selectFilterField(e.target.value)}><option value="">Selecione</option>{Object.entries(sourceMeta.filters).filter(([key]) => key !== "company").map(([key, meta]) => <option key={key} value={key}>{meta.label}</option>)}</select>
          <select value={draftFilter.operator} onChange={(e) => setDraftFilter({ ...draftFilter, operator: e.target.value })}>{(sourceMeta.filters[draftFilter.field]?.operators || ["eq"]).map((operator) => <option key={operator}>{operator}</option>)}</select>
          {filterOptions.length ? <select value={draftFilter.value} onChange={(e) => setDraftFilter({ ...draftFilter, value: e.target.value })}><option value="">Escolha uma opção</option>{filterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input placeholder={draftFilter.operator === "between" ? "início, fim" : "valor"} value={draftFilter.value} onChange={(e) => setDraftFilter({ ...draftFilter, value: e.target.value })} />}<button type="button" onClick={addFilter}>Adicionar</button>
        </div><div className="builder-chips">{form.filters.map((item, index) => <button type="button" key={`${item.field}-${index}`} onClick={() => setForm({ ...form, filters: form.filters.filter((_, position) => position !== index) })}>{sourceMeta.filters[item.field]?.label}: {String(item.value)} ×</button>)}</div></section>
        <section className="builder-section"><h3>Totais</h3><div className="builder-inline">
          <select value={draftTotal.field} onChange={(e) => setDraftTotal({ field: e.target.value, aggregation: sourceMeta.fields[e.target.value]?.aggregations?.[0] || "sum" })}><option value="">Selecione</option>{availableFields.map(([key, field]) => <option key={key} value={key}>{field.label}</option>)}</select>
          <select value={draftTotal.aggregation} onChange={(e) => setDraftTotal({ ...draftTotal, aggregation: e.target.value })}>{(sourceMeta.fields[draftTotal.field]?.aggregations || ["sum"]).map((aggregation) => <option key={aggregation}>{aggregation}</option>)}</select><button type="button" onClick={addTotal}>Adicionar</button>
        </div><div className="builder-chips">{form.totals.map((item) => <button type="button" key={item.field} onClick={() => setForm({ ...form, totals: form.totals.filter((total) => total.field !== item.field) })}>{sourceMeta.fields[item.field]?.label} ({item.aggregation}) ×</button>)}</div></section>
        <section className="builder-section"><h3>Quem pode acessar</h3><div className="field-picker">{ROLES.map(([key, label]) => <label className={form.permissions.includes(key) ? "selected" : ""} key={key}><input type="checkbox" checked={form.permissions.includes(key)} onChange={() => setForm({ ...form, permissions: form.permissions.includes(key) ? form.permissions.filter((role) => role !== key) : [...form.permissions.filter((role) => key === "all" ? false : role !== "all"), key] })} /><span>{label}</span></label>)}</div></section></>}
        <footer className="builder-footer"><button type="button" onClick={() => run()}>Visualizar 50 registros</button><button className="report-primary" type="submit" disabled={!form.fields.length}>Salvar relatório</button></footer>
      </form>}

      {preview && <section className="report-preview-panel"><header><div><span>{preview.cache === "hit" ? "Cache" : `${preview.query_time_ms} ms`}</span><h2>{previewTitle}</h2><p>{preview.row_count} registro(s) encontrados</p></div><div>{["pdf", "excel", "csv"].map((format) => <button key={format} onClick={() => exportReport({ definition: editingId ? reports.find((r) => r.id === editingId)?.definition || definition() : definition(), empresa_id: Number(empresaId), format, template_id: editingId || null })}>{format.toUpperCase()}</button>)}<button onClick={() => window.print()}>Imprimir</button></div></header><ReportChart preview={preview} />{preview.rows.length ? <div className="report-table-wrap"><table><thead><tr>{preview.columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.key}>{formatReportValue(row[column.key], column.type)}</td>)}</tr>)}</tbody></table></div> : <div className="report-empty">Nenhum registro encontrado para os filtros selecionados.</div>}</section>}
    </main>
  </div>;
}
