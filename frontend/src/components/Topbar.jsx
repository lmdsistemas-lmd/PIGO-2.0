import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useEmpresa } from "../context/EmpresaContext";
import "../styles/topbar.css";

function obterSaudacao() {
  const hora = new Date().getHours();

  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

function obterPrimeiroNome(nome) {
  const texto = String(nome || "").trim();
  if (!texto) return "Usuário";
  return texto.split(" ")[0];
}

function obterIniciais(nome) {
  const texto = String(nome || "").trim();

  if (!texto) return "US";

  const partes = texto.split(" ").filter(Boolean);

  if (partes.length === 1) {
    return partes[0].slice(0, 2).toUpperCase();
  }

  return `${partes[0][0] || ""}${partes[1][0] || ""}`.toUpperCase();
}

export default function Topbar({
  titulo = "Dashboard",
  subtitulo = "",
  caminho = "",
  onToggleSidebar = () => {},
  isMobileOrTablet = false,
  theme = "light",
  toggleTheme = () => {},
}) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { empresas, empresaAtual, selecionarEmpresa, loadingEmpresas } = useEmpresa();

  const nomeUsuario = user?.nome || user?.login || "Usuário";
  const primeiroNome = useMemo(() => obterPrimeiroNome(nomeUsuario), [nomeUsuario]);
  const iniciais = useMemo(() => obterIniciais(nomeUsuario), [nomeUsuario]);
  const saudacao = useMemo(() => obterSaudacao(), []);

  function handleLogout() {
    logout();
    localStorage.removeItem("empresa_atual");
    navigate("/login", { replace: true });
  }

  function handleEmpresaChange(event) {
    const empresaId = Number(event.target.value);
    const empresa = empresas.find((item) => Number(item.id) === empresaId);

    if (empresa) {
      selecionarEmpresa(empresa);
    }
  }

  return (
    <header className="topbar-shell">
      <div className="topbar-main">
        <div className="topbar-title-area">
          <div className="topbar-title-block">
            <div className="topbar-path">
              {user?.empresa ? `${user.empresa} ` : ""}
              {caminho ? `• ${caminho}` : ""}
            </div>
            <h1 className="topbar-title">{titulo}</h1>
            <p className="topbar-subtitle">
              {subtitulo || `${saudacao}, ${primeiroNome}`}
            </p>
          </div>
        </div>

        <div className="topbar-actions">
          <button 
            type="button" 
            onClick={toggleTheme} 
            className="topbar-theme-toggle"
            aria-label="Alternar tema"
          >
            {theme === "light" ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
              </svg>
            )}
          </button>

          <div className="topbar-company-group">
            <select
              id="empresa-topbar"
              value={empresaAtual?.id || ""}
              onChange={handleEmpresaChange}
              disabled={loadingEmpresas}
              className="topbar-company-select"
            >
              <option value="">
                {loadingEmpresas ? "..." : "Selecione a empresa"}
              </option>
              {empresas.map((empresa) => (
                <option key={empresa.id} value={empresa.id}>
                  {empresa.nome_exibicao}
                </option>
              ))}
            </select>
          </div>

          <div className="topbar-user-section">
            <div className="topbar-user-avatar" title={nomeUsuario}>{iniciais}</div>
            {!isMobileOrTablet && (
              <div className="topbar-user-info">
                <div className="topbar-user-name">{primeiroNome}</div>
              </div>
            )}
            <button type="button" onClick={handleLogout} className="topbar-logout-icon" title="Sair">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
