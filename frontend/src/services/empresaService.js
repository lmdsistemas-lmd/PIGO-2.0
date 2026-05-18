import api from "./api";

export async function listarEmpresas() {
  const response = await api.get("/empresas");
  return response.data;
}