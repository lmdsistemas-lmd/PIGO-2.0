const fs = require("node:fs");
const path = require("node:path");

function contractPath() {
  const candidates = [
    process.env.PIGO_REMOTE_SYNC_IPC_CONTRACT,
    process.resourcesPath && path.join(process.resourcesPath, "agent", "ipc_contract.json"),
    path.resolve(__dirname, "../../remote-sync-agent/ipc_contract.json"),
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function loadContract() {
  const file = contractPath();
  if (!file) throw new Error("IPC_CONTRACT_NOT_FOUND");
  const contract = JSON.parse(fs.readFileSync(file, "utf8"));
  if (!contract.pipe_name || !contract.protocol_version) {
    throw new Error("IPC_CONTRACT_INVALID");
  }
  return contract;
}

const IPC_CONTRACT = loadContract();
function getOwnerPipePath(pipeName = IPC_CONTRACT.pipe_name) {
  return `\\\\.\\pipe\\${pipeName}`;
}

const PIPE_NAME = getOwnerPipePath();

module.exports = { IPC_CONTRACT, PIPE_NAME, getOwnerPipePath, contractPath, loadContract };
