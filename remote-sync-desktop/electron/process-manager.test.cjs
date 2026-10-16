const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { ProcessManager } = require("./process-manager.cjs");

function pe(file, machine) {
  const data = Buffer.alloc(256);
  data.writeUInt16LE(0x5a4d, 0);
  data.writeUInt32LE(128, 0x3c);
  data.writeUInt32LE(0x4550, 128);
  data.writeUInt16LE(machine, 132);
  fs.writeFileSync(file, data);
}

test("seleciona somente o runtime da arquitetura real da DLL", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pigo-runtime-"));
  const dll = path.join(root, "fbclient.dll");
  pe(dll, 0x14c);
  const python = path.join(root, "python-x86", "python.exe");
  fs.mkdirSync(path.dirname(python));
  fs.writeFileSync(python, "runtime");
  const manager = new ProcessManager(root, root);
  const selected = manager.resolveRuntime({firebird:{clientPath:dll,architecture:"x86"}});
  assert.equal(selected.architecture, "x86");
  assert.equal(selected.python, python);
  assert.throws(() => manager.resolveRuntime({firebird:{clientPath:dll,architecture:"x64"}}), /configuração informa x64/);
});

test("falha claramente quando o runtime requerido está ausente", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pigo-runtime-"));
  const dll = path.join(root, "fbclient.dll");
  pe(dll, 0x8664);
  const manager = new ProcessManager(root, root);
  assert.throws(() => manager.resolveRuntime({firebird:{clientPath:dll}}), /runtime necessário \(x64\)/);
});
test("backoff limita reinícios e exige intervenção",()=>{const manager=new ProcessManager("agent","runtime");for(let i=0;i<5;i++){manager.scheduleRestart(1);if(manager.restartTimer)clearTimeout(manager.restartTimer)}assert.equal(manager.restartCount,5);assert.match(manager.lastError,/OWNER_UNHEALTHY/)});
test("captura owner encerrado antes do IPC com exit code e stderr",async()=>{
  const manager=new ProcessManager("agent","runtime");
  manager.child={pid:77,exitCode:null,pigoStartedAt:Date.now(),pigoStdout:"",pigoStderr:"falha de startup"};
  setTimeout(()=>{manager.lastExit={code:1,pid:77,elapsedMs:20,stdout:"",stderr:"falha de startup"};manager.child=null},20);
  await assert.rejects(
    manager.waitForOwnerReady({waitReady:async()=>{await new Promise(resolve=>setTimeout(resolve,50));throw Object.assign(new Error("offline"),{code:"PIPE_NOT_FOUND"})}},500),
    error=>error.code==="OWNER_EXITED_BEFORE_HANDSHAKE"&&error.exitCode===1&&error.details.stderr==="falha de startup",
  );
});
