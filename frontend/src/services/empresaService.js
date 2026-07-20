import api from "./api";

export async function listarEmpresas() {
  const response = await api.get("/empresas");
  return response.data;
}

export async function obterTenantAtual() {
  const response = await api.get("/me/tenant");
  return response.data;
}
