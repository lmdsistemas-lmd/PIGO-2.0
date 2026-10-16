export const OPERATION_GROUPS = [
  { title: "Financeiro", prefix: "/financeiro", items: [
    ["receber", "Contas a Receber"], ["pagar", "Contas a Pagar"], ["fechamentos", "Fechamentos de Caixa"],
    ["fluxo-caixa", "Fluxo de Caixa"], ["cheques", "Cheques Emitidos"], ["sangrias", "Sangrias"],
  ] },
  { title: "Pessoas", prefix: "/cadastros", items: [["clientes", "Clientes"], ["fornecedores", "Fornecedores"]] },
  { title: "Produtos", prefix: "/cadastros", items: [["produtos", "Produtos"], ["departamentos", "Departamentos de produtos"], ["grupos", "Grupos de produtos"], ["subgrupos", "Subgrupos de produtos"], ["marcas", "Marcas"]] },
  { title: "Diversos", prefix: "/cadastros", items: [["plano-contas", "Plano de Contas"]] },
];
export const OPERATIONS = OPERATION_GROUPS.flatMap((group) => group.items.map(([resource, title]) => ({ resource, title, group: group.title, path: `${group.prefix}/${resource}` })));
