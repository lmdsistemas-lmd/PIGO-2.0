import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Topbar from "../components/Topbar";
import CashClosingDialog from "../components/CashClosingDialog";
import { useEmpresa } from "../context/EmpresaContext";
import { useAuth } from "../context/AuthContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import api from "../services/api";
import { money, number } from "../utils/analytics";
import { downloadBlob } from "../utils/downloadArquivo";
import "../styles/dashboard.css";
import "../styles/commercial-analytics.css";
import "../styles/operations.css";

const STATES = { pending: "Aguardando agente", processing: "Processando no ERP", applied: "Confirmado pelo ERP", rejected: "Recusado pelo ERP" };
function display(value, type) {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "currency") return money(value);
  if (type === "number") return number(value);
  if (type === "date" || type === "datetime") {
    const date = new Date(type === "date" ? String(value).slice(0, 10) + "T12:00:00" : value);
    return Number.isNaN(date.valueOf()) ? String(value) : type === "date" ? date.toLocaleDateString("pt-BR") : date.toLocaleString("pt-BR");
  }
  return String(value);
}

function Dialog({ title, close, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className="operations-dialog" onCancel={(event) => { event.preventDefault(); close(); }} aria-label={title}>
    <div className="analytics-panel-heading"><h2>{title}</h2><button className="analytics-button" onClick={close} aria-label="Fechar janela">Fechar</button></div>{children}
  </dialog>;
}

function Table({ columns, rows, action, sort, onSort }) {
  return <div className="operations-table-scroll"><table className="operations-table"><thead><tr>{columns.map((col) => <th key={col.key} aria-sort={sort?.key === col.key ? sort.direction === "asc" ? "ascending" : "descending" : undefined}>{onSort ? <button onClick={() => onSort(col.key)}>{col.label}{sort?.key === col.key ? sort.direction === "asc" ? " ↑" : " ↓" : ""}</button> : col.label}</th>)}{action && <th>Ações</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={row._id ?? index}>{columns.map((col) => <td key={col.key}>{display(row[col.key], col.type)}</td>)}{action && <td>{action(row)}</td>}</tr>)}</tbody></table>{!rows.length && <p className="analytics-empty">Nenhum registro encontrado para os filtros selecionados.</p>}</div>;
}

export default function Operations(props) {
  const { empresaAtual, loadingEmpresas } = useEmpresa();
  const company = resolveEmpresaErpId(empresaAtual);
  return <Workspace key={`${props.resource}-${company}`} company={company} loadingEmpresas={loadingEmpresas} {...props} />;
}

function Workspace({ resource, title, group, company, loadingEmpresas, ...layout }) {
  const forecast = resource === "fluxo-caixa";
  const today = new Date();
  const localDate = (day) => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
  const [filters, setFilters] = useState({ search: "", status: "", start: forecast ? localDate(new Date(today.getFullYear(), today.getMonth(), 1)) : "", end: forecast ? localDate(new Date(today.getFullYear(), today.getMonth() + 1, 0)) : "" });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState({ key: "", direction: "asc" });
  const [hidden, setHidden] = useState([]);
  const [data, setData] = useState(null);
  const [commands, setCommands] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [version, setVersion] = useState(0);
  const [detail, setDetail] = useState(null);
  const [edit, setEdit] = useState(null);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const { user } = useAuth();
  const admin = user?.auth_source === "pigo" ? user.permissions?.includes("catalogs.manage") : ["erp-admin", "admin", "administrator", "administrador", "administrador erp"].includes(String(user?.role || user?.perfil || "").toLowerCase());
  const editable = group !== "Financeiro" && admin;
  const params = { empresa_id: company, ...filters, start: filters.start || undefined, end: filters.end || undefined, page, page_size: pageSize, sort: sort.key || undefined, direction: sort.direction };

  useEffect(() => {
    if (!company || loadingEmpresas) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError("");
      try {
        const result = await api.get(`/operacoes/${resource}`, { params: { empresa_id: company, ...filters, start: filters.start || undefined, end: filters.end || undefined, page, page_size: pageSize, sort: sort.key || undefined, direction: sort.direction }, signal: controller.signal });
        if (!controller.signal.aborted) setData(result.data);
      } catch (err) { if (!controller.signal.aborted) { setData(null); setError(typeof err.message === "string" ? err.message : "Não foi possível carregar os dados."); } }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [company, loadingEmpresas, resource, filters, page, pageSize, sort, version]);

  useEffect(() => {
    if (!editable || !company) return;
    const controller = new AbortController();
    async function loadCommands() {
      try {
        const response = await api.get(`/erp/cadastros/${resource}`, { params: { empresa_id: company }, signal: controller.signal });
        if (!controller.signal.aborted) setCommands(response.data);
      } catch (err) { if (!controller.signal.aborted) setError(typeof err.message === "string" ? err.message : "Falha ao consultar solicitações ao ERP."); }
    }
    loadCommands();
    const interval = setInterval(loadCommands, 10000);
    return () => { controller.abort(); clearInterval(interval); };
  }, [editable, company, resource, version]);

  function applyFilters(event) { event.preventDefault(); setPage(1); setFilters(draftFilters); }
  async function openDetail(row) {
    setError("");
    try { const response = await api.get(`/operacoes/${resource}/${encodeURIComponent(row._id)}`, { params: { empresa_id: company } }); setDetail({ ...response.data, id: row._id }); }
    catch (err) { setError(String(err.message)); }
  }
  function beginEdit(record = null, id = null) {
    const fields = commands?.fields || {};
    setEdit({ id, requestId: crypto.randomUUID(), original: record || {}, values: Object.fromEntries(Object.keys(fields).map((key) => [key, record?.[key] ?? ""])), error: "" });
    setDetail(null);
  }
  async function save(event) {
    event.preventDefault(); setSaving(true);
    const changed = Object.entries(edit.values).filter(([key, value]) => edit.id ? String(value) !== String(edit.original[key] ?? "") : value !== "");
    if (!changed.length) { setEdit({ ...edit, error: "Altere pelo menos um campo." }); setSaving(false); return; }
    try {
      await api.post(`/erp/cadastros/${resource}`, { request_id: edit.requestId, empresa_id: company,
        action: edit.id ? "update" : "create", record_id: edit.id, payload: Object.fromEntries(changed),
        expected: edit.id ? Object.fromEntries(changed.map(([key]) => [key, edit.original[key] ?? null])) : {} });
      setEdit(null); setNotice("Solicitação enviada. A alteração só será confirmada após a gravação no ERP pelo agente."); setVersion((value) => value + 1);
    } catch (err) { setEdit({ ...edit, error: typeof err.message === "string" ? err.message : "Não foi possível enviar a solicitação." }); }
    finally { setSaving(false); }
  }
  async function exportData(format) {
    setExporting(true); setError("");
    try { const response = await api.get(`/operacoes/${resource}/export`, { params: { ...params, format }, responseType: "blob" }); downloadBlob(response.data, `${resource}.${format === "excel" ? "xlsx" : "csv"}`); }
    catch (err) { let message = "Não foi possível exportar a consulta."; if (err.response?.data instanceof Blob) { try { message = JSON.parse(await err.response.data.text()).detail || message; } catch { /* Keep readable fallback. */ } } else if (typeof err.message === "string") message = err.message; setError(message); }
    finally { setExporting(false); }
  }
  const columns = data?.columns?.filter((col) => col.available && !hidden.includes(col.key)) || [];
  const summaryColumns = data?.columns?.filter((col) => Object.hasOwn(data.summary || {}, col.key)) || [];
  const syncedAt = data?.last_sync_at ? new Date(data.last_sync_at) : null;
  const syncLabel = syncedAt && !Number.isNaN(syncedAt.valueOf())
    ? `${syncedAt.toLocaleDateString("pt-BR")} às ${syncedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`
    : null;

  return <div className="dashboard-page commercial-page operations-page">
    <Topbar titulo={title} caminho={`${group === "Financeiro" ? "Financeiro" : `Cadastros / ${group}`} / ${title}`} {...layout} />
    <header className="analytics-page-heading"><div><span className="analytics-eyebrow">{group === "Financeiro" ? "CONTROLE FINANCEIRO" : `CADASTROS · ${group.toUpperCase()}`}</span><h1>{title}</h1><p>{forecast ? "Previsão das entradas e saídas por vencimento dos títulos em aberto." : "Consulte os dados do ERP na empresa selecionada."}</p></div><div className="operations-actions">{syncLabel && <p className="operations-updated" title="Última sincronização deste cadastro com o ERP">Última atualização: <time dateTime={syncedAt.toISOString()}>{syncLabel}</time></p>}<button className="analytics-button" onClick={() => setVersion((v) => v + 1)} disabled={loading}>Atualizar</button>{editable && commands && <button className="analytics-button primary" onClick={() => beginEdit()} disabled={!company}>Novo cadastro</button>}</div></header>
    {!company && <p className="analytics-notice">{loadingEmpresas ? "Carregando empresas…" : "Selecione uma empresa com dados sincronizados."}</p>}
    {notice && <p className="analytics-notice" role="status">{notice}</p>}
    {error && <p className="analytics-notice analytics-error" role="alert">{error}</p>}
    {company && <form className="analytics-panel operations-filters" onSubmit={applyFilters}>
      {!forecast && <label>Pesquisar<input type="search" placeholder="Código, nome ou descrição" value={draftFilters.search} maxLength={200} onChange={(e) => setDraftFilters({ ...draftFilters, search: e.target.value })} /></label>}
      {!!data?.statuses?.length && <label>Status<select value={draftFilters.status} onChange={(e) => setDraftFilters({ ...draftFilters, status: e.target.value })}><option value="">Todos</option>{data.statuses.map((value) => <option key={value}>{value}</option>)}</select></label>}
      {(forecast || data?.has_period) && <><label>Data inicial<input type="date" required={forecast || !!draftFilters.end} value={draftFilters.start} onChange={(e) => setDraftFilters({ ...draftFilters, start: e.target.value })} /></label><label>Data final<input type="date" required={forecast || !!draftFilters.start} min={draftFilters.start} value={draftFilters.end} onChange={(e) => setDraftFilters({ ...draftFilters, end: e.target.value })} /></label></>}
      <button className="analytics-button primary" disabled={loading}>Aplicar filtros</button>
    </form>}
    {loading && <p className="analytics-notice" role="status">Carregando consulta…</p>}
    {data && !data.available && <section className="analytics-panel"><h2>Sincronização necessária</h2><p>{forecast ? "O agente ainda não enviou os saldos em aberto necessários para calcular esta previsão. Valores originais dos títulos não substituem o saldo após baixas parciais." : data.message}</p>{forecast && <p>Consultas pendentes: {data.missing.join(", ")}.</p>}</section>}
    {data?.available && forecast && <>
      <p className="analytics-notice">Previsão por vencimento: considera somente títulos em aberto no intervalo. O acumulado parte de zero; saldo bancário inicial e movimentos já realizados ainda não estão incluídos.</p>
      <div className="analytics-kpis">{[["entradas", "Entradas previstas"], ["saidas", "Saídas previstas"], ["resultado", "Resultado previsto"]].map(([key, label], index) => <article className={`analytics-kpi tone-${index}`} key={key}><span>{label}</span><strong>{money(data.summary[key])}</strong></article>)}</div>
      <section className="analytics-panel"><h2>Resultado acumulado previsto</h2><div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="dia" tickFormatter={(value) => display(value, "date")} /><YAxis tickFormatter={number} /><Tooltip formatter={money} /><Area isAnimationActive={false} type="monotone" dataKey="acumulado" name="Acumulado previsto" stroke="#2563eb" fill="#2563eb33" /></AreaChart></ResponsiveContainer></div></section>
      <section className="analytics-panel"><h2>Previsão diária</h2><Table columns={[{ key: "dia", label: "Data", type: "date" }, ...[["entradas", "Entradas"], ["saidas", "Saídas"], ["resultado", "Resultado"], ["acumulado", "Acumulado"]].map(([key, label]) => ({ key, label, type: "currency" }))]} rows={data.rows} /></section>
    </>}
    {data?.available && !forecast && <>
      {!!summaryColumns.length && <div className="analytics-kpis">{summaryColumns.map((col, index) => <article className={`analytics-kpi tone-${index % 4}`} key={col.key}><span>{col.label} · total filtrado</span><strong>{display(data.summary[col.key], "currency")}</strong></article>)}</div>}
      <section className="analytics-panel"><div className="analytics-panel-heading"><h2>{number(data.total)} registros</h2><div className="operations-actions"><details className="operations-columns"><summary>Colunas</summary><div>{data.columns.filter((col) => col.available).map((col) => <label key={col.key}><input type="checkbox" checked={!hidden.includes(col.key)} onChange={() => setHidden((previous) => previous.includes(col.key) ? previous.filter((key) => key !== col.key) : [...previous, col.key])} />{col.label}</label>)}</div></details><button className="analytics-button" disabled={exporting} onClick={() => exportData("csv")}>Exportar CSV</button><button className="analytics-button" disabled={exporting} onClick={() => exportData("excel")}>Exportar Excel</button></div></div>
        <Table columns={columns} rows={data.rows} sort={sort} onSort={(key) => { setSort({ key, direction: sort.key === key && sort.direction === "asc" ? "desc" : "asc" }); setPage(1); }} action={(row) => <button className="analytics-button" onClick={() => openDetail(row)}>Detalhes</button>} />
        <div className="operations-pagination"><label>Por página<select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>{[25, 50, 100].map((size) => <option key={size}>{size}</option>)}</select></label><span>Página {page} de {Math.max(1, Math.ceil(data.total / pageSize))}</span><button className="analytics-button" disabled={page === 1 || loading} onClick={() => setPage((p) => p - 1)}>Anterior</button><button className="analytics-button" disabled={page * pageSize >= data.total || loading} onClick={() => setPage((p) => p + 1)}>Próxima</button></div>
      </section>
    </>}
    {commands && <section className="analytics-panel"><div className="analytics-panel-heading"><h2>Solicitações ao ERP</h2><span className={`operations-state ${commands.agent_ready ? "applied" : "pending"}`}>{commands.agent_ready ? "Agente de gravação conectado" : "Aguardando configuração ou conexão do agente"}</span></div><p>O agente grava no ERP. Depois, a sincronização atualiza esta consulta.</p><Table columns={[{ key: "created_at", label: "Solicitação", type: "datetime" }, { key: "operation", label: "Operação" }, { key: "code", label: "Código ERP" }, { key: "state", label: "Situação" }, { key: "message", label: "Retorno do ERP" }]} rows={commands.commands.map((cmd) => ({ ...cmd, operation: cmd.action === "create" ? "Novo cadastro" : "Edição", code: cmd.result?.record_id || cmd.record_id, state: STATES[cmd.status], message: cmd.result?.message }))} /></section>}
    {detail && resource === "fechamentos" && <CashClosingDialog detail={detail} company={company} close={() => setDetail(null)} />}
    {detail && resource !== "fechamentos" && <Dialog title={`${title} · ${detail.id}`} close={() => setDetail(null)}><dl className="operations-record">{data.columns.map((col) => <div key={col.key}><dt>{col.label}</dt><dd>{display(detail.record[col.key], col.type)}</dd></div>)}</dl>
      {detail.stock_positions && <><h3>Estoque por local e variação</h3><p>As posições são apresentadas separadamente. A regra do estoque total do ERP ainda precisa ser confirmada.</p><Table columns={[{ key: "local", label: "Local (código)" }, { key: "variacao", label: "Variação (código)" }, { key: "quantidade", label: "Quantidade", type: "number" }]} rows={detail.stock_positions} />{detail.stock_positions_truncated && <p>Exibindo as primeiras 10.000 posições.</p>}</>}
      {editable && commands && <button className="analytics-button primary" onClick={() => beginEdit(detail.record, detail.id)}>Editar no ERP</button>}
    </Dialog>}
    {edit && <Dialog title={edit.id ? `Editar no ERP · ${edit.id}` : `Novo cadastro · ${title}`} close={() => { if (!saving) setEdit(null); }}><p>A solicitação será gravada no ERP pelo agente. As regras e os campos obrigatórios do ERP serão validados na gravação.</p>{!commands.agent_ready && <p className="analytics-notice">O agente de gravação ainda não está disponível. A solicitação ficará aguardando sua configuração ou conexão.</p>}<form onSubmit={save}>
      <div className="operations-edit-grid">{Object.entries(commands.fields).map(([key, type]) => <label key={key}>{data?.columns?.find((col) => col.key === key)?.label || key}<input required={key === "nome"} type={type === "number" ? "number" : key === "email" ? "email" : "text"} min={type === "number" ? "0" : undefined} step={type === "number" ? "0.0001" : undefined} maxLength={250} disabled={saving} value={edit.values[key]} onChange={(e) => setEdit({ ...edit, requestId: crypto.randomUUID(), values: { ...edit.values, [key]: e.target.value } })} /></label>)}</div>
      {edit.error && <p className="analytics-notice analytics-error" role="alert">{edit.error}</p>}<button className="analytics-button primary" disabled={saving}>{saving ? "Enviando…" : "Enviar ao agente"}</button>
    </form></Dialog>}
  </div>;
}
