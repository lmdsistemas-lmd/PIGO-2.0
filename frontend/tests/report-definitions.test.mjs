import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import definitions from '../src/components/reports/reportDefinitions.json' with { type: 'json' };
import * as config from '../src/components/reports/reportConfig.js';
import { validateReportDefinitions } from '../src/components/reports/reportDefinitionsValidator.js';

test('preserves every original report option, default, label and AI example', () => {
  // Contract captured from the uploaded original by parsing literal AST nodes,
  // without evaluating the original module.
  const names=['REPORT_CATEGORIES','CHARTS','ROLES','EMPTY_FORM','DEFAULT_WHITE_LABEL','ASSISTANT_EXAMPLES','BUSINESS_LABELS','PERIOD_LABELS'];
  const originalValues=Object.fromEntries(names.map(name => [name,config[name]]));
  assert.equal(createHash('sha256').update(JSON.stringify(originalValues)).digest('hex'),'29e7c540c24e41ccee392ad29291a438a5eb053073f99a54ffdf36fbe4840779');
  assert.equal(config.CATEGORY_BY_KEY.finance.slug,'financeiro');
  assert.equal(config.CATEGORY_BY_KEY.sales.title,'Relatórios de Vendas');
});

test('rejects unexpected configuration fields and broken references before rendering', () => {
  const invalid=[data => {data.command='unexpected';},data => {data.EMPTY_FORM.chart='unknown';},data => {data.EMPTY_FORM.permissions=['unknown'];},data => {data.ROLES.push(data.ROLES[0]);},data => {data.DEFAULT_WHITE_LABEL.primaryColor='url(invalid)';}];
  for (const change of invalid) {
    const data=structuredClone(definitions);change(data);
    assert.throws(() => validateReportDefinitions(data),TypeError);
  }
});

test('accepts text data only and rejects prototype-sensitive keys', () => {
  const data=structuredClone(definitions);data.ASSISTANT_EXAMPLES=[() => 'unexpected'];
  assert.throws(() => validateReportDefinitions(data),TypeError);
  const malformed=structuredClone(definitions);malformed.PERIOD_LABELS=JSON.parse('{"__proto__":"unexpected"}');
  assert.throws(() => validateReportDefinitions(malformed),TypeError);
  assert.equal(validateReportDefinitions(structuredClone(definitions)).EMPTY_FORM.chart,'table');
});
