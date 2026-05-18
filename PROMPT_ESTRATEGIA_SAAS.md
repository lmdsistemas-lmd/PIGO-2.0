# PROMPT ESTRATÉGICO: Evolução SaaS Painel LMD

Este documento serve como a "Fonte da Verdade" e o "Roadmap Mestre" para o desenvolvimento do projeto **Painel LMD**. Ele descreve o estado atual, a visão de futuro e a ordem lógica de implementação para transformar o sistema em um SaaS profissional escalável.

---

## 1. O PROJETO: Painel LMD SaaS
O **Painel LMD** é uma plataforma de Business Intelligence e Dashboard voltada para empresas que utilizam ERPs baseados em **Firebird**. 
*   **Missão:** Democratizar o acesso a indicadores (KPIs), relatórios avançados e insights de IA para clientes que possuem dados "presos" em servidores locais.
*   **Modelo de Negócio:** SaaS Multi-tenant onde o cliente paga pela licença de uso e visualiza seus dados na nuvem, sem necessidade de configurações complexas de infraestrutura (VPN/IP Fixo).

---

## 2. ESTADO ATUAL (Onde estamos)
*   **Backend (FastAPI):** Conecta-se diretamente aos bancos Firebird dos clientes (modo local/híbrido).
*   **Admin System (Next.js):** Gerencia empresas e licenças básicas.
*   **Frontend (React/Vite):** Dashboard moderno e premium, mas dependente de conexão direta ou arquivos JSON legados.
*   **Banco de Dados Administrativo:** MySQL (rodando localmente).
*   **Sincronismo:** Existe um rascunho de agente em Python, mas a arquitetura de recebimento de dados ainda não está consolidada no modelo SaaS.

---

## 3. O PRÓXIMO PASSO: A Virada de Chave (PostgreSQL)
A decisão estratégica é migrar toda a inteligência e armazenamento central para **PostgreSQL**.
*   **Por que Postgres?** Suporte nativo a JSONB (para filtros dinâmicos), alta performance para analytics, robustez para IA e facilidade de escala.
*   **Estratégia de Espelhamento:** As tabelas do ERP serão espelhadas 1:1 no Postgres, adicionando colunas de controle (`tenant_id`, `sync_group_id`, `source_id`, `last_updated_at`).
*   **Fim do Legado:** Substituição do FastReport por um motor de relatórios próprio baseado em SQL versionado.

---

## 4. O FUTURO (Onde vamos chegar)
*   **IA de Performance:** Um assistente que não apenas mostra gráficos, mas "lê" o banco de dados e sugere ações (ex: "Sua margem no produto X caiu 10% devido ao aumento do CMV").
*   **Autonomia Total:** Sincronismo em tempo real (ou quase real) via Agente Silencioso no cliente.
*   **Escalabilidade Infinita:** Capacidade de gerenciar centenas de empresas em um único banco centralizado com isolamento lógico rigoroso.

---

## 5. ORDEM DE DESENVOLVIMENTO RECOMENDADA

Para garantir uma transição suave e sem quebras, seguiremos esta ordem:

### Fase 1: Infraestrutura e Base Administrativa (O Alicerce)
1.  **Setup PostgreSQL:** Instalação e configuração do banco.
2.  **Schema Administrativo:** Criar tabelas de `tenants`, `users`, `licenses` e `sync_jobs`.
3.  **Refatoração do Backend:** Migrar a conexão administrativa de MySQL para PostgreSQL.

### Fase 2: Camada de Sincronismo (O Coração)
4.  **Sync API:** Criar endpoints para o agente local enviar dados (UPSERT).
5.  **Refatoração do Agente:** Ajustar o script Python no cliente para fazer o "Push" de dados incremental.
6.  **Carga Inicial:** Realizar o primeiro espelhamento de tabelas críticas (`Vendas`, `Financeiro`, `Estoque`).

### Fase 3: Motor de Relatórios e Dashboard (A Entrega de Valor)
7.  **Report Catalog:** Implementar a estrutura de metadados de relatórios.
8.  **Migração de Repositories:** Alterar o Dashboard para ler do Postgres Cloud em vez do Firebird Local.
9.  **Exportação:** Sistema de geração de PDF/Excel próprio.

### Fase 4: Inteligência Artificial (O Diferencial)
10. **Integração LLM:** Conectar a IA ao catálogo de relatórios e views do Postgres para análise de dados.

---

## 💡 Diretriz de Implementação para a IA:
> "Sempre que formos trabalhar em uma funcionalidade, consulte este roadmap. A prioridade agora é a **Fase 1: Setup do PostgreSQL e Schema Administrativo**. Não devemos avançar para relatórios sem que a base de dados sincronizada esteja íntegra."
