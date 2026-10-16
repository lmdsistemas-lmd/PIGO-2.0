const test = require("node:test");
const assert = require("node:assert/strict");
const { routeAgentCommand } = require("./command-router.cjs");

test("activate executa como bootstrap sem consultar o Named Pipe", async () => {
  let bootstrapArgs;
  let ipcCalls = 0;
  const response = await routeAgentCommand("activate", {
    executeBootstrap: async (args) => {
      bootstrapArgs = args;
      return { ok: true, code: 0, stdout: "activated", stderr: "" };
    },
    executeIpc: async () => { ipcCalls += 1; },
  });
  assert.deepEqual(bootstrapArgs, ["--activate"]);
  assert.equal(ipcCalls, 0);
  assert.equal(response.success, true);
});

test("test-firebird funciona antes da ativação sem consultar IPC", async () => {
  let argument;
  const response = await routeAgentCommand("test-firebird", {
    executeBootstrap: async (args) => {
      [argument] = args;
      return { ok: true, code: 0, stdout: "{}", stderr: "" };
    },
    executeIpc: async () => assert.fail("IPC não deveria ser chamado"),
  });
  assert.equal(argument, "--test-firebird");
  assert.equal(response.code, "BOOTSTRAP_COMPLETED");
});

test("sync-now e diagnose operacional usam exclusivamente IPC", async () => {
  const commands = [];
  const dependencies = {
    executeBootstrap: async () => assert.fail("bootstrap não deveria ser chamado"),
    executeIpc: async (command) => {
      commands.push(command);
      return { success: true, data: { state: "IDLE" } };
    },
  };
  await routeAgentCommand("sync-now", dependencies);
  await routeAgentCommand("diagnose", dependencies);
  assert.deepEqual(commands, ["sync-now", "diagnose"]);
});

test("comando desconhecido retorna erro estruturado", async () => {
  const response = await routeAgentCommand("unknown", {});
  assert.equal(response.success, false);
  assert.equal(response.code, "AGENT_COMMAND_UNKNOWN");
});
