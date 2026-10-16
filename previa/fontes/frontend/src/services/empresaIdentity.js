export function resolveEmpresaErpId(empresa) {
  const candidate = empresa?.erp_id ?? empresa?.empresa_id ?? empresa?.id;

  if (candidate === null || candidate === undefined || candidate === "") {
    return "";
  }

  const normalized = String(candidate).trim();
  return /^\d+$/.test(normalized) ? normalized : "";
}

export function normalizeCnpj(value) {
  return String(value || "").replace(/\D/g, "");
}

export function maskCnpj(value) {
  const digits = normalizeCnpj(value);
  return digits.length === 14
    ? `${digits.slice(0, 2)}.***.***/****-${digits.slice(-2)}`
    : "";
}
