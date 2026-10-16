const test = require("node:test");
const assert = require("node:assert/strict");
const { parseEnv, normalizeStore } = require("./config-manager.cjs");
test("importa env antigo sem executar seu conteudo", () => {
  const x = parseEnv(
    'FB_HOST=server\nFB_PASS="secret"\n# comment\nSYNC_INTERVAL_MINUTES=5',
  );
  assert.deepEqual(x, {
    FB_HOST: "server",
    FB_PASS: "secret",
    SYNC_INTERVAL_MINUTES: "5",
  });
});
test("migra o cofre 0.1.0 para o contrato versionado",()=>{const x=normalizeStore({licenseApiKey:{protection:"dpapi-machine",value:"encrypted-license"},remote_sync_token:{protection:"dpapi-machine",value:"encrypted-token"}});assert.deepEqual(x,{version:1,scope:"LocalMachine",entries:{license_api_key:"encrypted-license",remote_sync_token:"encrypted-token"}})});
