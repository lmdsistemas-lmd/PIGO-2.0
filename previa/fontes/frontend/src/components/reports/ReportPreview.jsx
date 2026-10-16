import { useState } from "react";

function formatValue(value, type) {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "currency") return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
  if (["number", "decimal"].includes(type)) return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(Number(value));
  if (type === "boolean") return String(value).toUpperCase() === "S" ? "Sim" : String(value).toUpperCase() === "N" ? "Não" : String(value);
  if (type === "date") { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString("pt-BR"); }
  return String(value);
}

function PreviewChart({ preview }) {
  if (!preview || preview.chart === "table" || !preview.rows.length) return null;
  if (preview.chart === "cards") return <div className="reports-preview-cards">{preview.columns.slice(0, 4).map((column) => <article key={column.key}><span>{column.label}</span><strong>{formatValue(preview.rows[0][column.key], column.format || column.type)}</strong></article>)}</div>;
  const labelKey = preview.columns[0]?.key;
  const valueKey = preview.columns.find((column) => preview.rows.some((row) => Number.isFinite(Number(row[column.key]))))?.key;
  if (!labelKey || !valueKey) return null;
  const values = preview.rows.slice(0, 12).map((row) => ({ label: String(row[labelKey] ?? ""), value: Number(row[valueKey] || 0) }));
  const maximum = Math.max(...values.map((item) => Math.abs(item.value)), 1);
  return <div className={`reports-preview-chart chart-${preview.chart}`}>{values.map((item, index) => <div key={`${item.label}-${index}`}><i style={{ height: `${Math.max(8, Math.abs(item.value) / maximum * 180)}px` }} /><span>{item.label}</span></div>)}</div>;
}

export default function ReportPreview({ title, preview, definition, whiteLabel, loading, error, onRefresh, onEdit, onBack, onExport }) {
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState("");
  async function exportAs(format) { setExporting(format); try { await onExport(format); } finally { setExporting(""); setExportOpen(false); } }
  return <section className="reports-preview-page" style={{ "--report-accent": whiteLabel?.primaryColor || "#2563eb" }}>
    <header className="reports-preview-toolbar"><div><button onClick={onBack}>← Biblioteca</button><span>Preview limitado a 50 registros</span><h1>{whiteLabel?.title || title || "Pré-visualização"}</h1>{whiteLabel?.subtitle && <p>{whiteLabel.subtitle}</p>}</div><div><button className="reports-button" onClick={onEdit}>Editar</button><button className="reports-button" onClick={onRefresh} disabled={loading}>Atualizar</button><div className="reports-export-menu"><button className="reports-button primary" onClick={() => setExportOpen((value) => !value)}>{exporting ? "Exportando…" : "Exportar"}</button>{exportOpen && <div><button onClick={() => exportAs("pdf")}>PDF</button><button onClick={() => exportAs("excel")}>Excel</button><button onClick={() => exportAs("csv")}>CSV</button><button onClick={() => window.print()}>Imprimir</button></div>}</div></div></header>
    {definition?.filters?.length > 0 && <div className="reports-applied-filters"><strong>Filtros aplicados</strong>{definition.filters.map((filter, index) => <span key={`${filter.field}-${index}`}>{filter.field}: {Array.isArray(filter.value) ? filter.value.join(" → ") : String(filter.value)}</span>)}</div>}
    <div className="reports-preview-surface">{loading ? <div className="reports-preview-state"><i /><strong>Gerando preview…</strong><p>Aguarde enquanto o Report Engine processa a definição.</p></div> : error ? <div className="reports-preview-state error"><strong>Não foi possível gerar o preview.</strong><p>{error}</p><button className="reports-button" onClick={onRefresh}>Tentar novamente</button></div> : !preview ? <div className="reports-preview-state"><strong>Preview ainda não gerado.</strong><p>Use “Gerar preview” para consultar os dados explicitamente.</p><button className="reports-button primary" onClick={onRefresh}>Gerar preview</button></div> : <><div className="reports-preview-meta"><span>{preview.row_count} registro(s) encontrados</span><span>{preview.query_time_ms} ms</span><span>{preview.cache === "hit" ? "Cache" : "Consulta"}</span></div><PreviewChart preview={preview} />{preview.rows.length ? <div className="reports-table-wrap"><table><thead><tr>{preview.columns.map((column) => <th key={column.key} title={column.help}>{column.label}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.key}>{formatValue(row[column.key], column.format || column.type)}</td>)}</tr>)}</tbody></table></div> : <div className="reports-preview-state"><strong>Nenhum dado encontrado.</strong><p>Ajuste os filtros e gere um novo preview.</p></div>}</>}</div>
    {whiteLabel?.footer && <footer className="reports-print-footer"><span>{whiteLabel.footerText}</span>{whiteLabel.issueDate && <span>Emitido em {new Date().toLocaleDateString("pt-BR")}</span>}</footer>}
  </section>;
}
