import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { allowedPage } from "../utils/access";
import MenuIcon from "./MenuIcon";
import { OPERATION_GROUPS } from "../config/operations";
import "../styles/sidebar.css";

const management = [["vendas", "Vendas"], ["financeiro", "Financeiro"], ["estoque", "Estoque"], ["consolidado", "Consolidado"], ["clientes", "Clientes"], ["metas", "Metas de Vendas"], ["curva-abc", "Curva ABC"]];
const registrations = OPERATION_GROUPS.filter((group) => group.title !== "Financeiro");

export default function Sidebar({ collapsed = false, onToggleCollapsed = () => {}, isMobileOrTablet = false, isOpen = false, onClose = () => {} }) {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const can = (path) => allowedPage(user, path);
  const routeGroup = pathname.startsWith('/acesso') ? 'acesso' : pathname.startsWith('/cadastros/') ? 'cadastros' : pathname.startsWith('/financeiro/') ? 'financeiro' : pathname.startsWith('/dashboard/') ? 'gestao' : '';
  const [openGroups, setOpenGroups] = useState(() => ({ [routeGroup]: true }));
  const [closedForPath, setClosedForPath] = useState({});
  const compact = collapsed && !isMobileOrTablet;
  function isExpanded(group) { return !compact && (openGroups[group] || (routeGroup === group && closedForPath[group] !== pathname)); }
  function toggle(group) {
    if (compact) {
      onToggleCollapsed();
      setOpenGroups((previous) => ({ ...previous, [group]: true }));
      setClosedForPath((previous) => ({ ...previous, [group]: '' }));
      return;
    }
    const wasOpen = isExpanded(group);
    setOpenGroups((previous) => ({ ...previous, [group]: !wasOpen }));
    setClosedForPath((previous) => ({ ...previous, [group]: wasOpen ? pathname : '' }));
  }
  const closeMobile = () => { if (isMobileOrTablet) onClose(); };
  const link = (path, label) => can(path) ? <Link key={path} to={path} onClick={closeMobile} className={`submenu-item ${pathname === path ? 'submenu-item-active' : ''}`} aria-current={pathname === path ? 'page' : undefined}>{label}</Link> : null;
  function groupButton(id, label, icon) {
    return <button type="button" className={`menu-item ${routeGroup === id ? 'active' : ''}`} onClick={() => toggle(id)} aria-label={label} title={compact ? label : undefined} aria-expanded={isExpanded(id)} aria-controls={`menu-${id}`}><span className="menu-icon"><MenuIcon name={icon} /></span><span className="menu-label">{label}</span><span className="menu-chevron" aria-hidden="true">{isExpanded(id) ? '⌃' : '⌄'}</span></button>;
  }
  return <aside className={`sidebar ${compact ? 'sidebar-collapsed' : ''} ${isMobileOrTablet ? 'sidebar-overlay-mode' : ''} ${isOpen ? 'sidebar-open' : ''}`} aria-label="Menu principal">
    <div className="logo"><img src={compact ? '/logo-azul.svg' : '/logo-comprida.svg'} alt="LMD Sistemas" className={compact ? 'sidebar-logo-compact' : 'sidebar-logo-full'} /></div>
    {!isMobileOrTablet && <button type="button" className="sidebar-collapse-button" onClick={onToggleCollapsed} aria-label={compact ? 'Expandir menu lateral' : 'Recolher menu lateral'} title={compact ? 'Expandir menu lateral' : 'Recolher menu lateral'}><MenuIcon name={compact ? 'expandir' : 'recolher'} /><span>{compact ? '' : 'Recolher menu'}</span></button>}
    <nav className="sidebar-nav" aria-label="Seções do sistema">
      {management.some(([slug]) => can(`/dashboard/${slug}`)) && <div className="menu-group">{groupButton('gestao', 'Gestão', 'gestao')}{isExpanded('gestao') && <div className="submenu" id="menu-gestao">{management.map(([slug, label]) => link(`/dashboard/${slug}`, label))}</div>}</div>}
      {can('/financeiro/receber') && <div className="menu-group">{groupButton('financeiro', 'Financeiro', 'financeiro')}{isExpanded('financeiro') && <div className="submenu" id="menu-financeiro">{OPERATION_GROUPS[0].items.map(([slug, label]) => link(`/financeiro/${slug}`, label))}</div>}</div>}
      {can('/cadastros/clientes') && <div className="menu-group">{groupButton('cadastros', 'Cadastros', 'cadastros')}{isExpanded('cadastros') && <div className="submenu" id="menu-cadastros">{registrations.map((group) => <div className="registration-subgroup" key={group.title}><h3>{group.title}</h3>{group.items.map(([slug, label]) => link(`${group.prefix}/${slug}`, label))}</div>)}</div>}</div>}
      {[["/relatorios", "Relatórios com IA", "relatorios"], ["/funcionarios", "Equipe", "equipe"], ["/performance", "Performance", "performance"]].filter(([path]) => can(path)).map(([path, label, icon]) => <Link key={path} to={path} onClick={closeMobile} className={`menu-item ${pathname.startsWith(path) ? 'active' : ''}`} aria-label={label} aria-current={pathname.startsWith(path) ? 'page' : undefined} title={compact ? label : undefined}><span className="menu-icon"><MenuIcon name={icon} /></span><span className="menu-label">{label}</span></Link>)}
      {can('/acesso/usuarios') && <div className="menu-group">{groupButton('acesso', 'Acesso', 'acesso')}{isExpanded('acesso') && <div className="submenu" id="menu-acesso">{[['usuarios','Usuários'],['perfis','Perfis'],['permissoes','Permissões']].map(([slug,label]) => link(`/acesso/${slug}`,label))}</div>}</div>}
    </nav>
  </aside>;
}
