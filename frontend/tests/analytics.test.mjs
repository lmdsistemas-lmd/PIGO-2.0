import assert from "node:assert/strict";
import test from "node:test";
import { csvCell, money, percent } from "../src/utils/analytics.js";

test("CSV mantém separadores e neutraliza fórmulas de planilhas", () => {
  assert.equal(csvCell('Produto; "A"'), '"Produto; ""A"""');
  assert.equal(csvCell("=HYPERLINK(\"x\")"), '"\'=HYPERLINK(""x"")"');
  assert.equal(csvCell("  +123"), '"\'  +123"');
  assert.equal(csvCell(1200.5), '"1200.5"');
});

test("indicadores usam moeda e percentuais brasileiros", () => {
  assert.match(money(1234.56), /1\.234,56/);
  assert.equal(percent(25.5), "25,5%");
});
