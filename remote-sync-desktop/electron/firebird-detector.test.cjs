const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { peArchitecture } = require("./firebird-detector.cjs");
test("detecta x86 e x64 pelo cabecalho PE real", () => {
  for (const [machine, expected] of [
    [0x14c, "x86"],
    [0x8664, "x64"],
  ]) {
    const file = path.join(os.tmpdir(), `pigo-${machine}.dll`);
    const b = Buffer.alloc(256);
    b.writeUInt16LE(0x5a4d, 0);
    b.writeUInt32LE(128, 0x3c);
    b.writeUInt32LE(0x4550, 128);
    b.writeUInt16LE(machine, 132);
    fs.writeFileSync(file, b);
    assert.equal(peArchitecture(file), expected);
    fs.unlinkSync(file);
  }
});

test("rejeita DLL inexistente, inválida e corrompida", () => {
  const missing = path.join(os.tmpdir(), "pigo-missing-fbclient.dll");
  assert.throws(() => peArchitecture(missing));
  const invalid = path.join(os.tmpdir(), "pigo-invalid-fbclient.dll");
  fs.writeFileSync(invalid, "not-a-pe");
  assert.throws(() => peArchitecture(invalid));
  fs.unlinkSync(invalid);
  const corrupt = path.join(os.tmpdir(), "pigo-corrupt-fbclient.dll");
  const data = Buffer.alloc(64);
  data.writeUInt16LE(0x5a4d, 0);
  data.writeUInt32LE(4096, 0x3c);
  fs.writeFileSync(corrupt, data);
  assert.throws(() => peArchitecture(corrupt));
  fs.unlinkSync(corrupt);
});
