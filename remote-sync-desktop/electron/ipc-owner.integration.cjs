const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { IpcClient } = require("./ipc-client.cjs");

test("sync-now usa o mesmo PID do proprietario via Named Pipe", { skip: process.platform !== "win32", timeout: 20000 }, async () => {
  const secret = "integration-local-secret";
  const pipe = `\\\\.\\pipe\\PIGORemoteSyncTest${process.pid}`;
  const python = path.resolve(__dirname, "../runtime/python-x64/python.exe");
  const agentDir = path.resolve(__dirname, "../../remote-sync-agent");
  const script = [
    "import sys,time",
    "sys.path.insert(0,sys.argv[1])",
    "from owner import AgentOwner,NamedPipeServer",
    "o=AgentOwner(lambda: (time.sleep(1) or True),lambda: True,lambda: True,interval_minutes=60)",
    "o.start()",
    "NamedPipeServer(o,sys.argv[2],sys.argv[3]).start()",
    "time.sleep(15)",
  ].join(";");
  const child = spawn(python, ["-c", script, agentDir, secret, pipe], { windowsHide: true });
  let stdout = "";
  let stderr = "";
  child.stdout?.on("data", (data) => { stdout += String(data); });
  child.stderr?.on("data", (data) => { stderr += String(data); });
  const client = new IpcClient(() => secret, pipe);
  try {
    let before;
    try {
      before = await client.waitReady(8000, { ownerPid: child.pid, isOwnerAlive: () => child.exitCode === null });
    } catch (error) {
      error.message += ` exit=${child.exitCode} stdout=${stdout} stderr=${stderr}`;
      throw error;
    }
    assert.equal(before.success, true);
    const accepted = await client.request("sync-now");
    assert.equal(accepted.code, "COMMAND_ACCEPTED");
    // O IPC deve continuar respondendo enquanto a sincronizacao esta em andamento.
    const duringSync = await client.request("status");
    assert.equal(duringSync.data.pid, before.data.pid);
    assert.equal(duringSync.data.pid, child.pid);
    const bad = new IpcClient(() => "incorrect", pipe);
    const rejected = await bad.request("status");
    assert.equal(rejected.code, "IPC_AUTH_FAILED");
  } finally {
    child.kill();
  }
});
