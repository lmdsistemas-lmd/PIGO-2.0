# Integração das análises ao PIGO

O GePlug foi usado como referência de interface e comportamento acessíveis pelo site. O PIGO continua usando seu próprio backend, isolamento por tenant/empresa e dados sincronizados do ERP. Nenhum código servidor ou dado comercial do GePlug foi importado.

A revisão ampliada inclui Financeiro, Cadastros, fechamento em oito abas e solicitações ao remote sync agent. O estado por módulo e as diferenças estão em [COMPARATIVO_OPERACIONAL.md](COMPARATIVO_OPERACIONAL.md). A gravação de produção exige o adaptador específico descrito em [GRAVACAO_ERP.md](GRAVACAO_ERP.md).

## Funcionalidades implementadas

- **Clientes** (`/dashboard/clientes`): carteira cadastrada, compradores e novos clientes no período, ticket médio, distribuição por cidade, ranking e clientes sem compras. Tabelas com busca, ordenação, paginação e CSV.
- **Curva ABC** (`/dashboard/curva-abc`): classificação dos produtos por faturamento, participação e percentual acumulado. Os limites são 80% e 95%; o produto que cruza o limite permanece na classe anterior. Valores nulos/negativos são excluídos dessa análise. Há filtro por classe, busca e CSV.
- **Metas de vendas** (`/dashboard/metas`): metas mensais da empresa ou de vendedores com histórico de vendas na empresa, realizado, percentual, falta atingir e projeção pela média de dias corridos. Metas futuras podem usar vendedores com histórico, mesmo sem vendas no mês selecionado. Administradores podem criar, atualizar e excluir. Uma meta por tenant, empresa, mês e responsável, persistida no PostgreSQL pela migration `009_sales_goals.sql`.
- **Relatórios**: seis modelos adicionais no construtor existente: vendas por marca, vendas por vendedor, vendas diárias, clientes por cidade, carteira por vencimento e títulos abertos por cliente. Total de 11 modelos. Os modelos de carteira usam valor nominal de títulos abertos e não deduzem baixas parciais.
- Navegação dos novos módulos no desktop e no menu **Outros** em dispositivos móveis.

## Módulos preservados

O assistente de Relatórios com IA, o Builder, o preview e as exportações existentes foram preservados. Equipe, análise de funcionário, Performance e seus detalhamentos também permanecem. Seus arquivos de implementação foram comparados com o ZIP original, sem alterações.

As análises de clientes, ABC e metas usam a data de faturamento das vendas e excluem status `C` e `CANCELADO`. Os novos modelos de relatórios mantêm o catálogo e a edição existentes; por exemplo, o modelo Vendas diárias usa a data de emissão, indicada em sua descrição.

## Desenvolvimento

Ferramentas validadas: Node.js 24.19, Python 3.12 e PostgreSQL 17. Instale com o lockfile existente:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
```

Configure o backend pelos nomes descritos em `backend/.env.example`, usando seu banco e integração existentes. Não há credenciais reais no projeto. Aplique as migrations antes de iniciar:

```bash
cd backend
python -m scripts.apply_migrations
uvicorn app.main:app --host 127.0.0.1 --port 4000
```

Em outro processo, inicie o frontend com `npm run dev --prefix frontend`. O Vite usa a porta 5176 e encaminha `/api` ao backend na porta 4000.

Na máquina de nuvem preparada, os auxiliares externos ao checkout são:

```bash
bash /workspace/tools/pigo/install.sh
bash /workspace/tools/pigo/start.sh
python /workspace/tools/pigo/smoke.py
```

O auxiliar de banco cria exclusivamente `pigo_development` em PostgreSQL local, publicado somente em loopback na porta 55432, com dados sob `/workspace/.local/pigo-postgres`. A fixture é sintética, limitada por código a esse banco, e gera credenciais temporárias de teste sem imprimi-las. Ela não representa a licença nem os dados de produção do usuário. Os auxiliares de nuvem e essa base não fazem parte do pacote de código.

## Validação

```bash
cd frontend
npm run build
node --test tests/*.test.mjs
npx eslint src/pages/CommercialAnalytics.jsx src/pages/SalesGoals.jsx src/components/AnalyticsTable.jsx src/utils/analytics.js
```

```bash
cd backend
LICENSE_CONTROL_INTEGRATION_TOKEN=test-shared-token python -m unittest discover -s tests
```

O token acima pertence somente à suíte de testes existente. Em produção, a integração continua exigindo o segredo real configurado de forma segura.

Os testes locais cobrem valores de referência, exclusão de cancelamentos, limites ABC, CRUD de metas, tenant/empresa, autenticação, interpretação com IA, preview e navegação desktop/móvel. A integração com dados e License Control de produção não foi executada nesta tarefa.

## Diferenças ainda não implementadas

DRE contábil, fiscal, capital de giro e comissões monetárias ainda não estão implementados integralmente. Cheques, sangrias, fechamento e cadastros receberam consultas e contratos de sincronização, mas dependem do mapeamento real do ERP. O fluxo novo é uma previsão por títulos abertos; saldo bancário inicial e realizado ainda precisam de integração. A arquitetura de licenciamento foi preservada, e o agente foi ampliado para consultas e gravação por procedimento de negócio configurado localmente. Consulte os documentos acima para os limites de cada módulo.
