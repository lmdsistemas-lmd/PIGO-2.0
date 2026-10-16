const test = require("node:test");
const assert = require("node:assert/strict");
const { AgentOwnerResolver } = require("./agent-owner-resolver.cjs");

test("start e readiness concorrentes compartilham uma unica operacao", async () => {
  const resolver = new AgentOwnerResolver({}, {});
  let starts = 0;
  resolver.performStartConfiguredOwner = async () => {
    starts += 1;
    await new Promise((resolve) => setTimeout(resolve, 25));
    return { state: "DESKTOP_OWNER", pipeReady: true, pid: 77 };
  };
  resolver.performEnsureDesktopOwner = async () => assert.fail("segunda operacao nao deve iniciar");
  const first = resolver.startConfiguredOwner();
  const second = resolver.ensureDesktopOwner();
  assert.equal(first, second);
  const [a, b] = await Promise.all([first, second]);
  assert.equal(starts, 1);
  assert.deepEqual(a, b);
  assert.equal(resolver.operationPromise, null);
});

test("detecta conflito e mantém prioridade do serviço", async () => {
  const manager = { child: { pid: 22 }, stopAndWait: async () => { manager.child = null; } };
  const client = { request: async () => ({ success: true, data: { pid: 11, owner: "service" } }) };
  const resolver = new AgentOwnerResolver(manager, client);
  resolver.serviceState = () => ({ installed: true, running: true, pid: 11 });
  assert.equal((await resolver.resolve()).state, "OWNER_CONFLICT");
  const resolved = await resolver.ensureDesktopOwner();
  assert.equal(manager.child, null);
  assert.equal(resolved.state, "SERVICE_OWNER");
});

test("não assume silenciosamente quando serviço instalado está parado", async () => {
  const manager = { child: null };
  const client = { request: async () => { throw new Error("offline"); } };
  const resolver = new AgentOwnerResolver(manager, client);
  resolver.serviceState = () => ({ installed: true, running: false, pid: null });
  const result = await resolver.ensureDesktopOwner();
  assert.equal(result.state, "OWNER_UNAVAILABLE");
  assert.equal(result.requiresConfirmation, true);
});

test("inicia proprietário desktop e aguarda pipe quando serviço está ausente", async () => {
  let waited = false;
  const manager = {
    child: null,
    start() { this.child = { pid: 44 }; return { running: true }; },
  };
  const client = {
    waitReady: async () => {
      waited = true;
      return { success: true, data: { owner: "desktop", pid: 44, instance_id: "abc" } };
    },
  };
  const resolver = new AgentOwnerResolver(manager, client);
  resolver.serviceState = () => ({ installed: false, running: false, pid: null });
  resolver.resolve = async () => ({ state: "DESKTOP_OWNER", ownerType: "desktop", pid: 44, instanceId: "abc", pipeReady: true });
  const result = await resolver.startConfiguredOwner();
  assert.equal(waited, true);
  assert.equal(result.state, "DESKTOP_OWNER");
});

test("serviço RUNNING sem IPC é parado antes do fallback desktop", async () => {
  let running = true;
  const manager = {
    child: null,
    start() { this.child = { pid: 55 }; return { running: true }; },
    waitForOwnerReady: async () => ({ success: true, data: { owner: "desktop", pid: 55, instance_id: "fallback" } }),
  };
  const client = { waitReady: async () => { throw Object.assign(new Error("offline"), { code: "OWNER_NOT_AVAILABLE" }); } };
  const resolver = new AgentOwnerResolver(manager, client);
  resolver.serviceState = () => ({ installed: true, name: "PIGORemoteSync", status: running ? "RUNNING" : "STOPPED", running, pid: running ? 10 : null });
  resolver.serviceCommand = (command) => { if (command === "stop") running = false; return true; };
  resolver.waitForService = async (expected) => ({ installed: true, running: expected ? running : false });
  resolver.resolve = async () => ({ state: "DESKTOP_OWNER", ownerType: "desktop", pid: 55, instanceId: "fallback", pipeReady: true, service: { installed: true, running: false } });
  const result = await resolver.startConfiguredOwner();
  assert.equal(result.fallbackCode, "SERVICE_RUNNING_WITHOUT_IPC");
  assert.equal(result.ownerType, "desktop");
});

test("não cria segundo owner quando serviço sem IPC não pode ser parado", async () => {
  const manager = { child: null, start: () => assert.fail("owner desktop não deve iniciar") };
  const client = { waitReady: async () => { throw Object.assign(new Error("offline"), { code: "OWNER_NOT_AVAILABLE" }); } };
  const resolver = new AgentOwnerResolver(manager, client);
  resolver.serviceState = () => ({ installed: true, name: "PIGORemoteSync", status: "RUNNING", running: true, pid: 10 });
  resolver.serviceCommand = () => false;
  resolver.waitForService = async () => ({ running: true });
  await assert.rejects(resolver.startConfiguredOwner(), (error) => error.code === "SERVICE_RUNNING_WITHOUT_IPC");
});
