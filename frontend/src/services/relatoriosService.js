import api from "./api";

export async function listarRelatorios(categoria) {
  const response = await api.get(`/relatorios/categoria/${categoria}`);
  return response.data;
}

export async function inspecionarRelatorio(cdarquivo) {
  const response = await api.get(`/relatorios/${cdarquivo}/inspecionar`);
  return response.data;
}

export async function obterOpcoesRelatorio(cdarquivo, payload = {}) {
  const response = await api.post(`/relatorios/${cdarquivo}/opcoes`, payload);
  return response.data;
}

export async function executarPreviewRelatorio(
  cdarquivo,
  payload = {},
  limit = 200
) {
  const response = await api.post(
    `/relatorios/${cdarquivo}/preview?limit=${limit}`,
    payload
  );

  return response.data;
}