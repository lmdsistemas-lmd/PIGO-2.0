const test = require("node:test");
const assert = require("node:assert/strict");
const { runConcurrencyStress } = require("./ipc-concurrency-stress.cjs");

test("100 startups usam um owner e um readiness sem polling concorrente", { skip: process.platform !== "win32", timeout: 30000 }, async () => {
  const result = await runConcurrencyStress(100);
  assert.equal(result.success, true, JSON.stringify(result));
  assert.equal(result.ownerReady, 100);
  assert.equal(result.ownersCreated, 100);
  assert.equal(result.readinessStarted, 100);
  assert.equal(result.pollRequestsDuringStartup, 0);
  assert.equal(result.maxIpcInFlight, 1);
  assert.equal(result.maxWaitReadyInFlight, 1);
});
