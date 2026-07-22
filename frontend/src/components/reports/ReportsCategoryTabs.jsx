import { NavLink } from "react-router-dom";
import { REPORT_CATEGORIES } from "./reportConfig";

export default function ReportsCategoryTabs() {
  return <nav className="reports-category-tabs" aria-label="Categorias de relatórios">
    {Object.entries(REPORT_CATEGORIES).map(([slug, item]) => <NavLink key={slug} to={`/relatorios/${slug}`} className={({ isActive }) => isActive ? "active" : ""}>{item.label}</NavLink>)}
  </nav>;
}
