const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const EventEmitter = require("node:events");
const config = require("./config-manager.cjs");
const { peArchitecture } = require("./firebird-detector.cjs");
const { IPC_CONTRACT } = require("./ipc-contract.cjs");
class ProcessManager extends EventEmitter {
  constructor(agentDir, runtimeRoot) {
    super();
    this.agentDir = agentDir;
    this.runtimeRoot = runtimeRoot;
    this.child = null;
    this.paused = false;
    this.lastSync = null;
    this.lastError = null;
    this.expectedStop = false;
    this.restartCount = 0;
    this.restartTimer = null;
    this.lastExit = null;
    this.startingOwner = false;
  }
  resolveRuntime(c) {
    const dll = c.firebird?.clientPath;
    if (!dll || !fs.existsSync(dll))
      throw new Error("A DLL do Firebird não foi localizada.");
    const detected = peArchitecture(dll);
    if (c.firebird?.architecture && c.firebird.architecture !== detected)
      throw new Error(
        `A DLL selecionada é ${detected}, mas a configuração informa ${c.firebird.architecture}.`,
      );
    const python = path.join(
      this.runtimeRoot,
      detected === "x86" ? "python-x86" : "python-x64",
      "python.exe",
    );
    if (!fs.existsSync(python))
      throw new Error(
        `O runtime necessário (${detected}) não foi instalado corretamente.`,
      );
    return { python, architecture: detected, dll };
  }
  run(command = [], wait = false) {
    if (this.child) throw new Error("O agente já está em execução.");
    const selected = this.resolveRuntime(config.load());
    this.emit(
      "log",
      `[RUNTIME] architecture=${selected.architecture} python=${path.basename(path.dirname(selected.python))} client=${path.basename(selected.dll)}\n`,
    );
    const runtimeDir = path.dirname(selected.python);
    const launcher =
      "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name='__main__')";
    const child = spawn(
      selected.python,
      [
        "-c",
        launcher,
        this.agentDir,
        path.join(this.agentDir, "agent.py"),
        ...command,
      ],
      {
        cwd: this.agentDir,
        windowsHide: true,
        env: {
          ...process.env,
          PATH: `${runtimeDir};${path.join(runtimeDir, "Lib", "site-packages", "pywin32_system32")};${process.env.PATH || ""}`,
          PIGO_REMOTE_SYNC_DATA_DIR: config.DATA_DIR,
          PYTHONUNBUFFERED: "1",
          PYTHONUTF8: "1",
          PYTHONIOENCODING: "utf-8",
        },
      },
    );
    child.pigoMetadata = {
      agentPath: path.join(this.agentDir, "agent.py"),
      runtimePath: selected.python,
      architecture: selected.architecture,
      dataDir: config.DATA_DIR,
    };
    child.pigoStartedAt = Date.now();
    child.pigoStdout = "";
    child.pigoStderr = "";
    if (!wait) this.child = child;
    child.stdout?.on("data", (d) => {child.pigoStdout+=String(d);this.emit("log", String(d))});
    child.stderr?.on("data", (d) => {child.pigoStderr+=String(d);this.emit("log", String(d))});
    child.on("exit", (code) => {
      this.lastExit = {code,pid:child.pid,elapsedMs:Date.now()-child.pigoStartedAt,stdout:child.pigoStdout,stderr:child.pigoStderr,...child.pigoMetadata};
      if (this.child === child) this.child = null;
      if (!wait && !this.expectedStop && !this.startingOwner && code !== 0) this.scheduleRestart(code);
      this.emit("status", this.status(code));
    });
    return child;
  }
  execute(command) {
    return new Promise((resolve, reject) => {
      let stdout = "";
      let stderr = "";
      let child;
      try {
        child = this.run(command, true);
      } catch (e) {
        this.lastError = e.message;
        return reject(e);
      }
      child.stdout?.on("data", (data) => (stdout += String(data)));
      child.stderr?.on("data", (data) => (stderr += String(data)));
      child.on("exit", (code) => resolve({ ok: code === 0, code, pid: child.pid, stdout, stderr, ...child.pigoMetadata }));
      child.on("error", reject);
    });
  }
  start() {
    try {
      this.expectedStop = false;
      this.startingOwner = true;
      if (!this.child) this.run(["--owner", "--pipe-name", IPC_CONTRACT.pipe_name]);
      this.lastError = null;
    } catch (e) {
      this.lastError = e.message;
    }
    return this.status();
  }
  async waitForOwnerReady(client, timeout=20000, callSite="process-manager.wait-owner-ready") {
    const started = Date.now();
    const child = this.child;
    if (!child) throw Object.assign(new Error("O processo proprietário não foi iniciado."),{code:"OWNER_START_FAILED"});
    try {
      const response = await client.waitReady(timeout, {
        callSite,
        ownerPid: child.pid,
        isOwnerAlive: () => this.child === child && child.exitCode === null,
      });
      this.startingOwner = false;
      return response;
    } catch (error) {
      this.startingOwner = false;
      const ownerAlive = this.child === child && child.exitCode === null;
      const exit = this.lastExit || {code:child.exitCode,pid:child.pid,elapsedMs:Date.now()-child.pigoStartedAt,stdout:child.pigoStdout,stderr:child.pigoStderr,...child.pigoMetadata};
      if (!ownerAlive) {
        const dependencyMissing=/IPC_DEPENDENCY_MISSING/.test(`${exit.stdout}\n${exit.stderr}`);
        const lockConflict=/OWNER_LOCKED_BY_ACTIVE_PROCESS/.test(`${exit.stdout}\n${exit.stderr}`);
        const code=dependencyMissing?"IPC_DEPENDENCY_MISSING":lockConflict?"OWNER_LOCK_CONFLICT":"OWNER_EXITED_BEFORE_HANDSHAKE";
        throw Object.assign(new Error("O proprietário encerrou antes de concluir o handshake IPC."),{code,exitCode:exit.code,details:exit});
      }
      error.details = {
        ...(error.details || {}), ownerPid:child.pid, ownerAlive:true,
        elapsedMs:Date.now()-started, stdout:child.pigoStdout, stderr:child.pigoStderr,
        ...child.pigoMetadata,
      };
      throw error;
    }
  }
  stop() {
    this.expectedStop = true;
    if (this.restartTimer) clearTimeout(this.restartTimer);
    this.child?.kill();
    this.child = null;
    return this.status();
  }
  stopAndWait() {
    const child = this.child;
    if (!child) return Promise.resolve(this.status());
    this.expectedStop = true;
    return new Promise((resolve) => {
      child.once("exit", () => resolve(this.status()));
      child.kill();
      this.child = null;
    });
  }
  scheduleRestart(exitCode) {
    const delays = [2000, 5000, 15000, 30000];
    this.restartCount += 1;
    this.lastError = `Proprietário encerrou com código ${exitCode}; tentativa ${this.restartCount}.`;
    if (this.restartCount > delays.length) {
      this.lastError = "OWNER_UNHEALTHY: limite de reinícios atingido.";
      return;
    }
    this.restartTimer = setTimeout(() => { this.restartTimer = null; this.start(); }, delays[this.restartCount - 1]);
  }
  pause() {
    this.paused = true;
    this.stop();
    return this.status();
  }
  resume() {
    this.paused = false;
    return this.start();
  }
  restart() {
    this.stop();
    return this.start();
  }
  async syncNow() {
    const resumeAfter = Boolean(this.child);
    if (resumeAfter) await this.stopAndWait();
    try {
      const x = await this.execute(["--sync-once"]);
      if (x.ok) this.lastSync = new Date().toLocaleString("pt-BR");
      if (resumeAfter) this.start();
      return this.status(x.code);
    } catch {
      if (resumeAfter) this.start();
      return this.status(1);
    }
  }
  async diagnose() {
    const resumeAfter = Boolean(this.child);
    if (resumeAfter) await this.stopAndWait();
    try {
      const result = await this.execute(["--test-firebird"]);
      if (resumeAfter) this.start();
      return result;
    } catch {
      if (resumeAfter) this.start();
      return { ok: false, error: this.lastError };
    }
  }
  status(code) {
    return {
      running: Boolean(this.child),
      paused: this.paused,
      pid: this.child?.pid,
      state: this.paused
        ? "Pausado"
        : this.child
          ? "Ativo"
          : this.lastError
            ? "Erro de runtime"
            : code && code !== 0
              ? "Erro"
              : "Parado",
      lastSync: this.lastSync,
      error: this.lastError,
      restartCount: this.restartCount,
    };
  }
}
module.exports = { ProcessManager };
