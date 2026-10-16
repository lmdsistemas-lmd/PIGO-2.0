export const REPORT_CATEGORIES = {
  vendas: { key: "sales", label: "Vendas", title: "Relatórios de Vendas", description: "Analise pedidos, produtos, clientes e vendedores." },
  financeiro: { key: "finance", label: "Financeiro", title: "Relatórios Financeiros", description: "Acompanhe recebimentos, vencimentos e carteira financeira." },
  contabilidade: { key: "accounting", label: "Contabilidade", title: "Relatórios Contábeis", description: "Fontes contábeis planejadas para próximas integrações." },
  outros: { key: "other", label: "Outros", title: "Outros Relatórios", description: "Explore novas áreas analíticas conectadas ao PIGO." },
};

export const CATEGORY_BY_KEY = Object.fromEntries(Object.entries(REPORT_CATEGORIES).map(([slug, value]) => [value.key, { slug, ...value }]));
export const CHARTS = { table: "Tabela", cards: "Cards", bar: "Barras", line: "Linha", pie: "Pizza", area: "Área" };
export const ROLES = [["all", "Todos"], ["administrator", "Administrador"], ["supervisor", "Supervisor"], ["finance", "Financeiro"], ["sales", "Vendas"], ["user", "Usuário"]];
export const EMPTY_FORM = { name: "", description: "", source: "", fields: [], filters: [], group_by: [], order_by: [], totals: [], chart: "table", permissions: ["all"] };
export const DEFAULT_WHITE_LABEL = { mode: "company", companyName: "PIGO", title: "", subtitle: "", primaryColor: "#2563eb", secondaryColor: "#0f172a", header: true, footer: true, footerText: "Gerado pelo PIGO", issueDate: true, responsibleUser: true, appliedFilters: true, pagination: true, orientation: "portrait", paperSize: "A4" };
export const ASSISTANT_EXAMPLES = ["Vendas por produto deste mês", "Recebimentos em aberto por cliente", "Clientes por cidade"];
export const BUSINESS_LABELS = { revenue: "Faturamento", open_receivable: "Em aberto", receivable: "A receber", customer_count: "Quantidade de clientes", product_count: "Quantidade de produtos", seller: "Vendedor", customer: "Cliente", product: "Produto", city: "Cidade", group: "Grupo", brand: "Marca" };
export const PERIOD_LABELS = { today: "Hoje", yesterday: "Ontem", current_week: "Esta semana", last_week: "Semana passada", current_month: "Este mês", previous_month: "Mês passado", current_quarter: "Este trimestre", last_quarter: "Último trimestre", current_year: "Este ano", previous_year: "Ano passado", last_7_days: "Últimos 7 dias", last_30_days: "Últimos 30 dias", last_90_days: "Últimos 90 dias" };
