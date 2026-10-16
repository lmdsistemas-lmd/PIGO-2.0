const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  ipcMain,
  dialog,
  nativeImage,
  shell,
} = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const cfg = require("./config-manager.cjs");
const detector = require("./firebird-detector.cjs");
const { diagnose } = require("./diagnostics.cjs");
const { ProcessManager } = require("./process-manager.cjs");
const { IpcClient, rawPipeTest, pipePathDiagnostics } = require("./ipc-client.cjs");
const { AgentOwnerResolver } = require("./agent-owner-resolver.cjs");
const { routeAgentCommand } = require("./command-router.cjs");
const { IPC_CONTRACT } = require("./ipc-contract.cjs");
const { runConcurrencyStress } = require("./ipc-concurrency-stress.cjs");
let win, tray;
const dev = !app.isPackaged;
const rendererSandbox = process.env.PIGO_ELECTRON_SANDBOX === "true";
const smokeTest = process.env.PIGO_ELECTRON_SMOKE_TEST === "1";
const rawPipeDiagnostic = process.env.PIGO_RAW_PIPE_DIAGNOSTIC === "1";
const ipcConcurrencyStress = process.env.PIGO_IPC_CONCURRENCY_STRESS === "1";
const preloadPath = dev
  ? path.join(__dirname, "preload.cjs")
  : path.join(process.resourcesPath, "app.asar.unpacked", "electron", "preload.cjs");
const rendererPath = path.join(__dirname, "../dist/index.html");
const agentDir = dev
  ? path.resolve(__dirname, "../../remote-sync-agent")
  : path.join(process.resourcesPath, "agent");
const runtimeRoot = dev
  ? path.resolve(__dirname, "../runtime")
  : path.join(process.resourcesPath, "runtime");
const manager = new ProcessManager(agentDir, runtimeRoot);
const ipcClient = new IpcClient(() => cfg.ipcSecret(), undefined, (message) => appendLog(message));
const ownerResolver = new AgentOwnerResolver(manager, ipcClient);
const ipcCommand = (command, payload = {}, callSite = "main.unspecified") => ipcClient.request(command, payload, 5000, { callSite });
let ownerReadyForPolling = false;
let statusPollInFlight = false;
async function pollOwnerStatus() {
  if (!ownerReadyForPolling || ownerResolver.operationPromise || statusPollInFlight) {
    appendLog(`[IPC_FLOW] event=POLL_SKIPPED owner_ready=${ownerReadyForPolling} owner_operation=${ownerResolver.operationName || "none"} poll_in_flight=${statusPollInFlight}`);
    return;
  }
  statusPollInFlight = true;
  try {
    const owner = await ownerResolver.resolve("react-status-poll");
    if (owner.state === "OWNER_CONFLICT") await manager.stopAndWait();
    if (owner.ipc?.success) win?.webContents.send("agent:status", owner.ipc.data);
  } catch (error) {
    appendLog(`[IPC_FLOW] event=POLL_FAILURE code=${error.code || "unknown"}`);
  } finally {
    statusPollInFlight = false;
  }
}
async function runIpcDiagnostic() {
  const managerState = manager.status();
  const rawConnect = await rawPipeTest();
  const handshakeLogs = [];
  let handshakeResponse = null;
  let handshakeError = null;
  try {
    handshakeResponse = await new IpcClient(() => cfg.ipcSecret(), undefined, (line) => handshakeLogs.push(line)).waitReady(5000, {
      interval: 100,
      ownerPid: managerState.pid || null,
      isOwnerAlive: () => !managerState.pid || manager.child?.pid === managerState.pid,
    });
  } catch (error) {
    handshakeError = { code: error.code, message: error.message, details: error.details || null };
  }
  const ownerPid = handshakeResponse?.data?.pid || managerState.pid || null;
  const ownerAlive = Boolean(handshakeResponse?.success || (managerState.pid && manager.child?.exitCode === null));
  const ownerDetected = Boolean(rawConnect.connected || ownerPid);
  const attempts = handshakeLogs.filter((line) => line.includes("probe attempt=")).length;
  const pathInfo = pipePathDiagnostics();
  return {
    success: rawConnect.connected && handshakeResponse?.success === true,
    code: !ownerDetected ? "OWNER_NOT_RUNNING" : handshakeResponse?.success ? "IPC_DIAGNOSTIC_OK" : handshakeError?.code || "IPC_HANDSHAKE_FAILED",
    electronMainPid: process.pid,
    processType: process.type || "browser",
    execPath: process.execPath,
    resourcesPath: process.resourcesPath,
    appPath: app.getAppPath(),
    nodeVersion: process.versions.node,
    electronVersion: process.versions.electron,
    arch: process.arch,
    pipePath: pathInfo.value,
    pipePathJson: pathInfo.json,
    pipePathLength: pathInfo.length,
    charCodes: pathInfo.charCodes,
    pipeVisible: rawConnect.connected,
    rawConnect: {
      connected: rawConnect.connected,
      code: rawConnect.code,
      durationMs: rawConnect.durationMs,
      nativeError: rawConnect.nativeError,
    },
    handshake: {
      success: handshakeResponse?.success === true,
      attempts,
      protocol: handshakeResponse?.version || null,
      ownerPid,
      ownerInstanceId: handshakeResponse?.data?.instance_id || null,
      lastError: handshakeError,
    },
    owner: { detected: ownerDetected, pid: ownerPid, alive: ownerAlive },
    build: { desktopVersion: app.getVersion(), agentVersion: agentVersion(), ipcProtocolVersion: IPC_CONTRACT.protocol_version },
    retryLog: handshakeLogs,
  };
}
function appendLog(message) {
  fs.mkdirSync(cfg.LOG_DIR, { recursive: true });
  const line = `${new Date().toISOString()} ${message}\n`;
  fs.appendFileSync(path.join(cfg.LOG_DIR, "desktop.log"), line, "utf8");
  win?.webContents.send("agent:log", message);
}
function electronLog(message) {
  appendLog(`[ELECTRON] ${message}`);
}
function agentVersion() {
  try {
    return fs.readFileSync(path.join(agentDir, "agent.py"), "utf8").match(/^AGENT_VERSION\s*=\s*["']([^"']+)/m)?.[1] || "unknown";
  } catch {
    return "unknown";
  }
}
function lastJsonLine(text) {
  for (const line of String(text || "").trim().split(/\r?\n/).reverse()) {
    try { return JSON.parse(line); } catch {}
  }
  return null;
}
function failure(stage, code, message, extra = {}) {
  return { success:false,ok:false,stage,code,message,detailsAvailable:true,...extra };
}
function installationState(configured, activated, owner) {
  if (!configured) return "NOT_CONFIGURED";
  if (!activated) return "NOT_ACTIVATED";
  if (owner.pipeReady) return "OWNER_READY";
  if (owner.state === "OWNER_STARTING") return "OWNER_STARTING";
  if (owner.service?.installed && !owner.service.running) return "ACTIVATED_OWNER_STOPPED";
  return "OWNER_UNAVAILABLE";
}
if (!app.requestSingleInstanceLock()) app.quit();
else app.on("second-instance", () => { if (win) { win.show(); win.focus(); } });
function create() {
  electronLog(`app_packaged=${app.isPackaged}`);
  electronLog(`resources_path=${process.resourcesPath}`);
  electronLog(`app_path=${app.getAppPath()}`);
  electronLog(`preload_path=${preloadPath}`);
  electronLog(`preload_exists=${fs.existsSync(preloadPath)}`);
  electronLog(`sandbox=${rendererSandbox}`);
  electronLog("context_isolation=true node_integration=false");
  electronLog(`platform=${process.platform} arch=${process.arch} electron=${process.versions.electron}`);
  win = new BrowserWindow({
    width: 1120,
    height: 760,
    minWidth: 850,
    minHeight: 620,
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: rendererSandbox,
    },
  });
  let fallbackVisible = false;
  const showFallback = (code) => {
    if (fallbackVisible || win.isDestroyed()) return;
    fallbackVisible = true;
    const logPath = path.join(cfg.LOG_DIR, "desktop.log");
    const html = `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>PIGO Remote Sync</title><style>body{font:16px system-ui;background:#0f172a;color:#e2e8f0;display:grid;place-items:center;min-height:100vh;margin:0}.box{max-width:620px;padding:32px;background:#1e293b;border-radius:16px}button{padding:10px 16px;margin:8px 8px 0 0}</style><main class="box"><h1>PIGO Remote Sync não conseguiu iniciar a interface.</h1><p>Código: <b>${String(code).replace(/[^A-Z0-9_-]/gi, "")}</b></p><p>O diagnóstico técnico foi salvo em:<br><code>${logPath.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</code></p><button onclick="location.href='pigo-restart://renderer'">Reiniciar</button><button onclick="location.href='pigo-logs://open'">Abrir diagnóstico</button></main></html>`;
    win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`).catch(() => {});
    win.show();
  };
  win.webContents.on("will-navigate", (event, url) => {
    if (url === "pigo-restart://renderer") {
      event.preventDefault();
      fallbackVisible = false;
      dev ? win.loadURL("http://localhost:5174") : win.loadFile(rendererPath);
    } else if (url === "pigo-logs://open") {
      event.preventDefault();
      shell.openPath(cfg.LOG_DIR).catch(() => {});
    }
  });
  win.webContents.on("preload-error", (_event, failedPath, error) => {
    electronLog(`preload_error=true preload_path=${failedPath || preloadPath} error_name=${error?.name || "Error"} error_message=${error?.message || "unknown"}`);
    showFallback("PRELOAD_ERROR");
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    electronLog(`render_process_gone=true reason=${details.reason} exit_code=${details.exitCode}`);
    showFallback("RENDER_PROCESS_GONE");
  });
  win.webContents.on("did-fail-load", (_event, code, description, url, isMainFrame) => {
    if (!isMainFrame || code === -3) return;
    electronLog(`did_fail_load=true error_code=${code} description=${description} url=${url}`);
    showFallback("DID_FAIL_LOAD");
  });
  dev
    ? win.loadURL("http://localhost:5174")
    : win.loadFile(rendererPath);
  win.once("ready-to-show", () => win.show());
  win.on("close", (e) => {
    if (!app.quitting) {
      e.preventDefault();
      win.hide();
    }
  });
}
ipcMain.on("renderer:preload-ready", () => {
  electronLog("preload_ready=true");
  if (smokeTest) setTimeout(() => app.exit(0), 100);
});
process.on("uncaughtException", (error) => {
  electronLog(`uncaught_exception=true error_name=${error?.name || "Error"} error_message=${error?.message || "unknown"}`);
  if (smokeTest) app.exit(3);
});
app.on("child-process-gone", (_event, details) => {
  electronLog(`child_process_gone=true type=${details.type} reason=${details.reason} exit_code=${details.exitCode}`);
});
function trayMenu() {
  tray = new Tray(nativeImage.createEmpty());
  tray.setToolTip("PIGO Remote Sync");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Abrir", click: () => win.show() },
      { label: "Sincronizar agora", click: () => ipcCommand("sync-now", {}, "tray.sync-now").catch(() => {}) },
      { label: "Pausar", click: () => ipcCommand("pause", {}, "tray.pause").catch(() => {}) },
      { type: "separator" },
      {
        label: "Sair",
        click: () => {
          app.quitting = true;
          manager.stop();
          app.quit();
        },
      },
    ]),
  );
}
app.whenReady().then(async () => {
  create();
  if (ipcConcurrencyStress) {
    const result = { ...(await runConcurrencyStress(100)), nodeVersion: process.versions.node, electronVersion: process.versions.electron, arch: process.arch, appVersion: app.getVersion() };
    if (process.env.PIGO_IPC_CONCURRENCY_STRESS_OUTPUT) fs.writeFileSync(process.env.PIGO_IPC_CONCURRENCY_STRESS_OUTPUT, JSON.stringify(result, null, 2), "utf8");
    return app.exit(result.success ? 0 : 5);
  }
  if (rawPipeDiagnostic) {
    const diagnostic = await runIpcDiagnostic();
    electronLog(`raw_pipe_test=${JSON.stringify(diagnostic)}`);
    if (process.env.PIGO_RAW_PIPE_DIAGNOSTIC_OUTPUT) fs.writeFileSync(process.env.PIGO_RAW_PIPE_DIAGNOSTIC_OUTPUT, JSON.stringify(diagnostic, null, 2), "utf8");
    return app.exit(diagnostic.rawConnect.connected ? 0 : 4);
  }
  if (smokeTest) setTimeout(() => app.exit(2), 15000);
  trayMenu();
  if (cfg.configured() && cfg.activated()) {
    const owner = await ownerResolver.ensureDesktopOwner();
    ownerReadyForPolling = Boolean(owner.pipeReady);
  }
  app.setLoginItemSettings({
    openAtLogin: cfg.load().options?.startWithWindows !== false,
  });
  setInterval(pollOwnerStatus, 1000);
});
ipcMain.handle("ipc:raw-pipe-test", runIpcDiagnostic);
app.on("window-all-closed", () => {});
manager.on("status", (s) => win?.webContents.send("agent:status", s));
manager.on("log", (line) => appendLog(String(line).trimEnd()));
ipcMain.handle("initialize", async () => {
  const configured = cfg.configured();
  const activated = cfg.activated();
  const owner = ownerResolver.operationPromise
    ? await ownerResolver.operationPromise
    : await ownerResolver.resolve("react-initialize");
  return {
    config: cfg.load(),
    configured,
    activated,
    installationState: installationState(configured, activated, owner),
    credentials: cfg.credentialStatus(),
    owner,
    service: {
      installed: owner.service.installed,
      running: owner.service.running,
      ownerProcess: Boolean(owner.pid),
      pipeReady: owner.pipeReady,
      pid: owner.pid,
      instanceId: owner.instanceId,
      lastError: owner.lastError,
    },
    build: {
      desktopVersion: app.getVersion(),
      agentVersion: agentVersion(),
      ipcProtocolVersion: IPC_CONTRACT.protocol_version,
      vaultVersion: cfg.credentialStatus().version,
    },
    status: owner.ipc?.data || manager.status(),
  };
});
ipcMain.handle("config:save", async (_, c) => {
  const clean = cfg.save(c);
  app.setLoginItemSettings({
    openAtLogin: clean.options?.startWithWindows !== false,
  });
  const owner = await ownerResolver.resolve();
  if (["DESKTOP_OWNER", "SERVICE_OWNER"].includes(owner.state)) await ipcCommand("reload-config", {}, "config-save.reload").catch(() => {});
  return clean;
});
ipcMain.handle("database:select", async () => {
  const x = await dialog.showOpenDialog(win, {
    properties: ["openFile"],
    filters: [
      { name: "Bancos Firebird", extensions: ["fdb", "gdb"] },
      { name: "Todos os arquivos", extensions: ["*"] },
    ],
  });
  return x.canceled ? null : x.filePaths[0];
});
ipcMain.handle("schema:export", async (_, config) => {
  try {
    cfg.save(config);
    const result = await manager.execute(["--export-schema"]);
    const data = lastJsonLine(result.stdout || "");
    if (result.code === 0 && data?.success) return data;
    return failure("schema-export", data?.code || "SCHEMA_EXPORT_FAILED", data?.message || "Não foi possível exportar a estrutura do ERP.");
  } catch {
    return failure("schema-export", "SCHEMA_EXPORT_FAILED", "Verifique a configuração e a conexão Firebird.");
  }
});
ipcMain.handle("firebird:detect", async () => ({
  installations: await detector.detect(),
}));
ipcMain.handle("diagnose", async (_, c) => {
  cfg.save(c);
  const preflight = await diagnose(c);
  if (!preflight.ok) return preflight;
  const activeOwner = await ownerResolver.resolve();
  if (["DESKTOP_OWNER", "SERVICE_OWNER"].includes(activeOwner.state)) {
    const response = await ipcCommand("diagnose", {}, "diagnostic.start");
    if (!response.success) return {ok:false,steps:preflight.steps,message:response.code};
    let ownerStatus = response.data;
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      const current = await ipcCommand("status", {}, "diagnostic.status-poll");
      ownerStatus = current.data;
      if (ownerStatus?.state !== "DIAGNOSING" && !ownerStatus?.pending_command && ownerStatus?.last_diagnostic) break;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    const cash = ownerStatus?.last_diagnostic?.cash_register;
    const cashSteps = (cash?.tables || []).map((table) => ({
      label: `Caixa · ${table.table}`,
      ok: table.compatible,
      message: !table.found
        ? "Tabela não encontrada nesta versão do ERP"
        : !table.compatible
          ? `Campos obrigatórios ausentes: ${table.missing_required_fields.join(", ")}`
          : `${table.records ?? 0} registros · ${table.first_date || "sem primeira data"} → ${table.last_date || "sem última data"}`,
    }));
    return {
      ok: ownerStatus?.last_diagnostic?.success === true,
      steps: [...preflight.steps, ...cashSteps],
      cashRegister: cash,
      message: cash ? "Diagnóstico do Firebird e do módulo Caixa concluído." : "Diagnóstico concluído sem informações do módulo Caixa.",
    };
  }
  const connection = await manager.diagnose();
  let payload = null;
  try { payload = JSON.parse(String(connection.stdout || "").trim().split(/\r?\n/).at(-1)); } catch {}
  const connectionSteps = (payload?.steps || []).map((item) => ({label:item.name,ok:item.ok,message:item.detail}));
  return {ok:Boolean(connection.ok && payload?.success),steps:[...preflight.steps,...connectionSteps],message:payload?.success?"A conexão com o Firebird foi concluída com sucesso.":"O Firebird foi localizado, mas a conexão real falhou."};
});
async function validateWithCurrentToken(versions) {
  try {
    appendLog("[OWNER] start_requested=true activation_mode=reuse-existing-token");
    const owner = await ownerResolver.startConfiguredOwner();
    appendLog(`[OWNER] owner_type=${owner.ownerType || "desktop"} process_started=${Boolean(owner.pid)} pid=${owner.pid || "none"}`);
    appendLog(`[IPC] pipe_ready=${owner.pipeReady}`);
    let diagnostic = await ipcCommand("diagnose", {}, "activation-existing.diagnose");
    if (!diagnostic.success && diagnostic.code === "OWNER_BUSY") {
      const idleDeadline = Date.now() + 30000;
      while (Date.now() < idleDeadline) {
        const current = await ipcCommand("status", {}, "activation-existing.wait-idle");
        if (current.data?.state === "IDLE" && !current.data?.pending_command) break;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      diagnostic = await ipcCommand("diagnose", {}, "activation-existing.retry-diagnose");
    }
    if (!diagnostic.success) return failure("diagnose",diagnostic.code || "DIAGNOSE_REJECTED","O proprietário rejeitou o diagnóstico da credencial existente.",{status:diagnostic.data,versions});
    const deadline = Date.now() + 30000;
    let status = diagnostic.data;
    while (Date.now() < deadline) {
      const current = await ipcCommand("status", {}, "activation-existing.status-poll");
      status = current.data;
      if (!["DIAGNOSING", "STARTING", "SYNCING", "WRITING"].includes(status?.state) && !status?.pending_command && status?.last_diagnostic) break;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    const authenticated = status?.last_diagnostic?.authenticated === true && status?.last_diagnostic?.tenant_resolved === true && status?.last_result === "success";
    appendLog(`[DIAGNOSTICO] existing_token=true authenticated=${authenticated} tenant_resolved=${Boolean(status?.last_diagnostic?.tenant_resolved)} code=${status?.last_diagnostic?.code || status?.last_error_code || "unknown"}`);
    if (!authenticated) {
      const code = status?.last_diagnostic?.code || status?.last_error_code || "EXISTING_TOKEN_VALIDATION_FAILED";
      return failure("validate-existing-token",code,"Não foi possível validar a credencial de sincronização existente.",{retryable:Boolean(status?.last_diagnostic?.retryable),status,versions});
    }
    return {success:true,ok:true,stage:"complete",code:"EXISTING_ACTIVATION_REUSED",message:"A credencial existente foi validada; não foi necessária uma nova ativação.",detailsAvailable:true,tokenPersisted:true,ownerStarted:Boolean(owner.pid),pipeReady:Boolean(owner.pipeReady),authenticated:true,reusedExistingToken:true,versions,owner:{owner_type:owner.ownerType,pid:owner.pid,instance_id:owner.instanceId,state:owner.state,pipe_ready:owner.pipeReady},status};
  } catch (error) {
    return failure(error.code === "OWNER_NOT_AVAILABLE" ? "wait-ipc" : "start-owner",error.code || "OWNER_START_FAILED",error.message,{exitCode:error.exitCode,stdout:error.details?.stdout,stderr:error.details?.stderr,versions});
  }
}
async function handleActivation(options = {}) {
  let forceReactivation = Boolean(options.reactivate);
  const versions = {desktopVersion:app.getVersion(),agentVersion:agentVersion(),ipcProtocolVersion:IPC_CONTRACT.protocol_version};
  appendLog(`[ACTIVATION] command_started=true desktop_version=${versions.desktopVersion} agent_version=${versions.agentVersion} ipc_protocol_version=${versions.ipcProtocolVersion}`);
  if (!cfg.configured()) return failure("activate","CONFIG_NOT_FOUND","A configuração precisa ser salva antes da ativação.");
  const credentials = cfg.credentialStatus();
  appendLog(`[CREDENTIALS] config_found=${credentials.configFound} vault_found=${credentials.storeFound} vault_version=${credentials.version} license_api_key_present=${credentials.licenseKeyPresent} firebird_password_present=${credentials.firebirdPasswordPresent} installation_accessible=${credentials.installationAccessible}`);
  if (!credentials.configFound) return failure("activate","CONFIG_NOT_FOUND","O arquivo config.json não foi encontrado.");
  if (!credentials.licenseKeyPresent) return failure("activate","LICENSE_KEY_MISSING","A chave de licença não foi salva no cofre.");
  if (!credentials.firebirdPasswordPresent) return failure("activate","FIREBIRD_PASSWORD_MISSING","A senha do Firebird não foi salva no cofre.");
  if (!credentials.installationAccessible) return failure("activate","INSTALLATION_FILE_UNREADABLE","O arquivo installation.json não está acessível.");
  try {
    await ownerResolver.stopOwner();
  } catch (error) {
    return failure("start-owner",error.code || "OWNER_STOP_FAILED",error.message);
  }
  if (credentials.remoteSyncTokenReadable && !options.reactivate) {
    appendLog("[ACTIVATION] existing_token=true action=validate-before-activate");
    const existing = await validateWithCurrentToken(versions);
    if (existing.success) return existing;
    const invalidCredentialCodes = new Set(["INVALID_API_KEY","REMOTE_TOKEN_INVALID","INSTALLATION_BLOCKED","SYNC_NOT_ALLOWED","LICENSE_EXPIRED"]);
    if (existing.retryable || !invalidCredentialCodes.has(existing.code)) {
      appendLog(`[ACTIVATION] remote_call_skipped=true existing_token_code=${existing.code} retryable=${Boolean(existing.retryable)}`);
      return existing;
    }
    appendLog(`[ACTIVATION] existing_token_valid=false code=${existing.code} action=activate`);
    if (existing.code === "INSTALLATION_BLOCKED") forceReactivation = true;
    await ownerResolver.stopOwner();
  }
  let activation;
  try {
    activation = await manager.execute([forceReactivation ? "--reactivate" : "--activate"]);
  } catch (error) {
    return failure("activate","ACTIVATION_PROCESS_START_FAILED",error.message);
  }
  const agentResult = lastJsonLine(activation.stdout);
  appendLog(`[ACTIVATION] process_pid=${activation.pid} exit_code=${activation.code} agent_path=${activation.agentPath} runtime_path=${activation.runtimePath} data_dir=${activation.dataDir}`);
  appendLog(`[ACTIVATION] api_status=${agentResult?.api_status ?? "unknown"} api_code=${agentResult?.code || "unknown"} token_received=${Boolean(agentResult?.token_received)} token_saved=${Boolean(agentResult?.token_saved)}`);
  if (!activation.ok) {
    const code = agentResult?.code === "ACTIVATION_REMOTE_TIMEOUT" ? "ACTIVATION_REMOTE_TIMEOUT" : "ACTIVATION_PROCESS_FAILED";
    return failure("activate",code,agentResult?.message || "O agente recusou ou não concluiu a ativação.",{retryable:Boolean(agentResult?.retryable),exitCode:activation.code,agentCode:agentResult?.code,stdout:activation.stdout,stderr:activation.stderr,versions,existingTokenPreserved:credentials.remoteSyncTokenReadable});
  }
  const persisted = cfg.credentialStatus();
  appendLog(`[CREDENTIALS] remote_sync_token_present=${persisted.remoteSyncTokenPresent} remote_sync_token_readable=${persisted.remoteSyncTokenReadable}`);
  if (!persisted.remoteSyncTokenPresent || !persisted.remoteSyncTokenReadable) return failure("persist-token","TOKEN_NOT_PERSISTED","A licença foi validada, mas a credencial de sincronização não foi persistida ou não pôde ser descriptografada.",{exitCode:activation.code,stdout:activation.stdout,stderr:activation.stderr,versions});
  try {
    appendLog("[OWNER] start_requested=true");
    const serviceBeforeStart = ownerResolver.serviceState();
    appendLog(`[OWNER] service_installed=${serviceBeforeStart.installed} service_name=${serviceBeforeStart.name} service_status=${serviceBeforeStart.status} service_pid=${serviceBeforeStart.pid || "none"} service_path=${serviceBeforeStart.executablePath || "none"}`);
    appendLog(`[OWNER] selected=${serviceBeforeStart.installed ? "service" : "desktop"} reason=${serviceBeforeStart.installed ? "service-installed" : "service-not-installed"}`);
    const owner = await ownerResolver.startConfiguredOwner();
    appendLog(`[OWNER] owner_type=${owner.ownerType || (owner.service?.installed && !owner.fallbackCode ? "service" : "desktop")} reason=${owner.selectedReason || "resolved"} process_started=${Boolean(owner.pid)} process_alive=${Boolean(owner.pid)} pid=${owner.pid || "none"} instance_id=${owner.instanceId || "none"}`);
    appendLog(`[IPC] pipe_ready=${owner.pipeReady}`);
    const initial = await ipcCommand("status", {}, "activation.status-initial");
    let diagnostic = await ipcCommand("diagnose", {}, "activation.diagnose");
    if (!diagnostic.success && diagnostic.code === "OWNER_BUSY") {
      const idleDeadline = Date.now() + 30000;
      while (Date.now() < idleDeadline) {
        const current = await ipcCommand("status", {}, "activation.wait-idle");
        if (current.data?.state === "IDLE" && !current.data?.pending_command) break;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      diagnostic = await ipcCommand("diagnose", {}, "activation.retry-diagnose");
    }
    if (!diagnostic.success) return failure("diagnose",diagnostic.code || "DIAGNOSE_REJECTED","O proprietário rejeitou o diagnóstico autenticado.",{status:diagnostic.data,versions});
    const deadline = Date.now() + 30000;
    let status = initial.data;
    while (Date.now() < deadline) {
      const current = await ipcCommand("status", {}, "activation.status-poll");
      status = current.data;
      if (!["DIAGNOSING", "STARTING", "SYNCING", "WRITING"].includes(status?.state) && !status?.pending_command && status?.last_diagnostic) break;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    const authenticated = status?.last_diagnostic?.authenticated === true && status?.last_diagnostic?.tenant_resolved === true && status?.last_result === "success";
    appendLog(`[DIAGNOSTICO] authenticated=${authenticated}`);
    if (!authenticated) return failure("diagnose",status?.last_error_code || "AUTHENTICATED_DIAGNOSIS_FAILED","A credencial foi salva, mas o diagnóstico autenticado falhou.",{status,versions});
    return {success:true,ok:true,stage:"complete",code:"ACTIVATION_COMPLETED",message:"Ativação e diagnóstico concluídos.",detailsAvailable:true,tokenPersisted:true,ownerStarted:Boolean(owner.pid),pipeReady:Boolean(owner.pipeReady),authenticated:true,versions,owner:{owner_type:owner.ownerType,pid:owner.pid,instance_id:owner.instanceId,state:owner.state,pipe_ready:owner.pipeReady},status};
  } catch (error) {
    const waitCodes = new Set(["OWNER_NOT_AVAILABLE","OWNER_PIPE_TIMEOUT","SERVICE_RUNNING_WITHOUT_IPC","PIPE_NOT_FOUND","PIPE_ACCESS_DENIED","PIPE_CONNECTION_RESET","PIPE_CONNECT_TIMEOUT","PIPE_HANDSHAKE_TIMEOUT","IPC_PROTOCOL_MISMATCH","IPC_AUTH_FAILED","IPC_RESPONSE_INVALID"]);
    const stage = waitCodes.has(error.code) ? "wait-ipc" : "start-owner";
    appendLog(`[OWNER] process_started=false process_alive=false code=${error.code || "OWNER_START_FAILED"} exit_code=${error.exitCode ?? error.details?.code ?? "unknown"} stderr_available=${Boolean(error.details?.stderr)}`);
    if (stage === "wait-ipc") appendLog("[IPC] pipe_ready=false");
    return failure(stage,error.code || "OWNER_START_FAILED",error.code === "OWNER_NOT_AVAILABLE" ? "A licença foi validada, mas o serviço de sincronização ainda não está disponível." : error.message,{exitCode:error.exitCode ?? error.details?.code,stdout:error.details?.stdout,stderr:error.details?.stderr,ownerPid:error.details?.ownerPid,ownerAlive:error.details?.ownerAlive,lastProbeCode:error.details?.lastProbeCode,pipePath:error.details?.pipePath,ownerDetails:error.details,versions});
  }
}
ipcMain.handle("agent:activate", async (_, options = {}) => {
  ownerReadyForPolling = false;
  appendLog("[IPC_FLOW] event=POLL_BLOCKED call_site=activation");
  const result = await handleActivation(options);
  ownerReadyForPolling = Boolean(result?.success && result?.pipeReady);
  appendLog(`[IPC_FLOW] event=POLL_RELEASED call_site=activation owner_ready=${ownerReadyForPolling}`);
  return result;
});
ipcMain.handle("agent:command", async (_, command) => {
  if (command === "logs") {
    const response = await ipcCommand("status", {}, "renderer.logs-status");
    return response.data || {state:response.state,error:response.success?null:response.code};
  }
  try {
    const response = await routeAgentCommand(command, {
      executeBootstrap: (args) => manager.execute(args),
      executeIpc: (name) => ipcCommand(name, {}, `renderer.agent-command.${name}`),
    });
    return response?.data || response;
  } catch (error) {
    return {success:false,code:error.code || "AGENT_COMMAND_FAILED",message:error.code === "OWNER_NOT_AVAILABLE" ? "O serviço de sincronização ainda não está disponível." : error.message};
  }
});
ipcMain.handle("logs:read", () => {
  const files = ["desktop.log", "agent.log"].map((name) => path.join(cfg.LOG_DIR, name)).filter((file) => fs.existsSync(file));
  return files.flatMap((file) => fs.readFileSync(file, "utf8").split(/\r?\n/)).slice(-300);
});
ipcMain.handle("config:import", async () => {
  const known = path.join(agentDir, ".env");
  let file = fs.existsSync(known) ? known : null;
  if (!file) {
    const x = await dialog.showOpenDialog(win, {
      filters: [
        { name: "Configuração antiga", extensions: ["env"] },
        { name: "Todos", extensions: ["*"] },
      ],
    });
    file = x.canceled ? null : x.filePaths[0];
  }
  return file ? cfg.importEnv(file) : null;
});
