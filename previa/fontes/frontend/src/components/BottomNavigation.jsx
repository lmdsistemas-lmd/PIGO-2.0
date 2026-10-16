import { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import "../styles/bottom-navigation.css";
import { OPERATIONS } from "../config/operations";

function BottomNavigation() {
  const location = useLocation();
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
      icon: "/icons/painel.svg",
      active: location.pathname.startsWith("/dashboard/vendas"),
    },
    {
      path: "/dashboard/financeiro",
      label: "Financeiro",
      icon: "/icons/painel.svg",
      active: location.pathname.startsWith("/dashboard/financeiro"),
    },
    {
      path: "/dashboard/estoque",
      label: "Estoque",
      icon: "/icons/painel.svg",
      active: location.pathname.startsWith("/dashboard/estoque"),
    },
    {
      path: "/dashboard/consolidado",
      label: "Consolidado",
      icon: "/icons/painel.svg",
      active: location.pathname.startsWith("/dashboard/consolidado"),
    },
  ];

  const outrosItems = [
    ...OPERATIONS.map((item) => ({ path: item.path, label: item.title, icon: "/icons/painel.svg", active: location.pathname === item.path })),
    ...[["clientes", "Clientes"], ["metas", "Metas de Vendas"], ["curva-abc", "Curva ABC"]].map(([path, label]) => ({
      path: `/dashboard/${path}`, label, icon: "/icons/painel.svg", active: location.pathname === `/dashboard/${path}`,
    })),
    {
      path: "/funcionarios",
      label: "Equipe",
      icon: "/icons/funcionario.svg",
      active: location.pathname.startsWith("/funcionarios"),
    },
    {
      path: "/performance",
      label: "Performance",
      icon: "/icons/performance.svg",
      active: location.pathname.startsWith("/performance"),
    },
    {
      path: "/relatorios",
      label: "Relatórios",
      icon: "/icons/relatorio.svg",
      active: location.pathname.startsWith("/relatorios"),
    },
  ];

  return (
    <>
      {outrosOpen && (
        <div className="bottom-nav-overlay" onClick={() => setOutrosOpen(false)} />
      )}

      <nav className="bottom-nav" ref={menuRef}>
        {mainItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`bottom-nav-item ${item.active ? "active" : ""}`}
            aria-label={item.label}
            onClick={() => setOutrosOpen(false)}
          >
            <div className="bottom-nav-icon">
              <img src={item.icon} alt="" aria-hidden="true" />
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
              {outrosItems.map((item) =>
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`bottom-nav-popup-item ${item.active ? "active" : ""}`}
                    onClick={() => setOutrosOpen(false)}
                  >
                    <div className="bottom-nav-popup-icon">
                      <img src={item.icon} alt="" aria-hidden="true" />
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
