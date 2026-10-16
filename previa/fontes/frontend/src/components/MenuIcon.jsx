const paths = {
  acesso: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6',
  gestao: 'M4 19V5M4 19h16M8 15l4-5 4 3 4-7',
  financeiro: 'M3 6h18v14H3zM6 6V3h12v3M16 11h5v5h-5z',
  cadastros: 'M3 7V5h7l2 3h9v12H3zM12 11v6M9 14h6',
  relatorios: 'M6 3h9l4 4v14H6zM14 3v5h5M9 17v-4M13 17v-6M16 17v-3',
  equipe: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5',
  performance: 'm12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
  estoque: 'm3 7 9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10M7 5l10 4',
  consolidado: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  recolher: 'm14 6-6 6 6 6M20 4v16',
  expandir: 'm10 6 6 6-6 6M4 4v16',
};
export default function MenuIcon({ name }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.gestao} /></svg>;
}
