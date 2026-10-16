import api from "./api";

export const getReportCatalog = async () => (await api.get("/reports/catalog")).data;
export const getReadyTemplates = async (category) => (await api.get("/reports/ready-templates", { params: { category } })).data;
export const getFilterOptions = async (category, source, filter, empresaId, search = "") => (await api.get(`/reports/catalog/${category}/${source}/filters/${filter}/options`, { params: { empresa_id: empresaId, search } })).data;
export const listReports = async (category) => (await api.get("/reports", { params: { category } })).data;
export const createReport = async (payload) => (await api.post("/reports", payload)).data;
export const updateReport = async (id, payload) => (await api.put(`/reports/${id}`, payload)).data;
export const duplicateReport = async (id) => (await api.post(`/reports/${id}/duplicate`)).data;
export const deleteReport = async (id) => api.delete(`/reports/${id}`);
export const previewReport = async (payload) => (await api.post("/reports/preview", payload)).data;
export const interpretReportPrompt = async (payload) => (await api.post("/reports/assistant/interpret", payload)).data;
export async function exportReport(payload) {
  const response = await api.post("/reports/export", payload, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `relatorio-pigo.${payload.format === "excel" ? "xlsx" : payload.format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
