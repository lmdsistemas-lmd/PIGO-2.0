const { execFileSync } = require("node:child_process");

const SERVICE_NAME = "PIGORemoteSync";
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

class AgentOwnerResolver {
  constructor(manager, client) {
    this.manager = manager;
    this.client = client;
    this.lastError = null;
    this.operationPromise = null;
    this.operationName = null;
  }
  runOwnerOperation(name, operation) {
    if (this.operationPromise) return this.operationPromise;
    this.operationName = name;
    this.operationPromise = Promise.resolve().then(operation).finally(() => {
      this.operationPromise = null;
      this.operationName = null;
    });
    return this.operationPromise;
  }
  serviceState() {
    if (process.platform !== "win32") return { installed: false, name: SERVICE_NAME, status: "NOT_FOUND", running: false, pid: null };
    try {
      const text = execFileSync("sc.exe", ["queryex", SERVICE_NAME], { encoding: "utf8", windowsHide: true });
      let configuration = "";
      try { configuration = execFileSync("sc.exe", ["qc", SERVICE_NAME], { encoding: "utf8", windowsHide: true }); } catch {}
      const status = text.match(/STATE\s*:\s*\d+\s+(\w+)/)?.[1] || "UNKNOWN";
      return {
        installed: true,
        name: SERVICE_NAME,
        status,
        running: status === "RUNNING",
        pid: Number(text.match(/PID\s*:\s*(\d+)/)?.[1] || 0) || null,
        executablePath: configuration.match(/BINARY_PATH_NAME\s*:\s*(.+)/)?.[1]?.trim() || null,
        account: configuration.match(/SERVICE_START_NAME\s*:\s*(.+)/)?.[1]?.trim() || null,
      };
    } catch {
      return { installed: false, name: SERVICE_NAME, status: "NOT_FOUND", running: false, pid: null, executablePath: null, account: null };
    }
  }
  serviceCommand(command) {
    try {
      execFileSync("sc.exe", [command, SERVICE_NAME], { encoding: "utf8", windowsHide: true });
      this.lastError = null;
      return true;
    } catch (error) {
      this.lastError = error.message;
      return false;
    }
  }
  async waitForService(running, timeout = 15000) {
    const end = Date.now() + timeout;
    let state = this.serviceState();
    while (Date.now() < end && state.running !== running) {
      await delay(250);
      state = this.serviceState();
    }
    return state;
  }
  async resolve(callSite="owner-resolver.resolve") {
    const service = this.serviceState();
    let ipc = null;
    try {
      ipc = await this.client.request("status", {}, 1000, { callSite });
    } catch (error) {
      this.lastError = error.code || error.message;
    }
    const desktop = Boolean(this.manager.child);
    const ipcOwner = ipc?.data?.owner;
    const desktopPid = this.manager.child?.pid || (ipcOwner === "desktop" ? ipc?.data?.pid : null);
    let state = "OWNER_UNAVAILABLE";
    if (service.running && (desktop || ipcOwner === "desktop")) state = "OWNER_CONFLICT";
    else if (service.running) state = ipc?.success && ipcOwner === "service" ? "SERVICE_OWNER" : "OWNER_STARTING";
    else if (ipc?.success && ipcOwner === "desktop") state = "DESKTOP_OWNER";
    else if (desktop) state = "OWNER_STARTING";
    return {
      state, service, servicePid: service.pid, desktopPid,
      pipeReady: Boolean(ipc?.success),
      pid: ipc?.data?.pid || service.pid || desktopPid || null,
      instanceId: ipc?.data?.instance_id || null,
      ownerType: ipc?.data?.owner || null,
      ipc, lastError: this.lastError,
    };
  }
  async stopOwner() {
    await this.manager.stopAndWait();
    const service = this.serviceState();
    if (service.running) {
      if (!this.serviceCommand("stop")) throw Object.assign(new Error("Não foi possível parar o serviço proprietário."), { code: "SERVICE_STOP_FAILED" });
      const stopped = await this.waitForService(false);
      if (stopped.running) throw Object.assign(new Error("O serviço proprietário não parou dentro do prazo."), { code: "SERVICE_STOP_TIMEOUT" });
    }
    return this.resolve();
  }
  async performStartConfiguredOwner() {
    const service = this.serviceState();
    let fallbackCode = null;
    if (service.installed) {
      const startAccepted = service.running || this.serviceCommand("start");
      if (!startAccepted) fallbackCode = "SERVICE_START_FAILED";
      const started = startAccepted ? await this.waitForService(true) : service;
      if (!started.running) fallbackCode ||= "SERVICE_START_TIMEOUT";
      if (started.running) {
        try {
          const ipc = await this.client.waitReady(10000, { callSite: "start-owner.service-readiness" });
          return { ...(await this.resolve()), ipc, selectedReason: "service-installed" };
        } catch {
          fallbackCode = "SERVICE_RUNNING_WITHOUT_IPC";
          if (!this.serviceCommand("stop") || (await this.waitForService(false)).running) {
            throw Object.assign(new Error("O serviço está ativo, mas não abriu a comunicação local e não pôde ser interrompido com segurança."), { code: "SERVICE_RUNNING_WITHOUT_IPC", details: { service: started } });
          }
        }
      }
    }
    if (!this.manager.child) {
      const status = this.manager.start();
      if (!status.running) throw Object.assign(new Error(status.error || "O proprietário desktop não iniciou."), { code: "DESKTOP_OWNER_START_FAILED", details: this.manager.lastExit });
    }
    const ipc = this.manager.waitForOwnerReady
      ? await this.manager.waitForOwnerReady(this.client, 20000, "start-owner.desktop-readiness")
      : await this.client.waitReady(20000);
    return { ...(await this.resolve()), ipc, selectedReason: fallbackCode ? `desktop-fallback:${fallbackCode}` : "service-not-installed", fallbackCode };
  }
  startConfiguredOwner() {
    return this.runOwnerOperation("start-configured-owner", () => this.performStartConfiguredOwner());
  }
  async performEnsureDesktopOwner() {
    const current = await this.resolve();
    if (current.state === "OWNER_CONFLICT") {
      await this.manager.stopAndWait();
      return this.resolve();
    }
    if (current.state === "SERVICE_OWNER") return current;
    if (current.service.running) {
      await this.client.waitReady(20000, { callSite: "ensure-owner.service-readiness" });
      return this.resolve();
    }
    if (current.service.installed) return { ...current, requiresConfirmation: true };
    if (!this.manager.child) this.manager.start();
    if (this.manager.waitForOwnerReady) await this.manager.waitForOwnerReady(this.client, 20000, "ensure-owner.desktop-readiness");
    else await this.client.waitReady(20000);
    return this.resolve();
  }
  ensureDesktopOwner() {
    return this.runOwnerOperation("ensure-desktop-owner", () => this.performEnsureDesktopOwner());
  }
}

module.exports = { AgentOwnerResolver, SERVICE_NAME };
