export const CHART_TYPES = ['original','bar','line','area','donut','table'];
export function normalizePreferences(saved, blocks) {
  const ids = new Set(blocks.map(block=>block.id));
  const seen = new Set();
  const order = [...(Array.isArray(saved?.order)?saved.order:[]),...ids].filter(id=>ids.has(id) && !seen.has(id) && seen.add(id));
  return {order,hidden:(Array.isArray(saved?.hidden)?saved.hidden:[]).filter(id=>ids.has(id)),types:Object.fromEntries(Object.entries(saved?.types || {}).filter(([id,type])=>ids.has(id) && CHART_TYPES.includes(type)))};
}
export function preferenceKey(dashboard,user,company) {
  return JSON.stringify(['pigo-dashboard-v1',user?.tenant_id || user?.cnpj || '',user?.id || user?.login || '',String(company || ''),dashboard]);
}
