const fs = require("node:fs");
const { URL } = require("node:url");
const { peArchitecture, portOpen } = require("./firebird-detector.cjs");
async function diagnose(c) {
  const f = c.firebird || {},
    steps = [];
  const add = (label, ok, message) =>
    steps.push({ label, ok: Boolean(ok), message });
  const remote = String(f.database || "").startsWith("\\\\");
  const dbExists = remote || fs.existsSync(f.database || "");
  add(
    "Banco encontrado",
    dbExists,
    dbExists ? "Caminho disponível" : "Arquivo não localizado neste computador",
  );
  const dll = fs.existsSync(f.clientPath || "");
  add("DLL localizada", dll, dll ? f.clientPath : "Selecione fbclient.dll");
  let arch = "";
  if (dll)
    try {
      arch = peArchitecture(f.clientPath);
      add(
        "Arquitetura compatível",
        !f.architecture || arch === f.architecture,
        `${arch} detectado`,
      );
    } catch (e) {
      add("Arquitetura compatível", false, e.message);
    }
  add(
    "Porta acessível",
    await portOpen(f.host || "127.0.0.1", f.port || 3050),
    `${f.host}:${f.port}`,
  );
  try {
    const u = new URL(c.pigo?.apiBaseUrl);
    add("URL do PIGO", u.protocol === "https:", "HTTPS configurado");
  } catch {
    add("URL do PIGO", false, "URL inválida");
  }
  add(
    "CNPJ configurado",
    /^\d{14}$/.test(String(c.pigo?.companyCnpj || "").replace(/\D/g, "")),
    "Informe 14 dígitos",
  );
  return { ok: steps.every((x) => x.ok), steps };
}
module.exports = { diagnose };
