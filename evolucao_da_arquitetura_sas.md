# Prompt Detalhado — Evolução da Arquitetura SaaS, PostgreSQL e Motor de Relatórios

Estou desenvolvendo o projeto **Painel LMD**, que começou como um dashboard local conectado diretamente ao banco Firebird do cliente, mas agora está evoluindo para uma arquitetura **SaaS profissional**, com sincronismo remoto, banco central em nuvem, relatórios e recursos com IA.

---

# 1. Ideia Inicial do Projeto

A ideia inicial era criar um sistema de sincronismo remoto usando o conceito de **database-per-tenant**.

A proposta era:

* manter o banco Firebird no cliente;
* instalar um agente Python na máquina/servidor do cliente;
* esse agente iria extrair dados do Firebird;
* enviar os dados para a nuvem;
* armazenar os dados em arquivos SQLite isolados por cliente;
* permitir que o dashboard consultasse esses dados sincronizados sem precisar acessar diretamente o servidor do cliente.

A arquitetura inicial seria:

```txt
Firebird Cliente
        ↓
Agent Python
        ↓
FastAPI
        ↓
SQLite por Cliente
        ↓
Dashboard React
```

A ideia era que cada cliente tivesse seu próprio arquivo:

```txt
sync_data/cnpj_do_cliente.db
```

E que o backend decidisse dinamicamente:

```txt
Cliente local  → usa Firebird
Cliente remoto → usa SQLite sincronizado
```

Também foi pensada uma lógica de matriz e filial usando:

```json
{
  "sync_group": "CNPJ_MATRIZ"
}
```

Assim, empresas que compartilham o mesmo Firebird no cliente poderiam compartilhar o mesmo banco na nuvem, separando os dados por `EMP_ID`.

---

# 2. Problemas Identificados na Ideia Inicial

Apesar da proposta inicial funcionar para um MVP simples, ela apresenta limitações para um SaaS profissional.

## Problema 1 — SQLite não é a melhor base para SaaS escalável

SQLite é leve e simples, mas não é a melhor escolha para:

* múltiplos acessos simultâneos;
* relatórios pesados;
* dashboards analíticos;
* histórico grande de dados;
* consultas concorrentes;
* permissões avançadas;
* auditoria;
* IA consultando dados;
* crescimento do produto.

## Problema 2 — Reaproveitar repositories entre Firebird e SQLite pode gerar complexidade

A ideia inicial era reutilizar os repositories existentes de forma transparente entre Firebird e SQLite.

Porém, Firebird e SQLite possuem diferenças em:

* funções SQL;
* tipos de dados;
* datas;
* casts;
* joins;
* paginação;
* performance;
* collation;
* funções específicas.

Isso poderia gerar muitos ajustes condicionais no backend.

## Problema 3 — Sincronismo por “últimas 24h/48h” não é seguro

A proposta inicial previa buscar registros alterados nas últimas 24h/48h.

Isso pode gerar problemas como:

* perda de registros;
* duplicidade;
* timezone;
* relógio errado no cliente;
* registros antigos alterados fora da janela.

O ideal é usar sincronismo incremental controlado por cursor, como:

```txt
last_updated_at
last_id
last_sync_status
```

---

# 3. Nova Decisão Arquitetural

A melhor decisão para o projeto a partir de agora é evoluir diretamente para uma arquitetura SaaS mais profissional usando:

```txt
PostgreSQL + FastAPI + Agent de Sincronismo + Dashboard Cloud
```

A nova arquitetura será:

```txt
Firebird Cliente
        ↓
Remote Sync Agent
        ↓
FastAPI Sync API
        ↓
PostgreSQL Central
        ↓
Dashboard React
```

O dashboard deixará de depender do banco local do cliente e passará a consultar exclusivamente os dados sincronizados na nuvem.

---

# 4. Banco de Dados em Nuvem

A melhor decisão é usar **PostgreSQL centralizado**, e não SQLite.

O PostgreSQL será responsável por armazenar:

* empresas;
* usuários;
* permissões;
* licenças;
* jobs de sincronização;
* tabelas espelhadas do ERP;
* catálogo de relatórios;
* histórico de execuções;
* dados para IA.

Estrutura base sugerida:

```txt
PostgreSQL
├── companies
├── sync_groups
├── sync_jobs
├── report_catalog
├── report_executions
├── tb_pedido_venda
├── tb_pedido_item
├── tb_recebimento
├── tb_pagamento
├── tb_cliente
├── tb_produto
└── tb_usuario
```

---

# 5. Estratégia de Espelhamento

A melhor estratégia neste momento é usar **espelhamento 1:1 controlado**.

Ou seja, as principais tabelas do Firebird serão replicadas no PostgreSQL com nomes semelhantes:

```txt
Firebird:    TB_PEDIDO_VENDA
PostgreSQL:  tb_pedido_venda
```

```txt
Firebird:    TB_RECEBIMENTO
PostgreSQL:  tb_recebimento
```

```txt
Firebird:    TB_PAGAMENTO
PostgreSQL:  tb_pagamento
```

A estrutura será parecida, mas adaptada para PostgreSQL.

Além das colunas originais, cada tabela sincronizada deve receber colunas de controle:

```sql
tenant_id
sync_group_id
emp_id
source_id
source_created_at
source_updated_at
synced_at
```

Essas colunas serão usadas para:

* separar clientes;
* separar grupos matriz/filial;
* identificar o registro original do ERP;
* fazer UPSERT;
* controlar sincronização;
* auditar alterações.

---

# 6. Estratégia do Sync Agent

O agente instalado no cliente será um serviço local.

Ele será responsável por:

* conectar no Firebird;
* autenticar na API com token;
* fazer sincronização inicial completa;
* fazer sincronização incremental;
* manter fila offline;
* reenviar dados em caso de falha;
* registrar status local;
* não executar regras complexas de negócio.

## Primeira execução

Na primeira ativação:

```txt
1. Agent é instalado no servidor do cliente
2. Token da empresa é configurado
3. Agent autentica no backend
4. Backend retorna tenant_id e sync_group_id
5. Agent testa conexão com Firebird
6. Agent executa full sync
7. Backend grava dados no PostgreSQL
8. Dashboard passa a consultar os dados da nuvem
```

## Sincronizações seguintes

Depois da carga inicial, o Agent deve enviar apenas registros novos ou alterados.

Estratégia recomendada:

```sql
WHERE
    updated_at > :last_updated_at
OR (
    updated_at = :last_updated_at
    AND id > :last_id
)
```

Caso alguma tabela não tenha `updated_at`, será necessário usar uma estratégia alternativa:

* data de emissão/cadastro;
* comparação por hash;
* sincronismo por janela controlada;
* tabela auxiliar local;
* triggers no Firebird, se possível.

---

# 7. API de Sincronismo

O backend deve possuir endpoints como:

```txt
POST /api/sync/bootstrap
POST /api/sync/push
POST /api/sync/status
```

O `/bootstrap` autentica o Agent e retorna as configurações do tenant.

O `/push` recebe lotes de registros.

O `/status` registra saúde da sincronização.

O backend deve gravar os dados usando UPSERT:

```sql
ON CONFLICT (sync_group_id, emp_id, source_id)
DO UPDATE SET
    source_updated_at = EXCLUDED.source_updated_at,
    synced_at = NOW();
```

---

# 8. Módulo de Relatórios

A ideia inicial para relatórios era tentar ler/renderizar os arquivos de relatório do ERP, possivelmente usando FastReport.

Porém, foi identificado que essa abordagem pode gerar problemas:

* layouts não ficam fiéis;
* relatórios vêm bagunçados;
* dependência de formato legado;
* manutenção difícil;
* baixa flexibilidade;
* difícil integração com IA;
* difícil gerar SaaS profissional.

A melhor decisão é criar um **motor próprio de relatórios SaaS**.

---

# 9. Nova Estratégia para Relatórios

O sistema deve criar um catálogo próprio de relatórios.

Esse catálogo será armazenado no PostgreSQL na tabela:

```txt
report_catalog
```

Essa tabela não guarda os dados do relatório, mas sim os metadados:

* código;
* nome;
* categoria;
* grupo;
* descrição;
* caminho do SQL;
* filtros disponíveis;
* permissões;
* status ativo/inativo.

Exemplo:

```sql
CREATE TABLE report_catalog (
    id UUID PRIMARY KEY,
    code VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    report_group VARCHAR(100),
    description TEXT,
    sql_path VARCHAR(255) NOT NULL,
    filters JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Os SQLs dos relatórios devem ficar versionados no backend:

```txt
backend/
├── reports/
│   ├── sales/
│   │   ├── produtos_vendidos.sql
│   │   ├── vendas_por_vendedor.sql
│   │   └── recebimentos.sql
│   ├── financial/
│   │   ├── contas_receber.sql
│   │   └── contas_pagar.sql
│   └── templates/
```

---

# 10. Como os Relatórios Devem Funcionar

A tela de relatórios deve listar os relatórios cadastrados no `report_catalog`.

Fluxo:

```txt
1. Usuário abre a aba Relatórios
2. Frontend chama GET /api/reports
3. Backend retorna os relatórios disponíveis
4. Usuário clica em Visualizar
5. Frontend abre filtros do relatório
6. Usuário informa período, empresa, vendedor etc.
7. Frontend chama POST /api/reports/{id}/execute
8. Backend carrega o SQL correspondente
9. Backend aplica filtros seguros
10. Backend executa no PostgreSQL
11. Frontend exibe preview em tabela/gráfico
12. Usuário pode exportar PDF ou Excel
```

---

# 11. FastReport

A decisão recomendada é:

```txt
Não usar FastReport como motor principal do SaaS.
```

FastReport pode ser usado apenas como referência ou compatibilidade legada, caso necessário.

Melhor uso:

```txt
FastReport antigo = referência visual ou regra
SQL do relatório = reaproveitado quando possível
Layout novo = criado no SaaS
```

Assim, o sistema evita depender de layouts antigos e permite criar uma experiência mais moderna.

---

# 12. Relatórios com IA

O módulo de IA deve usar o catálogo de relatórios como base.

A IA não deve consultar diretamente qualquer tabela bruta sem controle.

Ela deve trabalhar com:

* report_catalog;
* views seguras;
* SQLs aprovados;
* permissões por tenant;
* filtros controlados.

Exemplo:

Usuário pergunta:

```txt
Quais produtos mais venderam este mês?
```

A IA identifica:

```txt
Relatório: Análise de Produtos Vendidos
SQL: sales/produtos_vendidos.sql
Filtros: mês atual
```

Depois executa de forma segura e retorna:

* tabela;
* gráfico;
* resumo;
* insights;
* sugestão de ação.

---

# 13. O Que Pode Ser Feito Agora

Mesmo antes de concluir a migração para PostgreSQL, já é possível adiantar o módulo de relatórios.

Porém, a recomendação é começar a migração para PostgreSQL desde já.

Ordem recomendada:

```txt
1. Criar PostgreSQL base
2. Criar tabelas administrativas
3. Criar report_catalog
4. Criar estrutura backend/reports
5. Criar endpoint GET /api/reports
6. Criar endpoint POST /api/reports/{id}/execute
7. Criar primeiros SQLs de relatórios
8. Iniciar espelhamento das tabelas do ERP
9. Fazer dashboard consultar PostgreSQL
10. Evoluir IA em cima do catálogo
```

---

# 14. Melhor Decisão de Agora em Diante

A melhor decisão técnica para o projeto é:

```txt
Migrar a base principal para PostgreSQL agora
```

e, em paralelo:

```txt
Criar o motor próprio de relatórios
```

A prioridade deve ser:

```txt
PostgreSQL + Sync Agent + Report Catalog
```

O projeto deve evitar investir tempo em renderização de relatórios legados do ERP, pois isso tende a gerar retrabalho.

---

# 15. Decisão Final

A arquitetura final recomendada é:

```txt
Firebird Cliente
        ↓
Agent de Sincronismo
        ↓
FastAPI
        ↓
PostgreSQL Central
        ↓
Motor de Relatórios
        ↓
Dashboard React
        ↓
Relatórios com IA
```

O SaaS deve evoluir com estas bases:

* PostgreSQL como banco central;
* espelhamento 1:1 das principais tabelas do ERP;
* sincronização inicial completa;
* sincronização incremental depois;
* UPSERT no backend;
* catálogo próprio de relatórios;
* SQLs versionados no backend;
* exportação PDF/Excel;
* IA usando relatórios e views seguras;
* FastReport apenas como referência ou legado.

Essa é a rota mais segura, profissional e escalável para transformar o Painel LMD em um SaaS robusto.
