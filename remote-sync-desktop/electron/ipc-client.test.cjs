const test = require("node:test");
const assert = require("node:assert/strict");
const net = require("node:net");
const { IpcClient, probePipe, rawPipeTest, pipePathDiagnostics, mapPipeError } = require("./ipc-client.cjs");
const { IPC_CONTRACT, getOwnerPipePath } = require("./ipc-contract.cjs");

function pipe(suffix) {
  return getOwnerPipePath(`PIGORemoteSync${suffix}${process.pid}`);
}

function handshakeServer(pipePath, { version = IPC_CONTRACT.protocol_version, silent = false, pid = process.pid } = {}) {
  return net.createServer((socket) => {
    socket.once("data", (raw) => {
      if (silent) return;
      const request = JSON.parse(String(raw));
      const ping = request.command === "ping";
      socket.end(JSON.stringify({
        version,
        success: true,
        code: ping ? "PONG" : "STATUS_OK",
        data: ping
          ? { protocol_version: version, pid, instance_id: "test", owner: "desktop" }
          : { pid, instance_id: "test", owner: "desktop" },
      }));
    });
  }).listen(pipePath);
}

test("pipe inexistente é identificado como PIPE_NOT_FOUND", { skip: process.platform !== "win32" }, async () => {
  const client = new IpcClient(() => "local-test-secret", pipe("Missing"));
  await assert.rejects(client.request("status", {}, 500), (error) => error.code === "PIPE_NOT_FOUND");
});

test("probe usa conexão real e não filesystem", { skip: process.platform !== "win32" }, async (context) => {
  const pipePath = pipe("Probe");
  const server = handshakeServer(pipePath);
  context.after(() => server.close());
  assert.deepEqual(await probePipe(pipePath, 500), { success: true, connected: true, code: "PIPE_CONNECTED" });
});

test("raw connect usa options.path e preserva o namespace Win32", { skip: process.platform !== "win32" }, async (context) => {
  const pipePath = pipe("Raw");
  const server = handshakeServer(pipePath);
  context.after(() => server.close());
  const result = await rawPipeTest(pipePath, 500);
  assert.equal(result.connected, true);
  assert.equal(result.code, "CONNECT_SUCCESS");
  assert.deepEqual(result.pipePath, pipePathDiagnostics(pipePath));
  assert.deepEqual(pipePathDiagnostics(getOwnerPipePath()).charCodes, [92,92,46,92,112,105,112,101,92,80,73,71,79,82,101,109,111,116,101,83,121,110,99]);
});

test("waitReady aguarda pipe que demora para aparecer e conclui ping/status", { skip: process.platform !== "win32", timeout: 8000 }, async (context) => {
  const pipePath = pipe("Delayed");
  let server;
  const timer = setTimeout(() => { server = handshakeServer(pipePath); }, 2000);
  context.after(() => { clearTimeout(timer); server?.close(); });
  const client = new IpcClient(() => "local-test-secret", pipePath);
  const response = await client.waitReady(6000, { interval: 50, ownerPid: process.pid });
  assert.equal(response.success, true);
  assert.equal(response.data.pid, process.pid);
});

test("conexão sem resposta vira PIPE_HANDSHAKE_TIMEOUT", { skip: process.platform !== "win32" }, async (context) => {
  const pipePath = pipe("Silent");
  const server = handshakeServer(pipePath, { silent: true });
  context.after(() => server.close());
  const client = new IpcClient(() => "local-test-secret", pipePath);
  await assert.rejects(client.waitReady(700, { interval: 25 }), (error) => error.code === "PIPE_HANDSHAKE_TIMEOUT");
});

test("protocolo incompatível não é mascarado como timeout", { skip: process.platform !== "win32" }, async (context) => {
  const pipePath = pipe("Protocol");
  const server = handshakeServer(pipePath, { version: 99 });
  context.after(() => server.close());
  const client = new IpcClient(() => "local-test-secret", pipePath);
  await assert.rejects(client.waitReady(2000), (error) => error.code === "IPC_PROTOCOL_MISMATCH");
});

test("EACCES é mapeado como PIPE_ACCESS_DENIED", () => {
  assert.equal(mapPipeError({ code: "EACCES" }).code, "PIPE_ACCESS_DENIED");
});
