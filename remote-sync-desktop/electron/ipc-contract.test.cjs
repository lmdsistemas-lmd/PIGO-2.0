const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { IPC_CONTRACT, PIPE_NAME, getOwnerPipePath } = require("./ipc-contract.cjs");

test("Electron e agente usam o mesmo nome de pipe", () => {
  const pythonContract = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../remote-sync-agent/ipc_contract.json"), "utf8"));
  assert.equal(IPC_CONTRACT.pipe_name, "PIGORemoteSync");
  assert.deepEqual(IPC_CONTRACT, pythonContract);
  assert.equal(PIPE_NAME, "\\\\.\\pipe\\PIGORemoteSync");
  assert.equal(getOwnerPipePath(IPC_CONTRACT.pipe_name), PIPE_NAME);
});
