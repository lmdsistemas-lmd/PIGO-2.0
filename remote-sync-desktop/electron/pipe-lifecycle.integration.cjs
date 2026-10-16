const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { IpcClient } = require("./ipc-client.cjs");

function waitFor(predicate, timeout = 5000) {
  const end = Date.now() + timeout;
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (predicate()) return resolve();
      if (Date.now() >= end) return reject(new Error("WAIT_TIMEOUT"));
      setTimeout(tick, 50);
    };
    tick();
  });
}

test("instancia permanece LISTENING por 30 segundos sem cliente", { skip: process.platform !== "win32", timeout: 45000 }, async () => {
  const secret = "lifecycle-test-secret";
  const pipeName = `PIGORemoteSyncIdle${process.pid}`;
  const pipePath = `\\\\.\\pipe\\${pipeName}`;
  const python = path.resolve(__dirname, "../runtime/python-x64/python.exe");
  const agentDir = path.resolve(__dirname, "../../remote-sync-agent");
  const script = [
    "import sys,time",
    "sys.path.insert(0,sys.argv[1])",
    "from owner import AgentOwner,NamedPipeServer",
    "o=AgentOwner(lambda: True,lambda: True,lambda: True,interval_minutes=60)",
    "o.start()",
    "NamedPipeServer(o,sys.argv[2],sys.argv[3]).start()",
    "time.sleep(40)",
  ].join(";");
  const child = spawn(python, ["-c", script, agentDir, secret, pipePath], { windowsHide: true });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (data) => { stdout += String(data); });
  child.stderr.on("data", (data) => { stderr += String(data); });
  try {
    await waitFor(() => stdout.includes("instance=1 waiting_for_client=true"));
    assert.ok(fs.readdirSync("\\\\.\\pipe\\").includes(pipeName));
    await new Promise((resolve) => setTimeout(resolve, 30000));
    assert.equal((stdout.match(/handle_created=true/g) || []).length, 1, stdout);
    assert.equal(child.exitCode, null, stderr);
    assert.ok(fs.readdirSync("\\\\.\\pipe\\").includes(pipeName));
    const client = new IpcClient(() => secret, pipePath);
    assert.equal((await client.request("ping")).code, "PONG");
    assert.equal((await client.request("status")).data.pid, child.pid);
    await waitFor(() => (stdout.match(/handle_created=true/g) || []).length >= 3);
  } finally {
    child.kill();
  }
});
