const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const { execFile } = require("node:child_process");
function peArchitecture(file) {
  const b = fs.readFileSync(file);
  if (b.readUInt16LE(0) !== 0x5a4d)
    throw new Error("Arquivo não é uma DLL PE válida");
  const pe = b.readUInt32LE(0x3c);
  const machine = b.readUInt16LE(pe + 4);
  if (machine === 0x14c) return "x86";
  if (machine === 0x8664) return "x64";
  throw new Error(`Arquitetura PE não suportada: 0x${machine.toString(16)}`);
}
function candidateRoots() {
  return [
    "C:\\Program Files\\Firebird",
    "C:\\Program Files (x86)\\Firebird",
    "C:\\Firebird",
  ].filter(fs.existsSync);
}
function walk(root, depth = 3, out = []) {
  if (depth < 0) return out;
  let items = [];
  try {
    items = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const item of items) {
    const full = path.join(root, item.name);
    if (item.isFile() && item.name.toLowerCase() === "fbclient.dll")
      out.push(full);
    else if (item.isDirectory()) walk(full, depth - 1, out);
  }
  return out;
}
function versionFrom(file) {
  const m = file.match(/(?:Firebird[_ -]?)?([35])(?:[_ .-]?\d)?/i);
  return m ? m[1] : "desconhecida";
}
async function detect() {
  const files = [...new Set(candidateRoots().flatMap((x) => walk(x)))];
  return files.map((clientPath) => {
    let architecture = "desconhecida";
    try {
      architecture = peArchitecture(clientPath);
    } catch {}
    return {
      clientPath,
      architecture,
      version: versionFrom(clientPath),
      installationPath: path.dirname(clientPath),
    };
  });
}
function portOpen(host, port, timeout = 1500) {
  return new Promise((resolve) => {
    const s = net.createConnection({ host, port: Number(port) });
    const done = (ok) => {
      s.destroy();
      resolve(ok);
    };
    s.setTimeout(timeout);
    s.once("connect", () => done(true));
    s.once("timeout", () => done(false));
    s.once("error", () => done(false));
  });
}
module.exports = { peArchitecture, detect, portOpen, candidateRoots };
