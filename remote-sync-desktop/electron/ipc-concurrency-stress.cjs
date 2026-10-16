const net = require("node:net");
const { IpcClient } = require("./ipc-client.cjs");
const { getOwnerPipePath, IPC_CONTRACT } = require("./ipc-contract.cjs");
const { AgentOwnerResolver } = require("./agent-owner-resolver.cjs");

function serverFor(pipePath, pid) {
  return net.createServer((socket) => socket.once("data", (raw) => {
    const request = JSON.parse(String(raw));
    const ping = request.command === "ping";
    socket.end(JSON.stringify({ version: IPC_CONTRACT.protocol_version, success: true, code: ping ? "PONG" : "STATUS_OK", request_id: request.request_id, data: ping ? { protocol_version: 1, pid, instance_id: `stress-${pid}`, owner: "desktop" } : { pid, instance_id: `stress-${pid}`, owner: "desktop" } }));
  })).listen(pipePath);
}

async function runConcurrencyStress(cycles = 100) {
  const startedAt = Date.now();
  const metrics = { cycles, ownerReady: 0, ownersCreated: 0, readinessStarted: 0, pollRequestsDuringStartup: 0, maxIpcInFlight: 0, maxWaitReadyInFlight: 0, failures: [] };
  for (let cycle = 0; cycle < cycles; cycle += 1) {
    const pid = 10000 + cycle;
    const pipePath = getOwnerPipePath(`PIGORemoteSyncStress${process.pid}-${cycle}`);
    const client = new IpcClient(() => "stress-secret", pipePath);
    const resolver = new AgentOwnerResolver({}, client);
    let server;
    resolver.performStartConfiguredOwner = async () => {
      metrics.ownersCreated += 1;
      setTimeout(() => { server = serverFor(pipePath, pid); }, cycle % 4);
      metrics.readinessStarted += 1;
      const status = await client.waitReady(1000, { interval: 1, callSite: "stress.start-owner-readiness" });
      return { state: "DESKTOP_OWNER", pipeReady: true, pid: status.data.pid, instanceId: status.data.instance_id };
    };
    resolver.performEnsureDesktopOwner = async () => { throw new Error("CONCURRENT_READINESS_STARTED"); };
    try {
      const startup = resolver.startConfiguredOwner();
      const initialize = resolver.ensureDesktopOwner();
      if (!resolver.operationPromise) {
        metrics.pollRequestsDuringStartup += 1;
        await client.request("status", {}, 500, { callSite: "stress.react-status-poll" });
      }
      const [ownerA, ownerB] = await Promise.all([startup, initialize]);
      if (ownerA.pipeReady && ownerB.pipeReady && ownerA.pid === pid) metrics.ownerReady += 1;
      else metrics.failures.push({ cycle, code: "OWNER_RESULT_INVALID" });
    } catch (error) {
      metrics.failures.push({ cycle, code: error.code || error.message });
    } finally {
      metrics.maxIpcInFlight = Math.max(metrics.maxIpcInFlight, client.maxInFlight);
      metrics.maxWaitReadyInFlight = Math.max(metrics.maxWaitReadyInFlight, client.maxWaitReadyInFlight);
      if (server) await new Promise((resolve) => server.close(resolve));
    }
  }
  return { ...metrics, success: metrics.ownerReady === cycles && metrics.ownersCreated === cycles && metrics.readinessStarted === cycles && metrics.pollRequestsDuringStartup === 0 && metrics.failures.length === 0, durationMs: Date.now() - startedAt, processPid: process.pid, processType: process.type || "node" };
}

module.exports = { runConcurrencyStress };
