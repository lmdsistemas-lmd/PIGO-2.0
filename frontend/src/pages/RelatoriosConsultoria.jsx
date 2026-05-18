import Topbar from "../components/Topbar";
import ListaRelatorios from "../components/ListaRelatorios.jsx";
import "../styles/topbar.css";

function RelatoriosConsultoria({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  return (
    <>
      <Topbar titulo="Relatórios" caminho="Dashboard / Consultoria / Contabilidade" onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet} theme={theme} toggleTheme={toggleTheme} />
      <ListaRelatorios
        categoria="consultoria"
        titulo="Relatórios de Consultoria / Contabilidade"
      />
    </>
  );
}

export default RelatoriosConsultoria;
