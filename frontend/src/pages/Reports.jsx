import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Topbar from "../components/Topbar";
import ReportAssistantPanel from "../components/reports/ReportAssistantPanel";
import ReportEditor from "../components/reports/ReportEditor";
import ReportPreview from "../components/reports/ReportPreview";
import ReportsCategoryTabs from "../components/reports/ReportsCategoryTabs";
import ReportsLibrary from "../components/reports/ReportsLibrary";
import { CATEGORY_BY_KEY, DEFAULT_WHITE_LABEL, EMPTY_FORM, REPORT_CATEGORIES } from "../components/reports/reportConfig";
import { useEmpresa } from "../context/EmpresaContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import { createReport, deleteReport, duplicateReport, exportReport, getFilterOptions, getReadyTemplates, getReportCatalog, listReports, previewReport, updateReport } from "../services/reportsService";
import "../styles/reports-workspace.css";

const EMPTY_CATEGORY_META = { label: "Relatórios", sources: {}, planned_sources: [] };

function routeMode(pathname) {
  if (pathname.endsWith("/novo") || pathname.endsWith("/editar")) return "editor";
  if (pathname.endsWith("/preview") || pathname.endsWith("/preview-temporario")) return "preview";
  return "library";
}

export default function Reports(props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { categoria, reportId } = useParams();
  const { empresaAtual } = useEmpresa();
  const companyId = resolveEmpresaErpId(empresaAtual);
  const mode = routeMode(location.pathname);
  const categorySlug = REPORT_CATEGORIES[categoria] ? categoria : "vendas";
  const category = REPORT_CATEGORIES[categorySlug];
  const [catalog, setCatalog] = useState({});
  const [reports, setReports] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [whiteLabel, setWhiteLabel] = useState(DEFAULT_WHITE_LABEL);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [assistantDrawer, setAssistantDrawer] = useState(false);
  const [favorites, setFavorites] = useState(() => JSON.parse(localStorage.getItem("pigo_report_favorites") || "[]"));
  const categoryMeta = catalog[category.key] || EMPTY_CATEGORY_META;

  useEffect(() => {
    if (location.pathname === "/relatorios") {
      navigate(`/relatorios/${localStorage.getItem("pigo_reports_category") || "vendas"}`, { replace: true });
      return;
    }
    if (categoria && !REPORT_CATEGORIES[categoria]) {
      navigate("/relatorios/vendas", { replace: true });
      return;
    }
    localStorage.setItem("pigo_reports_category", categorySlug);
  }, [categoria, categorySlug, location.pathname, navigate]);

  useEffect(() => { getReportCatalog().then(setCatalog).catch((err) => setError(err.message)); }, []);

  const reload = useCallback(async () => {
    setLoading(true); setError("");
    try { const [saved, ready] = await Promise.all([listReports(category.key), getReadyTemplates(category.key)]); setReports(saved); setTemplates(ready); }
    catch (err) { setError(err.message || "Não foi possível carregar os relatórios."); }
    finally { setLoading(false); }
  }, [category.key]);

  useEffect(() => { reload(); }, [reload]);

  useEffect(() => {
    if (mode !== "editor") return;
    const suggested = location.state?.assistantDefinition || location.state?.template?.definition || location.state?.definition;
    if (suggested) {
      const prompt = location.state?.assistantPrompt || location.state?.template?.description || location.state?.description || "";
      setForm({ ...EMPTY_FORM, name: location.state?.template?.name || location.state?.title || (prompt ? `Relatório assistido — ${prompt.slice(0, 70)}` : "Novo relatório"), description: prompt, ...suggested });
      if (location.state?.whiteLabel) setWhiteLabel(location.state.whiteLabel);
      return;
    }
    if (reportId) {
      const report = reports.find((item) => item.id === reportId);
      if (report) setForm({ ...EMPTY_FORM, name: report.name, description: report.description, permissions: report.permissions, ...report.definition });
      return;
    }
    const firstSource = Object.keys(categoryMeta.sources || {})[0] || "";
    setForm({ ...EMPTY_FORM, source: firstSource });
  }, [mode, reportId, reports, categoryMeta.sources, location.state]);

  useEffect(() => {
    if (mode !== "preview") return;
    setPreview(location.state?.preview || null);
    setWhiteLabel(location.state?.whiteLabel || DEFAULT_WHITE_LABEL);
    const definition = location.state?.definition;
    if (definition) setForm((current) => ({ ...current, ...definition, name: location.state?.title || current.name }));
    else if (reportId) {
      const report = reports.find((item) => item.id === reportId);
      if (report) setForm({ ...EMPTY_FORM, name: report.name, description: report.description, permissions: report.permissions, ...report.definition });
    }
  }, [mode, reportId, reports, location.state]);

  const definition = useCallback(() => ({ category: category.key, source: form.source, fields: form.fields, filters: form.filters, group_by: form.group_by, order_by: form.order_by, totals: form.totals, chart: form.chart }), [category.key, form]);

  async function generatePreview(def = definition(), options = {}) {
    if (!companyId) { setPreviewError("Selecione uma empresa ERP antes de gerar o preview."); return null; }
    setPreviewLoading(true); setPreviewError("");
    try {
      const data = await previewReport({ definition: def, empresa_id: Number(companyId), limit: 50 });
      setPreview(data);
      if (options.navigate !== false) navigate(options.path || `/relatorios/${categorySlug}/preview-temporario`, { state: { definition: def, preview: data, title: options.title || form.name, whiteLabel, editorPath: options.editorPath } });
      return data;
    } catch (err) { setPreviewError(err.message); return null; }
    finally { setPreviewLoading(false); }
  }

  async function save(event) {
    event.preventDefault(); setSaving(true); setError("");
    const payload = { name: form.name, description: form.description, permissions: form.permissions, definition: definition() };
    try { if (reportId) await updateReport(reportId, payload); else await createReport(payload); await reload(); navigate(`/relatorios/${categorySlug}`); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  function openAssistantDefinition(suggested, prompt) {
    const target = CATEGORY_BY_KEY[suggested.category]?.slug || categorySlug;
    navigate(`/relatorios/${target}/novo?assistant=true`, { state: { assistantDefinition: suggested, assistantPrompt: prompt } });
    setAssistantDrawer(false);
  }

  async function runSaved(report) {
    await generatePreview(report.definition, { path: `/relatorios/${categorySlug}/${report.id}/preview`, title: report.name, editorPath: `/relatorios/${categorySlug}/${report.id}/editar` });
  }

  async function doExport(format) { await exportReport({ definition: definition(), empresa_id: Number(companyId), format, template_id: reportId || null }); }
  function toggleFavorite(id) { const next = favorites.includes(id) ? favorites.filter((item) => item !== id) : [...favorites, id]; setFavorites(next); localStorage.setItem("pigo_report_favorites", JSON.stringify(next)); }
  const previewTitle = location.state?.title || form.name || "Pré-visualização";
  const editorPath = location.state?.editorPath || (reportId ? `/relatorios/${categorySlug}/${reportId}/editar` : `/relatorios/${categorySlug}/novo`);
  const topbarTitle = mode === "library" ? "Relatórios" : mode === "editor" ? "Editor de Relatório" : "Preview do Relatório";
  const layoutClass = useMemo(() => `reports-shell mode-${mode}`, [mode]);

  return <div className={layoutClass}>
    <Topbar titulo={topbarTitle} subtitulo="Crie, personalize e execute análises com segurança." caminho={`Relatórios / ${category.label}`} {...props} />
    {mode !== "library" && <div className="reports-page-tools"><button className="reports-button" onClick={() => setAssistantDrawer(true)}>Assistente</button></div>}
    <ReportsCategoryTabs />
    {mode === "library" && <div className="reports-library-layout"><ReportsLibrary category={category} categoryMeta={categoryMeta} reports={reports} templates={templates} loading={loading} error={error} favorites={favorites} onNew={() => navigate(`/relatorios/${categorySlug}/novo`)} onUseTemplate={(template) => navigate(`/relatorios/${categorySlug}/novo`, { state: { template } })} onOpen={(report) => navigate(`/relatorios/${categorySlug}/${report.id}/editar`)} onRun={runSaved} onDuplicate={async (report) => { await duplicateReport(report.id); reload(); }} onDelete={async (report) => { if (confirm(`Excluir “${report.name}”?`)) { await deleteReport(report.id); reload(); } }} onFavorite={toggleFavorite} onRetry={reload} /><ReportAssistantPanel companyId={companyId} onApply={openAssistantDefinition} /></div>}
    {mode === "editor" && <ReportEditor category={category} categoryMeta={categoryMeta} form={form} setForm={setForm} whiteLabel={whiteLabel} setWhiteLabel={setWhiteLabel} saving={saving} error={error} onBack={() => navigate(`/relatorios/${categorySlug}`)} onSave={save} onPreview={() => generatePreview(definition(), { editorPath: location.pathname })} onAssistant={() => setAssistantDrawer(true)} getOptions={(field) => getFilterOptions(category.key, form.source, field, companyId)} />}
    {mode === "preview" && <ReportPreview title={previewTitle} preview={preview} definition={definition()} whiteLabel={whiteLabel} loading={previewLoading} error={previewError} onRefresh={() => generatePreview(definition(), { navigate: false })} onEdit={() => navigate(editorPath, { state: { definition: definition(), whiteLabel, title: previewTitle, description: form.description } })} onBack={() => navigate(`/relatorios/${categorySlug}`)} onExport={doExport} />}
    {assistantDrawer && <div className="reports-assistant-drawer"><button className="drawer-backdrop" onClick={() => setAssistantDrawer(false)} aria-label="Fechar" /><ReportAssistantPanel compact companyId={companyId} onApply={openAssistantDefinition} onClose={() => setAssistantDrawer(false)} /></div>}
  </div>;
}
