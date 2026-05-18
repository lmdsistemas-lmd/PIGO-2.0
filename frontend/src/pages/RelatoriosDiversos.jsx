import Topbar from "../components/Topbar";
import ListaRelatorios from "../components/ListaRelatorios.jsx";
import "../styles/topbar.css";

function RelatoriosDiversos({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  return (
    <>
      <Topbar titulo="Relatórios" caminho="Dashboard / Relatorios" onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet} theme={theme} toggleTheme={toggleTheme} />
      <ListaRelatorios categoria="diversos" titulo="Relatórios Diversos" />
    </>
  );
}

export default RelatoriosDiversos;
