import api from "./api";

export async function listarFuncionarios() {
  const response = await api.get("/funcionarios/");
  return response.data;
}

export async function listarColaboradoresERPDisponiveis(search = "") {
  const response = await api.get("/funcionarios/erp-disponiveis", {
    params: { search },
  });
  return response.data;
}

export async function detalharFuncionario(id) {
  const response = await api.get(`/funcionarios/${id}`);
  return response.data;
}

export async function criarFuncionario(dados) {
  const response = await api.post("/funcionarios/", dados);
  return response.data;
}

export async function atualizarFuncionario(id, dados) {
  const response = await api.put(`/funcionarios/${id}`, dados);
  return response.data;
}

export async function excluirFuncionario(id) {
  const response = await api.delete(`/funcionarios/${id}`);
  return response.data;
}

export async function listarDepartamentos() {
  const response = await api.get("/departamentos/");
  return response.data;
}

export async function criarDepartamento(dados) {
  const response = await api.post("/departamentos/", dados);
  return response.data;
}

export async function atualizarDepartamento(id, dados) {
  const response = await api.put(`/departamentos/${id}`, dados);
  return response.data;
}

export async function excluirDepartamento(id) {
  const response = await api.delete(`/departamentos/${id}`);
  return response.data;
}

export async function listarCargos() {
  const response = await api.get("/cargos/");
  return response.data;
}

export async function criarCargo(dados) {
  const response = await api.post("/cargos/", dados);
  return response.data;
}

export async function atualizarCargo(id, dados) {
  const response = await api.put(`/cargos/${id}`, dados);
  return response.data;
}

export async function excluirCargo(id) {
  const response = await api.delete(`/cargos/${id}`);
  return response.data;
}
