const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

test("Node x64 conecta ao owner Python x86 e x64 apos atraso de 10 segundos", { skip: process.platform !== "win32", timeout: 45000 }, async () => {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "pigo-owner-real-"));
  process.env.PIGO_REMOTE_SYNC_DATA_DIR = dataDir;
  const config = require("./config-manager.cjs");
  config.save({
    firebird: { host: "127.0.0.1", port: 3050, database: "test.fdb", user: "SYSDBA", clientPath: "fbclient.dll", charset: "WIN1252", driver: "fdb", architecture: "x64" },
    pigo: { apiBaseUrl: "https://example.invalid/api", companyCnpj: "12345678000199", syncIntervalMinutes: 60 },
    secrets: { firebirdPassword: "firebird-test", licenseApiKey: "license-test" },
  });
  const runtimeRoot = process.env.PIGO_TEST_RUNTIME_ROOT || path.resolve(__dirname, "../runtime");
  const agentDir = process.env.PIGO_TEST_AGENT_DIR || path.resolve(__dirname, "../../remote-sync-agent");
  const seedPython = path.join(runtimeRoot, "python-x64", "python.exe");
  const seed = "import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from credential_store import CredentialStore;s=CredentialStore(Path(sys.argv[2])/'credentials.dat',Path(sys.argv[2])/'installation.json');s.save_token('token-test');s.ensure_ipc_secret()";
  const seeded = spawnSync(seedPython, ["-c", seed, agentDir, dataDir], { encoding: "utf8", env: { ...process.env, PIGO_REMOTE_SYNC_DATA_DIR: dataDir } });
  assert.equal(seeded.status, 0, seeded.stderr);
  const { IpcClient } = require("./ipc-client.cjs");
  for (const architecture of ["x86", "x64"]) {
    const python = path.join(runtimeRoot, `python-${architecture}`, "python.exe");
    const pipeName = `PIGORemoteSyncReal${architecture}${process.pid}`;
    const pipe = `\\\\.\\pipe\\${pipeName}`;
    const child = spawn(python, [path.join(agentDir, "agent.py"), "--owner", "--pipe-name", pipeName], {
      cwd: agentDir,
      windowsHide: true,
      env: { ...process.env, PIGO_REMOTE_SYNC_DATA_DIR: dataDir, PYTHONUNBUFFERED: "1", PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
    });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (data) => { stdout += String(data); });
    child.stderr?.on("data", (data) => { stderr += String(data); });
    const client = new IpcClient(() => config.ipcSecret(), pipe);
    try {
      await new Promise((resolve) => setTimeout(resolve, 10000));
      let response;
      try {
        response = await client.waitReady(8000);
      } catch (error) {
        error.message += ` architecture=${architecture} exit=${child.exitCode} stdout=${stdout} stderr=${stderr}`;
        throw error;
      }
      assert.equal(response.success, true);
      assert.equal(response.data.owner, "desktop");
      assert.equal(response.data.pid, child.pid);
      const ping = await client.request("ping");
      assert.equal(ping.code, "PONG");
      assert.equal(ping.data.pid, child.pid);
      assert.equal(ping.version, 1);
      const status = await client.request("status");
      assert.equal(status.data.pid, child.pid);
    } finally {
      if (child.exitCode === null) {
        const exited = new Promise((resolve) => child.once("exit", resolve));
        child.kill();
        await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 2000))]);
      }
    }
  }
});
