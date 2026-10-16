// Report definitions are data. Reject unexpected shapes before the UI consumes them.
const TOP_LEVEL = ['REPORT_CATEGORIES','CHARTS','ROLES','EMPTY_FORM','DEFAULT_WHITE_LABEL','ASSISTANT_EXAMPLES','BUSINESS_LABELS','PERIOD_LABELS'];
const fail = (field) => { throw new TypeError(`Configuração de relatórios inválida: ${field}`); };
function record(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) fail(field);
  return value;
}
function keys(value, expected, field) {
  record(value, field);
  if (Object.keys(value).length !== expected.length || expected.some(key => !Object.hasOwn(value,key))) fail(field);
}
function text(value, field, allowEmpty = false) {
  if (typeof value !== 'string' || value.length > 500 || (!allowEmpty && !value.trim())) fail(field);
}
function labels(value, field) {
  record(value,field);
  for (const [key,label] of Object.entries(value)) {
    if (!/^[a-z][a-z0-9_]*$/.test(key) || ['constructor','prototype'].includes(key)) fail(field);
    text(label,field+'.'+key);
  }
}
export function validateReportDefinitions(data) {
  keys(data,TOP_LEVEL,'definitions');
  keys(data.REPORT_CATEGORIES,['vendas','financeiro','contabilidade','outros'],'categories');
  const categories = new Set();
  for (const [slug,category] of Object.entries(data.REPORT_CATEGORIES)) {
    keys(category,['key','label','title','description'],slug);
    for (const [key,value] of Object.entries(category)) text(value,slug+'.'+key);
    if (!/^[a-z]+$/.test(category.key) || categories.has(category.key)) fail(slug+'.key');
    categories.add(category.key);
  }
  keys(data.CHARTS,['table','cards','bar','line','pie','area'],'charts');labels(data.CHARTS,'charts');
  if (!Array.isArray(data.ROLES) || !data.ROLES.length) fail('roles');
  const roles = new Set();
  for (const pair of data.ROLES) {
    if (!Array.isArray(pair) || pair.length !== 2) fail('roles');
    if (!/^[a-z]+$/.test(pair[0]) || roles.has(pair[0])) fail('roles.key');
    text(pair[1],'roles.label');roles.add(pair[0]);
  }
  keys(data.EMPTY_FORM,['name','description','source','fields','filters','group_by','order_by','totals','chart','permissions'],'emptyForm');
  for (const key of ['name','description','source']) text(data.EMPTY_FORM[key],'emptyForm.'+key,true);
  for (const key of ['fields','filters','group_by','order_by','totals']) {
    if (!Array.isArray(data.EMPTY_FORM[key]) || data.EMPTY_FORM[key].length) fail('emptyForm.'+key);
  }
  if (!Object.hasOwn(data.CHARTS,data.EMPTY_FORM.chart)) fail('emptyForm.chart');
  if (!Array.isArray(data.EMPTY_FORM.permissions) || data.EMPTY_FORM.permissions.some(role => !roles.has(role))) fail('emptyForm.permissions');
  keys(data.DEFAULT_WHITE_LABEL,['mode','companyName','title','subtitle','primaryColor','secondaryColor','header','footer','footerText','issueDate','responsibleUser','appliedFilters','pagination','orientation','paperSize'],'whiteLabel');
  for (const [key,value] of Object.entries(data.DEFAULT_WHITE_LABEL)) {
    if (['header','footer','issueDate','responsibleUser','appliedFilters','pagination'].includes(key)) { if (typeof value !== 'boolean') fail('whiteLabel.'+key); }
    else text(value,'whiteLabel.'+key,true);
  }
  for (const key of ['primaryColor','secondaryColor']) if (!/^#[0-9a-f]{6}$/i.test(data.DEFAULT_WHITE_LABEL[key])) fail('whiteLabel.'+key);
  if (!['portrait','landscape'].includes(data.DEFAULT_WHITE_LABEL.orientation) || data.DEFAULT_WHITE_LABEL.paperSize !== 'A4') fail('whiteLabel.page');
  if (!Array.isArray(data.ASSISTANT_EXAMPLES) || !data.ASSISTANT_EXAMPLES.length) fail('assistantExamples');
  data.ASSISTANT_EXAMPLES.forEach(value => text(value,'assistantExamples'));
  labels(data.BUSINESS_LABELS,'businessLabels');labels(data.PERIOD_LABELS,'periodLabels');
  return data;
}
