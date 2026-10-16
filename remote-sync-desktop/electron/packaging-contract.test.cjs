const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

test("contrato do bootstrap Electron preserva preload e isolamento", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  const mainPath = path.join(root, pkg.main);
  const preloadPath = path.join(__dirname, "preload.cjs");
  const rendererPath = path.join(root, "index.html");
  const main = fs.readFileSync(mainPath, "utf8");
  const preload = fs.readFileSync(preloadPath, "utf8");

  assert.equal(pkg.main, "electron/main.cjs");
  assert.equal(fs.existsSync(mainPath), true);
  assert.equal(fs.existsSync(preloadPath), true);
  assert.equal(fs.existsSync(rendererPath), true);
  assert.deepEqual(pkg.build.asarUnpack, ["electron/preload.cjs"]);
  assert.match(main, /preload:\s*preloadPath/);
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /sandbox:\s*rendererSandbox/);
  assert.match(preload, /contextBridge\.exposeInMainWorld\("pigo"/);
  assert.doesNotMatch(preload, /exposeInMainWorld\([^,]+,\s*ipcRenderer/);
});

test("HTML inicia em Standards Mode", () => {
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  assert.equal(html.toLowerCase().startsWith("<!doctype html>"), true);
});
