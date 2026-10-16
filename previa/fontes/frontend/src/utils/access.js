export function allowedPage(user,path) {
  if(user?.auth_source!=='pigo') return !path.startsWith('/acesso') || ['erp-admin','admin','administrator','administrador erp'].includes(String(user?.role || user?.perfil || '').toLowerCase());
  const permissions=user.permissions || [];
  const required=path.startsWith('/acesso')?'access.manage':path.startsWith('/financeiro')||path.startsWith('/dashboard/financeiro')?'finance.read':path.startsWith('/dashboard/estoque')?'inventory.read':path.startsWith('/dashboard')?'management.read':path.startsWith('/cadastros')?'catalogs.read':path.startsWith('/relatorios')?'reports.read':path.startsWith('/funcionarios')?'team.read':path.startsWith('/performance')?'performance.read':null;
  return required ? permissions.includes(required) : true;
}
export function firstAllowedPath(user) {
  return ['/dashboard/vendas','/dashboard/financeiro','/dashboard/estoque','/cadastros/clientes','/relatorios','/funcionarios','/performance','/acesso/usuarios'].find(path=>allowedPage(user,path)) || '/sem-acesso';
}
