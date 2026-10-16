import { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import "../styles/bottom-navigation.css";
import { OPERATIONS, OPERATION_GROUPS } from "../config/operations";

import { useAuth } from "../context/AuthContext";
import { allowedPage } from "../utils/access";
import MenuIcon from "./MenuIcon";

function BottomNavigation() {
  const location = useLocation();
  const { user } = useAuth();
  const [outrosOpen, setOutrosOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOutrosOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, []);

  const isOutrosActive =
    OPERATIONS.some((item) => item.path === location.pathname) ||
    location.pathname.startsWith("/funcionarios") ||
    location.pathname.startsWith("/performance") ||
    location.pathname.startsWith("/relatorios") ||
    ["/dashboard/clientes", "/dashboard/metas", "/dashboard/curva-abc"].includes(location.pathname);

  const mainItems = [
    {
      path: "/dashboard/vendas",
      label: "Vendas",
      icon: "gestao",
      active: location.pathname.startsWith("/dashboard/vendas"),
    },
    {
      path: "/dashboard/financeiro",
      label: "Financeiro",
      icon: "financeiro",
      active: location.pathname.startsWith("/dashboard/financeiro"),
    },
    {
      path: "/dashboard/estoque",
      label: "Estoque",
      icon: "estoque",
      active: location.pathname.startsWith("/dashboard/estoque"),
    },
    {
      path: "/dashboard/consolidado",
      label: "Consolidado",
      icon: "consolidado",
      active: location.pathname.startsWith("/dashboard/consolidado"),
    },
  ];

  const outrosItems = [
    ...OPERATIONS.filter((item) => item.group === "Financeiro").map((item) => ({ path: item.path, label: item.title, icon: "financeiro", active: location.pathname === item.path })),
    ...[["clientes", "Clientes"], ["metas", "Metas de Vendas"], ["curva-abc", "Curva ABC"]].map(([path, label]) => ({
      path: `/dashboard/${path}`, label, icon: "gestao", active: location.pathname === `/dashboard/${path}`,
    })),
    {
      path: "/funcionarios",
      label: "Equipe",
      icon: "equipe",
      active: location.pathname.startsWith("/funcionarios"),
    },
    {
      path: "/performance",
      label: "Performance",
      icon: "performance",
      active: location.pathname.startsWith("/performance"),
    },
    {
      path: "/relatorios",
      label: "Relatórios",
      icon: "relatorios",
      active: location.pathname.startsWith("/relatorios"),
    },
  ];

  return (
    <>
      {outrosOpen && (
        <div className="bottom-nav-overlay" onClick={() => setOutrosOpen(false)} />
      )}

      <nav className="bottom-nav" ref={menuRef}>
        {mainItems.filter(item => allowedPage(user,item.path)).map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`bottom-nav-item ${item.active ? "active" : ""}`}
            aria-label={item.label}
            onClick={() => setOutrosOpen(false)}
          >
            <div className="bottom-nav-icon">
              <MenuIcon name={item.icon} />
            </div>
            <span className="bottom-nav-label">{item.label}</span>
          </Link>
        ))}

        <div className="bottom-nav-outros-wrapper">
          <button
            type="button"
            className={`bottom-nav-item ${isOutrosActive ? "active" : ""}`}
            onClick={() => setOutrosOpen((prev) => !prev)}
            aria-label="Outros"
          >
            <div className="bottom-nav-hamburger">
              <span /><span /><span />
            </div>
            <span className="bottom-nav-label">Outros</span>
          </button>

          {outrosOpen && (
            <div className="bottom-nav-popup">
              {allowedPage(user,'/cadastros/clientes') && <details className="bottom-registration-group" open={location.pathname.startsWith('/cadastros/') || undefined}>
                <summary><MenuIcon name="cadastros" />Cadastros</summary>
                {OPERATION_GROUPS.filter((group) => group.title !== 'Financeiro').map((group) => <div key={group.title}><h3>{group.title}</h3>{group.items.map(([resource, label]) => <Link key={resource} to={`${group.prefix}/${resource}`} className="bottom-nav-popup-item" onClick={() => setOutrosOpen(false)}>{label}</Link>)}</div>)}
              </details>}
              {[...outrosItems,{path:'/acesso/usuarios',label:'Acesso',icon:'acesso',active:location.pathname.startsWith('/acesso')}].filter(item => allowedPage(user,item.path)).map((item) =>
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`bottom-nav-popup-item ${item.active ? "active" : ""}`}
                    onClick={() => setOutrosOpen(false)}
                  >
                    <div className="bottom-nav-popup-icon">
                      <MenuIcon name={item.icon} />
                    </div>
                    <span className="bottom-nav-popup-label">{item.label}</span>
                  </Link>
              )}
            </div>
          )}
        </div>
      </nav>

    </>
  );
}

export default BottomNavigation;
