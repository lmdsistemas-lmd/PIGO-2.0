import { useEffect, useRef, useState } from 'react';
import api from '../services/api';
import { downloadBlob } from '../utils/downloadArquivo';
import { money } from '../utils/analytics';
import { CLOSING_TABS, closingTable, knownTotal } from '../utils/cashClosing';
import '../styles/cash-closing.css';

const CARDS = [['vendas','Total Vendas','💰','green'],['sangrias','Total Sangrias','📤','red'],['suprimentos','Suprimentos','📥','blue'],['recebimentos','Recebimentos','💳','orange'],['pagamentos','Pagamentos','📄','neutral'],['total_registrado','Valor Total','💎','purple']];
function value(v,type) {
  if(v === null || v === undefined || v === '') return '—';
  if(type==='currency') return money(v);
  if(type==='datetime') {
    const date=new Date(v);return Number.isNaN(date.valueOf())?String(v):date.toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'});
  }
  return String(v);
}
export default function CashClosingDialog({ detail, company, close }) {
  const ref=useRef(null);
  const [tab,setTab]=useState('financeiro');
  const [exporting,setExporting]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{const dialog=ref.current;const previous=document.activeElement;dialog.showModal();return()=>{dialog.close();previous?.focus();};},[]);
  const table=closingTable(detail,tab);
  const record=detail.record || {};
  const cash=(detail.cash_payments || []).find(row=>String(row.nome).trim().toLocaleUpperCase('pt-BR')==='DINHEIRO');
  async function exportDetail(format) {
    setExporting(true);setError('');
    try {
      const response=await api.get(`/operacoes/fechamentos/${encodeURIComponent(detail.id)}/export`,{params:{empresa_id:company,tab,format},responseType:'blob'});
      downloadBlob(response.data,`fechamento-${detail.id}-${tab}.${format==='excel'?'xlsx':'pdf'}`);
    } catch(err) {setError(err.message || 'Não foi possível exportar o fechamento.');}
    finally {setExporting(false);}
  }
  return <dialog ref={ref} className="cash-closing-dialog" aria-label="Fechamento de Caixa" onCancel={(event)=>{event.preventDefault();close();}}>
    <header className="cash-closing-header"><h2>Fechamento de Caixa</h2><button className="cash-close-icon" onClick={close} aria-label="Fechar janela">×</button></header>
    <div className="cash-closing-meta">{[['ID',detail.id],['Caixa',record.caixa],['Operador',record.operador],['Abertura',value(record.abertura,'datetime')],['Fechamento',value(record.fechamento,'datetime')]].map(([label,text])=><span key={label}>{label}: {text || '—'}</span>)}</div>
    <div className="cash-closing-tabs" role="tablist" aria-label="Detalhes do fechamento">{CLOSING_TABS.map(([key,label,icon])=><button key={key} role="tab" id={`cash-tab-${key}`} aria-selected={key===tab} aria-controls="cash-closing-panel" onClick={()=>{setTab(key);setError('');}}><span aria-hidden="true">{icon}</span>{label}</button>)}</div>
    <section role="tabpanel" id="cash-closing-panel" aria-labelledby={`cash-tab-${tab}`}>
      {tab==='financeiro' && <><h3>Resumo Financeiro</h3><div className="cash-summary-grid">{CARDS.map(([key,label,icon,tone])=><article className={`cash-summary-card cash-tone-${tone}`} key={key}><span><span aria-hidden="true">{icon}</span> {label}</span><strong>{value(detail.cash_summary?.[key],'currency')}</strong></article>)}<article className="cash-summary-card cash-tone-balance"><span>💵 Saldo Dinheiro</span><strong>{value(cash?.total,'currency')} <small>(Conferência: {value(cash?.conferencia,'currency')})</small></strong></article></div></>}
      <h3>{tab==='financeiro'?'Detalhamento por Forma de Pagamento':CLOSING_TABS.find(([key])=>key===tab)[1]}</h3>
      {!table.available ? <p className="cash-data-notice">Os dados desta aba ainda não estão disponíveis na integração.</p> : <div className="cash-table-scroll"><table className="cash-closing-table"><thead><tr>{table.columns.map(col=><th key={col.key}>{col.label}</th>)}</tr></thead><tbody>{table.rows.map((row,index)=><tr key={row._id || index}>{table.columns.map(col=><td key={col.key} className={`${col.type==='currency'?'cash-amount':''} cash-column-${col.key} ${col.key==='diferenca' && Number(row[col.key])<0?'cash-negative':''}`}>{value(row[col.key],col.type)}</td>)}</tr>)}</tbody><tfoot><tr>{table.columns.map((col,index)=><td key={col.key} className={`cash-column-${col.key}`}>{index===0?'TOTAL GERAL':['currency','number'].includes(col.type)?value(knownTotal(table.rows,col.key),col.type):''}</td>)}</tr></tfoot></table>{!table.rows.length && <p className="cash-data-notice">Nenhum registro nesta aba.</p>}</div>}
      {detail.cash_items_truncated && <p className="cash-data-notice">Exibindo até 10.000 registros. Consulte o ERP para o histórico completo.</p>}
    </section>
    {error && <p className="cash-data-notice" role="alert">{error}</p>}
    <footer className="cash-closing-footer"><button className="cash-export" disabled={exporting || !table.available} onClick={()=>exportDetail('excel')}>▣ Excel</button><button className="cash-export" disabled={exporting || !table.available} onClick={()=>exportDetail('pdf')}>▤ PDF</button><button className="cash-footer-close" onClick={close}>Fechar</button></footer>
  </dialog>;
}
