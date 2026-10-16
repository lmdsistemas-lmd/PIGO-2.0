const BOOTSTRAP_COMMANDS = new Set([
  "activate",
  "reactivate",
  "clear-credentials",
  "test-firebird",
]);
const IPC_COMMANDS = new Set([
  "status",
  "sync-now",
  "diagnose",
  "pause",
  "resume",
  "reload-config",
  "restart",
  "stop",
]);

const BOOTSTRAP_ARGUMENTS = {
  activate: "--activate",
  reactivate: "--reactivate",
  "clear-credentials": "--clear-credentials",
  "test-firebird": "--test-firebird",
};

async function routeAgentCommand(command, { executeBootstrap, executeIpc }) {
  if (BOOTSTRAP_COMMANDS.has(command)) {
    const result = await executeBootstrap([BOOTSTRAP_ARGUMENTS[command]]);
    return {
      success: result.ok,
      code: result.ok ? "BOOTSTRAP_COMPLETED" : "BOOTSTRAP_FAILED",
      command,
      exitCode: result.code,
      stdout: result.stdout,
      stderr: result.stderr,
    };
  }
  if (IPC_COMMANDS.has(command)) return executeIpc(command);
  return {
    success: false,
    code: "AGENT_COMMAND_UNKNOWN",
    message: "O comando solicitado não é reconhecido.",
  };
}

module.exports = { BOOTSTRAP_COMMANDS, IPC_COMMANDS, routeAgentCommand };
