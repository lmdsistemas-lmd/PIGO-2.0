import DashboardWorkspace, { DashboardBlock } from "../components/DashboardWorkspace";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Topbar from "../components/Topbar";
import { useEmpresa } from "../context/EmpresaContext";
import { useAuth } from "../context/AuthContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import api from "../services/api";
import { money, percent } from "../utils/analytics";
import "../styles/dashboard.css";
import "../styles/commercial-analytics.css";

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function SalesGoals(props) {
  const { empresaAtual, loadingEmpresas } = useEmpresa();
  const { user } = useAuth();
  const company = resolveEmpresaErpId(empresaAtual);
  const canEdit = user?.auth_source === "pigo" ? user.permissions?.includes("management.manage") : ["Administrador ERP", "erp-admin", "admin", "administrator"].includes(user?.perfil || user?.role);
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState(false);
  const [seller, setSeller] = useState("0");
  const [amount, setAmount] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setData(null); setError(""); setEditing(false);
      if (loadingEmpresas) { setLoading(true); return; }
      if (!company || !/^\d{4}-\d{2}$/.test(month)) { setLoading(false); return; }
      setLoading(true);
      try {
        const response = await api.get("/dashboard/metas", { params: { empresa_id: company, mes: `${month}-01` }, signal: controller.signal });
        if (!controller.signal.aborted) setData(response.data);
      } catch (err) { if (!controller.signal.aborted) setError(err.message); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [company, month, loadingEmpresas, version]);

  async function save(event) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      await api.put("/dashboard/metas", { empresa_id: Number(company), mes: `${month}-01`, vendedor_id: Number(seller), valor: amount });
      setEditing(false); setAmount(""); setVersion((value) => value + 1);
    } catch (err) { setError(typeof err.message === "string" ? err.message : "Confira o valor e tente novamente."); }
    finally { setSaving(false); }
  }

  async function remove(goal) {
    if (!window.confirm(`Excluir a meta de ${goal.responsavel} para este mês?`)) return;
    setSaving(true); setError("");
    try { await api.delete(`/dashboard/metas/${goal.id}`, { params: { empresa_id: company } }); setVersion((value) => value + 1); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return <DashboardWorkspace dashboard={"metas"}><div className="dashboard-page commercial-page"><Topbar titulo="Metas de Vendas" caminho="Dashboard / Metas" {...props} />
    <header className="analytics-page-heading"><div><span className="analytics-eyebrow">PLANEJAMENTO COMERCIAL</span><h1>Metas de Vendas</h1><p>Transforme objetivos em acompanhamento mensal, por empresa e vendedor.</p></div><Link className="analytics-button" to="/performance">Equipe e Performance →</Link></header>
    <section className="analytics-panel analytics-goal-toolbar"><label>Mês de referência<input aria-label="Mês de referência" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>{canEdit && <button className="analytics-button primary" disabled={!data || saving} onClick={() => { setEditing(true); setSeller("0"); setAmount(""); }}>Cadastrar meta</button>}</section>
    {loading && <div className="analytics-notice" role="status">Carregando metas…</div>}
    {!company && !loadingEmpresas && <div className="analytics-notice">Selecione uma empresa com dados sincronizados.</div>}
    {error && <div className="analytics-notice analytics-error" role="alert">{error}<button className="analytics-button" onClick={() => setVersion((value) => value + 1)}>Tentar novamente</button></div>}
    {editing && <form className="analytics-panel analytics-goal-form" onSubmit={save}><h2>{data?.metas.some((goal) => String(goal.vendedor_id) === seller) ? "Atualizar meta" : "Cadastrar meta"}</h2><label>Responsável<select aria-label="Responsável" value={seller} onChange={(event) => { setSeller(event.target.value); const goal = data?.metas.find((item) => String(item.vendedor_id) === event.target.value); setAmount(goal ? String(goal.meta) : ""); }}><option value="0">Toda a empresa</option>{data?.vendedores.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}{data?.metas.filter((goal) => goal.vendedor_id && !data.vendedores.some((item) => String(item.id) === String(goal.vendedor_id))).map((goal) => <option key={goal.vendedor_id} value={goal.vendedor_id}>{goal.responsavel}</option>)}</select></label><label>Meta de faturamento (R$)<input aria-label="Meta de faturamento" type="number" min="0.01" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} /></label><p>O realizado considera vendas faturadas não canceladas no mês. A projeção usa a média por dia corrido e não representa uma previsão garantida.</p><div><button type="submit" className="analytics-button primary" disabled={saving}>{saving ? "Salvando…" : "Salvar meta"}</button><button type="button" className="analytics-button" onClick={() => setEditing(false)} disabled={saving}>Cancelar</button></div></form>}
    {data && <><div className="analytics-kpis"><DashboardBlock id="commercial-0" title="Faturamento do mês" kind="metric"><article className="analytics-kpi tone-0"><span>Faturamento do mês</span><strong>{money(data.faturamento)}</strong><small>Empresa selecionada</small></article><DashboardBlock id="commercial-1" title="Metas acompanhadas" kind="metric"></DashboardBlock><article className="analytics-kpi tone-1"><span>Metas acompanhadas</span><strong>{data.metas.length}</strong><small>Empresa e responsáveis</small></article></DashboardBlock></div>
      {!data.metas.length && <section className="analytics-panel analytics-empty"><h2>Seu próximo objetivo começa aqui</h2><p>Cadastre uma meta mensal para acompanhar o realizado, o valor restante e a projeção.</p></section>}
      <div className="analytics-goals-grid">{data.metas.map((goal) => <DashboardBlock id={"commercial-2-"+goal.id} key={goal.id} title={goal.responsavel} kind="chart"><article className="analytics-panel analytics-goal" key={goal.id}><div className="analytics-panel-heading"><h2>{goal.responsavel}</h2><span className={goal.percentual >= 100 ? "goal-achieved" : "goal-tracking"}>{goal.percentual >= 100 ? "Meta atingida" : "Em acompanhamento"}</span></div><strong className="goal-progress-value">{percent(goal.percentual)}</strong><progress aria-label={`Progresso da meta de ${goal.responsavel}`} max="100" value={Math.min(goal.percentual, 100)} /><dl><div><dt>Realizado</dt><dd>{money(goal.realizado)}</dd></div><div><dt>Meta</dt><dd>{money(goal.meta)}</dd></div><div><dt>Falta atingir</dt><dd>{money(goal.faltante)}</dd></div><div><dt>Projeção do mês</dt><dd>{money(goal.projecao)}</dd></div></dl>{canEdit && <div className="analytics-goal-actions"><button className="analytics-button" disabled={saving} onClick={() => { setSeller(String(goal.vendedor_id)); setAmount(String(goal.meta)); setEditing(true); }}>Editar</button><button className="analytics-button danger" disabled={saving} onClick={() => remove(goal)}>Excluir</button></div>}</article></DashboardBlock>)}</div>
    </>}
  </div></DashboardWorkspace>;
}
