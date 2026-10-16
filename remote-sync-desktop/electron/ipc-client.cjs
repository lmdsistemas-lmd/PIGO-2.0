const net = require("node:net");
const crypto = require("node:crypto");
const { IPC_CONTRACT, PIPE_NAME } = require("./ipc-contract.cjs");

function pipePathDiagnostics(pipePath = PIPE_NAME) {
  return {
    type: typeof pipePath,
    value: pipePath,
    json: JSON.stringify(pipePath),
    length: pipePath?.length,
    charCodes: Array.from(pipePath || "").map((character) => character.charCodeAt(0)),
  };
}

function nativeErrorDetails(error) {
  if (!error) return null;
  return {
    name: error.name,
    message: error.message,
    code: error.code,
    errno: error.errno,
    syscall: error.syscall,
    address: error.address,
    stack: error.stack,
  };
}

function authText(message) {
  return [message.version, message.request_id, message.timestamp, message.nonce, message.command, stable(message.payload || {})].join("|");
}

function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

function ipcError(code, message, details = {}) {
  const error = new Error(message || code);
  error.code = code;
  error.details = details;
  return error;
}

function mapPipeError(error, details = {}) {
  const codes = {
    ENOENT: "PIPE_NOT_FOUND",
    EACCES: "PIPE_ACCESS_DENIED",
    ECONNRESET: "PIPE_CONNECTION_RESET",
    ECONNREFUSED: "PIPE_NOT_FOUND",
  };
  return ipcError(codes[error?.code] || error?.code || "PIPE_CONNECTION_FAILED", "Não foi possível conectar à comunicação local.", { ...details, nativeCode: error?.code, nativeError: nativeErrorDetails(error) });
}

function rawPipeTest(pipePath = PIPE_NAME, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const started = Date.now();
    const socket = net.createConnection({ path: pipePath });
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      socket.destroy();
      resolve({ ...result, durationMs: Date.now() - started, processPid: process.pid, processType: process.type || "node", execPath: process.execPath, nodeVersion: process.versions.node, electronVersion: process.versions.electron || null, arch: process.arch, pipePath: pipePathDiagnostics(pipePath) });
    };
    const timer = setTimeout(() => finish({ connected: false, code: "PIPE_CONNECT_TIMEOUT", nativeError: null }), timeoutMs);
    socket.once("connect", () => finish({ connected: true, code: "CONNECT_SUCCESS", nativeError: null }));
    socket.once("error", (error) => finish({ connected: false, code: error.code || "CONNECT_ERROR", nativeError: nativeErrorDetails(error) }));
  });
}

function probePipe(pipePath, timeoutMs = 1000) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ path: pipePath });
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(result);
    };
    socket.once("connect", () => finish({ success: true, connected: true, code: "PIPE_CONNECTED" }));
    socket.once("error", (error) => finish({ success: false, connected: false, code: mapPipeError(error).code, nativeCode: error.code }));
    socket.setTimeout(timeoutMs, () => finish({ success: false, connected: false, code: "PIPE_CONNECT_TIMEOUT" }));
  });
}

class IpcClient {
  constructor(secretProvider, pipeName = PIPE_NAME, logger = () => {}) {
    this.secretProvider = secretProvider;
    this.pipeName = pipeName;
    this.logger = logger;
    this.inFlight = 0;
    this.maxInFlight = 0;
    this.waitReadyInFlight = 0;
    this.maxWaitReadyInFlight = 0;
    this.statusInFlight = 0;
  }

  request(command, payload = {}, timeout = 5000, meta = {}) {
    return new Promise((resolve, reject) => {
      const secret = this.secretProvider();
      if (!secret) return reject(ipcError("IPC_SECRET_MISSING", "A credencial da comunicação local não está disponível."));
      const message = {
        version: IPC_CONTRACT.protocol_version,
        request_id: crypto.randomUUID(),
        timestamp: Date.now() / 1000,
        nonce: crypto.randomBytes(16).toString("hex"),
        command,
        payload,
      };
      const flowId = message.request_id.slice(0, 8);
      const callSite = meta.callSite || "unspecified";
      const flow = (event, extra = "") => this.logger(`[IPC_FLOW] request_id=${flowId} operation=${command} call_site=${callSite} electron_pid=${process.pid} event=${event} in_flight=${this.inFlight} wait_ready_in_flight=${this.waitReadyInFlight} status_requests_in_flight=${this.statusInFlight}${extra ? ` ${extra}` : ""}`);
      message.authentication = crypto.createHmac("sha256", secret).update(authText(message)).digest("hex");
      this.inFlight += 1;
      if (command === "status") this.statusInFlight += 1;
      this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
      flow("REQUEST_START", `timestamp=${Date.now()}`);
      const socket = net.createConnection({ path: this.pipeName });
      flow("CONNECT_START");
      let data = "";
      let settled = false;
      let connected = false;
      const complete = (callback) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        socket.destroy();
        this.inFlight = Math.max(0, this.inFlight - 1);
        if (command === "status") this.statusInFlight = Math.max(0, this.statusInFlight - 1);
        callback();
      };
      const finish = () => complete(() => {
        let response;
        try {
          response = JSON.parse(data);
        } catch {
          return reject(ipcError("IPC_RESPONSE_INVALID", "O proprietário retornou uma resposta inválida.", { connected, responseBytes: Buffer.byteLength(data) }));
        }
        if (response.version !== IPC_CONTRACT.protocol_version) {
          flow("REQUEST_FAILURE", `code=IPC_PROTOCOL_MISMATCH`);
          return reject(ipcError("IPC_PROTOCOL_MISMATCH", "A versão do protocolo IPC é incompatível.", { expected: IPC_CONTRACT.protocol_version, received: response.version }));
        }
        flow("RESPONSE_COMPLETE", `code=${response.code || "unknown"}`);
        flow("REQUEST_SUCCESS", `code=${response.code || "unknown"}`);
        resolve(response);
      });
      const timer = setTimeout(() => complete(() => {
        flow("REQUEST_FAILURE", `code=${connected ? "PIPE_HANDSHAKE_TIMEOUT" : "PIPE_CONNECT_TIMEOUT"}`);
        reject(ipcError(
        connected ? "PIPE_HANDSHAKE_TIMEOUT" : "PIPE_CONNECT_TIMEOUT",
        connected ? "A conexão local abriu, mas não respondeu ao handshake." : "A comunicação local não aceitou conexão dentro do prazo.",
        { connected, command, pipePath: this.pipeName },
        ));
      }), timeout);
      socket.once("connect", () => {
        connected = true;
        flow("CONNECTED");
        flow("WRITE_START");
        socket.write(JSON.stringify(message), () => flow("WRITE_COMPLETE"));
      });
      socket.on("data", (chunk) => { data += chunk; flow("DATA_RECEIVED", `bytes=${chunk.length} total_bytes=${Buffer.byteLength(data)}`); });
      socket.once("end", () => { flow("SOCKET_END"); finish(); });
      socket.once("close", () => { flow("SOCKET_CLOSE", `has_data=${Boolean(data)}`); if (data) finish(); });
      // O servidor Win32 encerra cada instância do pipe após escrever uma
      // resposta completa. O Node pode observar EPIPE/ECONNRESET junto com os
      // bytes já recebidos; nesse caso a resposta válida tem precedência.
      socket.once("error", (error) => {
        if (data) return finish();
        complete(() => { const mapped=mapPipeError(error,{connected,command,pipePath:this.pipeName});flow("REQUEST_FAILURE",`code=${mapped.code} native_code=${error.code || "unknown"}`);reject(mapped); });
      });
    });
  }

  async waitReady(timeout = 20000, options = {}) {
    this.waitReadyInFlight += 1;
    this.maxWaitReadyInFlight = Math.max(this.maxWaitReadyInFlight, this.waitReadyInFlight);
    this.logger(`[IPC_FLOW] event=WAIT_READY_START call_site=${options.callSite || "unspecified"} wait_ready_in_flight=${this.waitReadyInFlight} in_flight=${this.inFlight}`);
    try {
      return await this.performWaitReady(timeout, options);
    } finally {
      this.waitReadyInFlight = Math.max(0, this.waitReadyInFlight - 1);
      this.logger(`[IPC_FLOW] event=WAIT_READY_END call_site=${options.callSite || "unspecified"} wait_ready_in_flight=${this.waitReadyInFlight} in_flight=${this.inFlight}`);
    }
  }

  async performWaitReady(timeout = 20000, { signal, interval = 250, isOwnerAlive = () => true, ownerPid = null, callSite = "unspecified" } = {}) {
    const end = Date.now() + timeout;
    let attempt = 0;
    let lastError = null;
    const pathInfo = pipePathDiagnostics(this.pipeName);
    this.logger(`[IPC_CLIENT] process_type=${process.type || "node"} pid=${process.pid} exec_path=${JSON.stringify(process.execPath)} node=${process.versions.node} electron=${process.versions.electron || "none"} arch=${process.arch}`);
    this.logger(`[IPC_CLIENT] wait_started timeout_ms=${timeout} pipe_name=${IPC_CONTRACT.pipe_name} pipe_path=${pathInfo.json} pipe_path_type=${pathInfo.type} pipe_path_length=${pathInfo.length} pipe_path_char_codes=${JSON.stringify(pathInfo.charCodes)}`);
    while (Date.now() < end) {
      attempt += 1;
      if (signal?.aborted) throw ipcError("OWNER_WAIT_CANCELLED", "A espera pelo proprietário foi cancelada.");
      if (!isOwnerAlive()) throw ipcError("OWNER_EXITED_BEFORE_HANDSHAKE", "O proprietário encerrou antes do handshake.", { ownerPid, pipePath: this.pipeName });
      const remaining = Math.max(100, end - Date.now());
      try {
        // O ping é simultaneamente o probe de conexão e o handshake. Usar uma
        // conexão vazia separada consumiria a instância corrente do pipe.
        const ping = await this.request("ping", {}, Math.min(1500, remaining), { callSite: `${callSite}.ping` });
        this.logger(`[IPC_CLIENT] probe attempt=${attempt} connected=true result=PIPE_CONNECTED`);
        if (!ping.success || ping.code !== "PONG") throw ipcError(ping.code || "IPC_HANDSHAKE_REJECTED", "O ping IPC foi rejeitado.", { response: ping, connected: true });
        this.logger(`[IPC_CLIENT] handshake=true protocol=${ping.version}`);
        const status = await this.request("status", {}, Math.min(1500, remaining), { callSite: `${callSite}.status` });
        if (!status.success || !status.data?.pid || !status.data?.instance_id) throw ipcError(status.code || "IPC_OWNER_STATUS_INVALID", "O status do proprietário é inválido.", { response: status, connected: true });
        this.logger(`[IPC_CLIENT] owner_ready=true pid=${status.data.pid} instance_id=${status.data.instance_id}`);
        return status;
      } catch (error) {
        lastError = error;
        this.logger(`[IPC_CLIENT] probe attempt=${attempt} connected=${Boolean(error.details?.connected)} result=${error.code || "IPC_HANDSHAKE_FAILED"}`);
        this.logger(`[IPC_CLIENT] handshake=false attempt=${attempt} result=${error.code || "IPC_HANDSHAKE_FAILED"}`);
        if (["IPC_PROTOCOL_MISMATCH", "IPC_AUTH_FAILED", "IPC_SECRET_MISSING", "PIPE_ACCESS_DENIED"].includes(error.code)) throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
      interval = Math.min(Math.round(interval * 1.25), 1000);
    }
    throw ipcError(lastError?.code || "PIPE_CONNECT_TIMEOUT", "O proprietário permaneceu ativo, mas o handshake IPC não foi concluído.", {
      ownerPid,
      ownerAlive: isOwnerAlive(),
      serverReportedStarted: true,
      lastProbeCode: lastError?.code,
      pipePath: this.pipeName,
      causeDetails: lastError?.details,
      probeAttempts: attempt,
      lastError: lastError?.code,
    });
  }
}

module.exports = { IpcClient, authText, stable, probePipe, rawPipeTest, pipePathDiagnostics, nativeErrorDetails, mapPipeError, ipcError, PIPE_NAME };
