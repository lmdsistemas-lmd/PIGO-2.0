import { useState } from "react";
import { CHARTS } from "./reportConfig";

export default function ReportCard({ report, sourceLabel, categoryLabel, favorite, onFavorite, onOpen, onRun, onDuplicate, onDelete }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const updated = report.updated_at ? new Date(report.updated_at).toLocaleDateString("pt-BR") : "—";
  return <article className="reports-card">
    <header><span className="reports-status">Ativo</span><button className={favorite ? "favorite active" : "favorite"} onClick={onFavorite} aria-label="Favoritar relatório">★</button></header>
    <div><small>{categoryLabel} · {sourceLabel}</small><h3>{report.name}</h3><p>{report.description || "Sem descrição."}</p></div>
    <dl><div><dt>Visualização</dt><dd>{CHARTS[report.definition?.chart] || "Tabela"}</dd></div><div><dt>Alterado</dt><dd>{updated}</dd></div><div><dt>Autor</dt><dd>{report.created_by || "Equipe"}</dd></div></dl>
    <footer><button className="reports-button primary" onClick={onOpen}>Abrir</button><button className="reports-button" onClick={onRun}>Executar</button><div className="reports-context"><button onClick={() => setMenuOpen((value) => !value)} aria-label="Mais ações">•••</button>{menuOpen && <div><button onClick={onDuplicate}>Duplicar</button><button onClick={onDelete}>Excluir</button></div>}</div></footer>
  </article>;
}
