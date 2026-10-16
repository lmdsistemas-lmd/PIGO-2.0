export const CLOSING_TABS = [['financeiro','Financeiro','💰'],['vendas','Vendas','🛒'],['produtos','Produtos Vendidos','📦'],['recebimentos','Recebimentos','💳'],['pagamentos','Pagamentos','💸'],['sangrias','Sangrias','📤'],['suprimentos','Suprimentos','📥'],['canceladas','Vendas Canceladas','❌']];
export const PAYMENT_COLUMNS = [['nome','Forma de Pagamento','text'],['entradas','Entrada','currency'],['saidas','Saída','currency'],['total','Total','currency'],['conferencia','Conferência','currency'],['diferenca','Diferença','currency']].map(([key,label,type])=>({key,label,type}));
const MOVEMENT_COLUMNS = [['data','Data','datetime'],['documento','Documento'],['descricao','Descrição'],['quantidade','Quantidade','number'],['valor','Valor','currency'],['usuario','Usuário']].map(([key,label,type])=>({key,label,type}));
const ORDER_COLUMNS = [['pedido','Pedido'],['data','Emissão','datetime'],['cliente','Cliente'],['status','Status'],['valor','Valor','currency'],['cancelamento','Cancelamento','datetime'],['motivo','Motivo']].map(([key,label,type])=>({key,label,type}));
const PRODUCT_COLUMNS = [['pedido','Pedido'],['sequencia','Item'],['produto','Produto'],['descricao','Descrição'],['quantidade','Quantidade','number'],['valor','Valor','currency']].map(([key,label,type])=>({key,label,type}));

export function knownTotal(rows, key) {
  if (rows.some(row=>row[key] === null || row[key] === undefined || row[key] === '' || !Number.isFinite(Number(row[key])))) return null;
  return rows.reduce((total,row)=>total+Number(row[key]),0);
}
export function closingTable(detail, tab) {
  if(tab==='financeiro') return {available:detail.cash_payments_available,columns:detail.cash_payment_columns || PAYMENT_COLUMNS,rows:detail.cash_payments || []};
  if(tab==='vendas' && detail.cash_orders_available) return {available:true,columns:ORDER_COLUMNS,rows:detail.cash_orders || []};
  if(tab==='produtos' && detail.cash_order_products_available) return {available:true,columns:PRODUCT_COLUMNS,rows:detail.cash_order_products || []};
  if(tab==='canceladas' && detail.cash_cancellations_available) return {available:true,columns:ORDER_COLUMNS,rows:detail.cash_cancellations || []};
  return {available:detail.cash_items_available,columns:MOVEMENT_COLUMNS,rows:detail.cash_items?.[tab] || []};
}
