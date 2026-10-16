import DashboardWorkspace, { DashboardBlock } from "../components/DashboardWorkspace";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Topbar from "../components/Topbar";
import DashboardFilters from "../components/DashboardFilters";
import AnalyticsTable from "../components/AnalyticsTable";
import { useEmpresa } from "../context/EmpresaContext";
import { resolveEmpresaErpId } from "../services/empresaIdentity";
import api from "../services/api";
import { money, number, percent } from "../utils/analytics";
import "../styles/dashboard.css";
import "../styles/commercial-analytics.css";

const CUSTOMER_COLUMNS = [{ key: "nome", label: "Cliente" }, { key: "pedidos", label: "Pedidos", render: number }, { key: "valor", label: "Faturamento", render: money }];
const INACTIVE_COLUMNS = [{ key: "codigo", label: "Código" }, { key: "nome", label: "Cliente" }, { key: "cidade", label: "Cidade" }];
const ABC_COLUMNS = [{ key: "codigo", label: "Código" }, { key: "produto", label: "Produto" }, { key: "quantidade", label: "Quantidade", render: number }, { key: "valor", label: "Faturamento", render: money }, { key: "participacao", label: "Participação", render: percent }, { key: "acumulado", label: "Acumulado", render: percent }, { key: "classe", label: "Classe", render: (value) => <span className={`abc-badge class-${value}`}>{value}</span> }];
const NO_DATA = [];

export default function CommercialAnalytics({ mode, ...props }) {
  const customers = mode === "clientes";
  const { empresaAtual, loadingEmpresas } = useEmpresa();
  const company = resolveEmpresaErpId(empresaAtual);
  const [filters, setFilters] = useState({ period: "today" });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [abcClass, setAbcClass] = useState("Todas");
  const onFilters = useCallback((value) => setFilters(value), []);
  const title = customers ? "Dashboard de Clientes" : "Curva ABC de Produtos";

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setData(null); setError("");
      if (loadingEmpresas) { setLoading(true); return; }
      if (!company) { setLoading(false); return; }
      if (filters.period === "custom" && (!filters.start || !filters.end || filters.start > filters.end)) {
        setError("Selecione um intervalo válido: a data inicial deve ser anterior à final."); setLoading(false); return;
      }
      setLoading(true);
      try {
        const response = await api.get(`/dashboard/${customers ? "clientes" : "curva-abc"}`, {
          params: { empresa_id: company, period: filters.period, start: filters.start, end: filters.end }, signal: controller.signal,
        });
        if (!controller.signal.aborted) setData(response.data);
      } catch (err) {
        if (!controller.signal.aborted) setError(typeof err.message === "string" ? err.message : "Não foi possível carregar a análise.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [company, customers, filters, loadingEmpresas, version]);

  const cards = customers && data ? [
    ["Clientes cadastrados", number(data.resumo.clientes), "Carteira da empresa"],
    ["Clientes compradores", number(data.resumo.compradores), "Com vendas no período"],
    ["Novos clientes", number(data.resumo.novos), "Cadastrados no período"],
    ["Ticket médio", money(data.resumo.ticketMedio), "Faturamento por pedido"],
  ] : data ? [["Faturamento analisado", money(data.total), "Produtos com receita positiva"], ...data.classes.map((item) => [`Classe ${item.classe}`, number(item.produtos), `${money(item.valor)} em vendas`])] : [];
  const products = (data?.produtos || NO_DATA).filter((item) => abcClass === "Todas" || item.classe === abcClass);

  return <DashboardWorkspace dashboard={mode}><div className="dashboard-page commercial-page">
    <Topbar titulo={title} caminho={`Dashboard / ${customers ? "Clientes" : "Curva ABC"}`} {...props} />
    <header className="analytics-page-heading"><div><span className="analytics-eyebrow">INTELIGÊNCIA COMERCIAL</span><h1>{title}</h1><p>{customers ? "Conheça sua carteira e descubra oportunidades de relacionamento." : "Priorize os produtos que mais contribuem para seu faturamento."}</p></div><Link className="analytics-button" to="/relatorios/vendas">Relatórios com IA →</Link></header>
    <DashboardFilters onChange={onFilters} showStatus={false} />
    {!company && !loadingEmpresas && <div className="analytics-notice">Selecione uma empresa com dados sincronizados para consultar esta análise.</div>}
    {loading && <div className="analytics-notice" role="status">Carregando análise…</div>}
    {error && <div className="analytics-notice analytics-error" role="alert">{error}<button className="analytics-button" onClick={() => setVersion((value) => value + 1)}>Tentar novamente</button></div>}
    {data && <>
      <div className="analytics-kpis">{cards.map(([label, value, hint], index) => <DashboardBlock id={"commercial-0-"+label} key={label} title={label} kind="metric"><article className={`analytics-kpi tone-${index}`} key={label}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article></DashboardBlock>)}</div>
      {customers ? <>
        <div className="analytics-two-columns"><DashboardBlock id="commercial-1" title="Clientes por cidade" kind="chart" rows={data.cidades.slice(0, 8)} labelKey="nome" series={[{key:"clientes",label:"Clientes"}]}><section className="analytics-panel"><h2>Clientes por cidade</h2>{data.cidades.length ? <div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.cidades.slice(0, 8)}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="nome" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar isAnimationActive={false} dataKey="clientes" name="Clientes" fill="#2563eb" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p className="analytics-empty">Nenhum cliente sincronizado.</p>}</section></DashboardBlock>
          <DashboardBlock id="commercial-2" title="RELACIONAMENTO" kind="chart"><section className="analytics-panel analytics-opportunity"><span className="analytics-eyebrow">RELACIONAMENTO</span><h2>{number(data.resumo.semCompras)} {data.resumo.semCompras === 1 ? "cliente sem compras" : "clientes sem compras"}</h2><p>Clientes cadastrados sem uma venda faturada no intervalo selecionado. Use a lista abaixo para planejar a retomada do contato.</p><strong>{money(data.resumo.faturamento)}</strong><small>Faturamento da carteira no período</small><Link className="analytics-button" to="/dashboard/metas">Acompanhar metas →</Link></section></DashboardBlock></div>
        <DashboardBlock id="commercial-3" title="Ranking de clientes" kind="wide"><AnalyticsTable title="Ranking de clientes" rows={data.ranking} columns={CUSTOMER_COLUMNS} filename="ranking-clientes.csv" /></DashboardBlock>
        <DashboardBlock id="commercial-4" title="Clientes sem compras no período" kind="wide"><AnalyticsTable title="Clientes sem compras no período" rows={data.semCompras} columns={INACTIVE_COLUMNS} filename="clientes-sem-compras.csv" /></DashboardBlock>
      </> : <>
        <DashboardBlock id="commercial-5" title="Concentração do faturamento" kind="chart" rows={data.produtos.slice(0, 10)} labelKey="produto" series={[{key:"valor",label:"Faturamento"}]}><section className="analytics-panel"><div className="analytics-panel-heading"><div><h2>Concentração do faturamento</h2><p>Classe A até 80%, B até 95% e C no restante. O produto que cruza cada limite permanece na classe anterior.</p></div><label>Classe <select aria-label="Filtrar classe ABC" value={abcClass} onChange={(event) => setAbcClass(event.target.value)}>{["Todas", "A", "B", "C"].map((value) => <option key={value}>{value}</option>)}</select></label></div>
          {data.produtos.length > 0 && <div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.produtos.slice(0, 10)}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="produto" tick={{ fontSize: 10 }} /><YAxis tickFormatter={(value) => number(value)} /><Tooltip formatter={(value) => money(value)} /><Bar isAnimationActive={false} dataKey="valor" name="Faturamento" fill="#2563eb" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div>}
        </section></DashboardBlock><DashboardBlock id="commercial-6" title="Classificação de produtos" kind="table"><AnalyticsTable title="Classificação de produtos" rows={products} columns={ABC_COLUMNS} filename="curva-abc.csv" /></DashboardBlock>
      </>}
    </>}
  </div></DashboardWorkspace>;
}
