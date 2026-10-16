import { useMemo, useState } from "react";
import ReportCard from "./ReportCard";
import ReportTemplates from "./ReportTemplates";

export default function ReportsLibrary({ category, categoryMeta, reports, templates, loading, error, favorites, onNew, onUseTemplate, onOpen, onRun, onDuplicate, onDelete, onFavorite, onRetry }) {
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const filtered = useMemo(() => reports.filter((report) => (!sourceFilter || report.source === sourceFilter) && `${report.name} ${report.description}`.toLowerCase().includes(search.toLowerCase())), [reports, search, sourceFilter]);
  return <div className="reports-library">
    <header className="reports-category-heading"><div><span>Biblioteca</span><h1>{category.title}</h1><p>{category.description}</p></div><button className="reports-button primary" onClick={onNew} disabled={!Object.keys(categoryMeta.sources || {}).length}>+ Novo relatório</button></header>
    <div className="reports-toolbar"><label><span>Pesquisar</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar relatórios…" /></label><label><span>Fonte</span><select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option value="">Todas as fontes</option>{Object.entries(categoryMeta.sources || {}).map(([key, source]) => <option key={key} value={key}>{source.label}</option>)}</select></label></div>
    {error && <div className="reports-error-state"><strong>Não foi possível carregar a biblioteca.</strong><p>{error}</p><button className="reports-button" onClick={onRetry}>Tentar novamente</button></div>}
    {!error && <ReportTemplates templates={templates} sources={categoryMeta.sources || {}} onUse={onUseTemplate} />}
    <section className="reports-library-section"><header><div><span>Sua equipe</span><h2>Meus relatórios</h2></div><b>{filtered.length}</b></header>{loading ? <div className="reports-skeleton-grid"><i /><i /><i /></div> : filtered.length ? <div className="reports-card-grid">{filtered.map((report) => <ReportCard key={report.id} report={report} sourceLabel={categoryMeta.sources?.[report.source]?.label || report.source} categoryLabel={category.label} favorite={favorites.includes(report.id)} onFavorite={() => onFavorite(report.id)} onOpen={() => onOpen(report)} onRun={() => onRun(report)} onDuplicate={() => onDuplicate(report)} onDelete={() => onDelete(report)} />)}</div> : <div className="reports-empty"><strong>Nenhum relatório encontrado.</strong><p>{Object.keys(categoryMeta.sources || {}).length ? "Crie um relatório ou ajuste a pesquisa." : `Fontes previstas: ${(categoryMeta.planned_sources || []).join(", ")}.`}</p></div>}</section>
    <section className="reports-library-section"><header><div><span>Colaboração</span><h2>Relatórios compartilhados</h2></div></header><div className="reports-empty compact">O compartilhamento aparecerá aqui quando houver modelos publicados pela equipe.</div></section>
  </div>;
}
