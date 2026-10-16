import { Children, cloneElement, Fragment, isValidElement, useEffect, useRef, useState } from 'react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useAuth } from '../context/AuthContext';
import { useEmpresa } from '../context/EmpresaContext';
import { resolveEmpresaErpId } from '../services/empresaIdentity';
import { normalizePreferences, preferenceKey } from '../utils/dashboardPreferences';
import '../styles/dashboard-personalization.css';

export function DashboardBlock({ children }) { return children; }
const TYPES = [['original','Original'],['bar','Barras'],['line','Linhas'],['area','Área'],['donut','Rosca'],['table','Tabela']];
const COLORS = ['#403cff','#10b981','#f59e0b','#ec4899','#0ea5e9','#8b5cf6'];
function walk(node, callback) {
  Children.forEach(node,item=>{if(!isValidElement(item)) return;if(item.type===DashboardBlock)callback(item);else if(item.props.children)walk(item.props.children,callback);});
}
function hasBlocks(node) { let found=false;walk(node,()=>{found=true;});return found; }
function onlyBlocks(node) {
  return Children.toArray(node).every(item=>{
    if(!isValidElement(item))return typeof item==='string'?!item.trim():item==null;
    return item.type===DashboardBlock || ((typeof item.type==='string' || item.type===Fragment) && item.props.children && onlyBlocks(item.props.children));
  });
}
function DataChart({ block, type }) {
  const {rows=[],labelKey='nome',series=[{key:'valor',label:'Valor'}],title} = block.props;
  if(!rows.length) return <section className="dashboard-personalized-chart"><h3>{title}</h3><p>Não há dados disponíveis para este bloco no período selecionado.</p></section>;
  if(type==='table') return <section className="dashboard-personalized-chart"><h3>{title}</h3><div className="dashboard-chart-table"><table><thead><tr><th>Descrição</th>{series.map(item=><th key={item.key}>{item.label}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index}><td>{row[labelKey]}</td>{series.map(item=><td key={item.key}>{row[item.key]==null?'—':Number(row[item.key]).toLocaleString('pt-BR')}</td>)}</tr>)}</tbody></table></div></section>;
  const Component = type==='line'?LineChart:type==='area'?AreaChart:BarChart;
  return <section className="dashboard-personalized-chart"><h3>{title}</h3><ResponsiveContainer width="100%" height={300}>{type==='donut'?<PieChart><Pie data={rows} dataKey={series[0].key} nameKey={labelKey} innerRadius="55%" outerRadius="80%" isAnimationActive={false}>{rows.map((_,index)=><Cell key={index} fill={COLORS[index%COLORS.length]} />)}</Pie><Tooltip /><Legend /></PieChart>:<Component data={rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={labelKey} tick={{fontSize:11}} /><YAxis /><Tooltip /><Legend />{series.map((item,index)=>type==='line'?<Line key={item.key} dataKey={item.key} name={item.label} stroke={COLORS[index%COLORS.length]} isAnimationActive={false} />:type==='area'?<Area key={item.key} dataKey={item.key} name={item.label} stroke={COLORS[index%COLORS.length]} fill={COLORS[index%COLORS.length]} fillOpacity={.2} isAnimationActive={false} />:<Bar key={item.key} dataKey={item.key} name={item.label} fill={COLORS[index%COLORS.length]} isAnimationActive={false} />)}</Component>}</ResponsiveContainer></section>;
}
function Customizer({ blocks, prefs, change, close }) {
  const ref=useRef(null);
  useEffect(()=>{const dialog=ref.current;dialog.showModal();return()=>dialog.close();},[]);
  function move(id,target) {
    if(id===target)return;
    const order=prefs.order.filter(key=>key!==id);order.splice(order.indexOf(target),0,id);change({...prefs,order});
  }
  return <dialog ref={ref} className="dashboard-customizer-dialog" aria-label="Personalizar gráficos" onCancel={(event)=>{event.preventDefault();close();}}>
    <header><h2>Personalizar gráficos</h2><button className="customizer-restore" onClick={()=>change(normalizePreferences(null,blocks))}>Restaurar</button><button className="customizer-close" aria-label="Fechar personalização" onClick={close}>×</button></header>
    <div className="customizer-list">{prefs.order.map((id,index)=>{const block=blocks.find(item=>item.id===id);return <div className="customizer-row" key={id} onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();const source=event.dataTransfer.getData('text/plain');if(prefs.order.includes(source))move(source,id);}}>
      <button className="customizer-grip" draggable onDragStart={event=>event.dataTransfer.setData('text/plain',id)} aria-label={`Arrastar ${block.title}`} title="Arraste para mudar a ordem">⠿</button>
      <label><input type="checkbox" checked={!prefs.hidden.includes(id)} onChange={()=>change({...prefs,hidden:prefs.hidden.includes(id)?prefs.hidden.filter(key=>key!==id):[...prefs.hidden,id]})} />{block.title}</label>
      {block.chart && <select aria-label={`Tipo de gráfico de ${block.title}`} value={prefs.types[id] || 'original'} onChange={event=>change({...prefs,types:{...prefs.types,[id]:event.target.value}})}>{TYPES.map(([key,label])=><option value={key} key={key}>{label}</option>)}</select>}
      <span className="customizer-move"><button aria-label={`Mover ${block.title} para cima`} disabled={index===0} onClick={()=>move(id,prefs.order[index-1])}>▲</button><button aria-label={`Mover ${block.title} para baixo`} disabled={index===prefs.order.length-1} onClick={()=>{const order=[...prefs.order];[order[index],order[index+1]]=[order[index+1],order[index]];change({...prefs,order});}}>▼</button></span>
    </div>;})}</div>
    <footer><button onClick={()=>change({...prefs,hidden:[]})}>Mostrar todos</button><small>Salvo neste navegador, por usuário e empresa.</small></footer>
  </dialog>;
}
function placeWorkspace(nodes,grid,inserted=false) {
  return Children.toArray(nodes).reduce((state,node)=>{
    if(!isValidElement(node) || !node.props.children)return {nodes:[...state.nodes,node],inserted:state.inserted};
    if(hasBlocks(node) && onlyBlocks(node))return {nodes:state.inserted?state.nodes:[...state.nodes,grid],inserted:true};
    const nested=placeWorkspace(node.props.children,grid,state.inserted);
    return {nodes:[...state.nodes,cloneElement(node,{},nested.nodes)],inserted:nested.inserted};
  },{nodes:[],inserted});
}
function Workspace({children,storageKey,dashboard}) {
  const elements=[];walk(children,block=>elements.push(block));
  const unique=new Map(elements.map(block=>[block.props.id,block]));
  const blocks=[...unique.values()].map(block=>({...block.props,chart:Array.isArray(block.props.rows)}));
  const [saved,setSaved]=useState(()=>{try{return JSON.parse(localStorage.getItem(storageKey));}catch{return null;}});
  const [editing,setEditing]=useState(false);
  const [notice,setNotice]=useState('');
  const prefs=normalizePreferences(saved,blocks);
  function change(next) {setSaved(next);try{localStorage.setItem(storageKey,JSON.stringify(next));setNotice('');}catch{setNotice('A preferência vale nesta sessão; o navegador não permitiu salvá-la.');}}
  // Keep the saved order, but give adjacent indicators their own rows so a
  // neighboring table can never determine a metric card's height.
  const sections=[];
  for(const id of prefs.order.filter(id=>!prefs.hidden.includes(id))) {
    const block=unique.get(id);
    const kind=block.props.kind==='metric'?'metrics':'panels';
    if(sections.at(-1)?.kind!==kind)sections.push({kind,ids:[]});
    sections.at(-1).ids.push(id);
  }
  function columns(count,maximum) { return Math.ceil(count/Math.ceil(count/maximum)); }
  const grid=<Fragment key="personalized-dashboard">
    <div className="dashboard-personalization-toolbar"><button onClick={()=>setEditing(true)}>⚙ Personalizar gráficos</button>{notice && <span role="status">{notice}</span>}</div>
    <div className={`dashboard-widget-grid dashboard-widget-grid-${dashboard}`}>
      {sections.map(section=><div key={section.ids[0]} className={`dashboard-widget-section dashboard-widget-section-${section.kind}`} style={section.kind==='metrics'?{'--metric-columns':columns(section.ids.length,5),'--metric-columns-medium':columns(section.ids.length,3),'--metric-columns-small':columns(section.ids.length,2)}:undefined}>
        {section.ids.map(id=>{
          const block=unique.get(id);const type=prefs.types[id] || 'original';
          const full=['wide','map','table'].includes(block.props.kind) || type==='table';
          return <div className={`dashboard-widget dashboard-widget-${block.props.kind || 'chart'} ${full?'dashboard-widget-full':''}`} key={id} data-widget-id={id}>
            {type==='original' || !Array.isArray(block.props.rows)?block.props.children:<DataChart block={block} type={type} />}
          </div>;
        })}
      </div>)}
      {prefs.order.length===prefs.hidden.length && <p className="dashboard-all-hidden">Nenhum bloco visível. <button onClick={()=>change({...prefs,hidden:[]})}>Mostrar todos</button></p>}
    </div>
  </Fragment>;
  return <>{placeWorkspace(children,grid).nodes}{editing && <Customizer blocks={blocks} prefs={prefs} change={change} close={()=>setEditing(false)} />}</>;
}
export default function DashboardWorkspace({dashboard,children}) {
  const {user}=useAuth();const {empresaAtual}=useEmpresa();
  const key=preferenceKey(dashboard,user,resolveEmpresaErpId(empresaAtual));
  return <Workspace storageKey={key} dashboard={dashboard} key={key}>{children}</Workspace>;
}
