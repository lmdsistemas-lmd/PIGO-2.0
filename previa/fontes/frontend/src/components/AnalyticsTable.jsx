import { useMemo, useState } from "react";
import { exportAnalytics } from "../utils/analytics";

export default function AnalyticsTable({ title, rows = [], columns, filename = "analise.csv" }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState(null);
  const filtered = useMemo(() => {
    const normalize = (value) => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
    const items = rows.filter((row) => columns.some((column) => normalize(row[column.key]).includes(normalize(search))));
    if (sort) items.sort((a, b) => {
      const left = a[sort.key] ?? "";
      const right = b[sort.key] ?? "";
      return (typeof left === "number" && typeof right === "number" ? left - right : String(left).localeCompare(String(right), "pt-BR", { numeric: true })) * sort.direction;
    });
    return items;
  }, [rows, columns, search, sort]);
  const lastPage = Math.max(0, Math.ceil(filtered.length / 15) - 1);
  const currentPage = Math.min(page, lastPage);
  return <section className="analytics-panel">
    <div className="analytics-panel-heading"><h2>{title}</h2><button className="analytics-button" disabled={!filtered.length} onClick={() => exportAnalytics(filtered, columns, filename)}>Exportar CSV</button></div>
    <label className="analytics-search"><span>Buscar nesta tabela</span><input type="search" placeholder="Digite para filtrar" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} /></label>
    <div className="analytics-table-scroll"><table><thead><tr>{columns.map((column) => <th key={column.key} scope="col" aria-sort={sort?.key === column.key ? sort.direction === 1 ? "ascending" : "descending" : "none"}><button onClick={() => { setSort({ key: column.key, direction: sort?.key === column.key ? -sort.direction : 1 }); setPage(0); }}>{column.label}{sort?.key === column.key ? sort.direction === 1 ? " ↑" : " ↓" : ""}</button></th>)}</tr></thead>
      <tbody>{filtered.slice(currentPage * 15, currentPage * 15 + 15).map((row, index) => <tr key={`${row.codigo ?? index}-${index}`}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row[column.key], row) : String(row[column.key] ?? "—")}</td>)}</tr>)}
        {!filtered.length && <tr><td colSpan={columns.length} className="analytics-empty">Nenhum registro encontrado para esta seleção.</td></tr>}</tbody></table></div>
    <div className="analytics-pagination"><span>{filtered.length} registros · Página {currentPage + 1} de {lastPage + 1}</span><div><button className="analytics-button" disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>Anterior</button><button className="analytics-button" disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}>Próxima</button></div></div>
  </section>;
}
