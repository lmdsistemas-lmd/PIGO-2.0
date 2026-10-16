import { downloadBlob } from "./downloadArquivo.js";

export const money = (value) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
export const number = (value) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(Number(value || 0));
export const percent = (value) => `${number(value)}%`;

export function csvCell(value) {
  let text = String(value ?? "");
  if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function exportAnalytics(rows, columns, filename) {
  const contents = [columns.map((column) => csvCell(column.label)).join(";"),
    ...rows.map((row) => columns.map((column) => csvCell(row[column.key])).join(";"))].join("\r\n");
  downloadBlob(new Blob(["\ufeff", contents], { type: "text/csv;charset=utf-8" }), filename);
}
