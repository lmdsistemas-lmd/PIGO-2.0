const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

test("Electron e Python compartilham DPAPI LocalMachine", {skip:process.platform!=="win32"}, () => {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "pigo-vault-"));
  process.env.PIGO_REMOTE_SYNC_DATA_DIR = dataDir;
  const config = require("./config-manager.cjs");
  config.save({firebird:{database:"test.fdb"},pigo:{apiBaseUrl:"https://example.test/api",companyCnpj:"12345678000199"},secrets:{firebirdPassword:"firebird-test",licenseApiKey:"license-test"}});
  const agentDir = path.resolve(__dirname, "../../remote-sync-agent");
  const script = "import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from credential_store import CredentialStore;s=CredentialStore(Path(sys.argv[2])/'credentials.dat',Path(sys.argv[2])/'installation.json');assert s.load_secret('firebird_password')=='firebird-test';assert s.load_secret('license_api_key')=='license-test';s.save_token('token-test');print('shared-vault-ok')";
  for(const architecture of ["python-x86","python-x64"]){
    const runtime=path.resolve(__dirname,`../runtime/${architecture}/python.exe`);
    const result = spawnSync(runtime,["-c",script,agentDir,dataDir],{encoding:"utf8",env:{...process.env,PIGO_REMOTE_SYNC_DATA_DIR:dataDir}});
    assert.equal(result.status,0,result.stderr);
    assert.match(result.stdout,/shared-vault-ok/);
  }
  assert.equal(config.credentialStatus().remoteSyncTokenPresent,true);
  assert.equal(config.credentialStatus().remoteSyncTokenReadable,true);
  fs.rmSync(dataDir,{recursive:true,force:true});
});
