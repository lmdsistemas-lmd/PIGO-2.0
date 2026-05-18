Viewed companies.json:1-17

Aqui está um resumo completo (prompt) do estado atual do seu projeto, organizado por módulos, para que você possa usar como referência ou para me situar em futuras conversas:

---

### 🚀 Resumo do Projeto: Dashboard - Painel LMD

O projeto evoluiu de um dashboard local para uma arquitetura **SaaS Multi-tenant**, com gerenciamento centralizado de licenças e coleta remota de dados.

#### 1. 🏗️ Arquitetura do Sistema
*   **Frontend (React + Vite)**: Interface principal de análise para os clientes finais.
*   **Backend (FastAPI)**: API de suporte e ponte para consultas em tempo real.
*   **Admin System (Next.js + Prisma + SQLite)**: O "cérebro" do sistema. Gerencia empresas, usuários administrativos, permissões e licenças.
*   **Remote Sync Agent (Python)**: Serviço que roda no servidor do cliente para extrair dados do Firebird e enviá-los via nuvem para o Dashboard.

#### 2. 🛠️ Módulos e Funcionalidades Recentes
*   **Gerenciamento de Empresas**: O Admin agora possui uma lista completa de clientes com controle de status (Ativo/Inativo), plano e data de vencimento.
*   **Segurança por API Token**: Cada empresa possui um token exclusivo (UUID) visível no Admin. Esse token é usado pelo Agente Remoto para se autenticar sem expor senhas do banco de dados.
*   **Sincronismo Remoto**: Criada uma solução que elimina a necessidade de abrir portas no roteador do cliente ou usar VPN. O agente faz o "push" dos dados de Vendas e Financeiro de forma automática.
*   **Correção de Compatibilidade**: O Agente foi otimizado para rodar tanto em Python 3.12 quanto no 3.13 (com patch para a biblioteca `fdb`).

#### 3. 📂 Estrutura de Arquivos Principal
*   `/frontend`: Dashboard de indicadores.
*   `/backend`: API de processamento Python.
*   `/admin-system`: Painel administrativo (Porta 3000).
*   `/remote-sync-agent`: Pasta pronta para ser enviada ao cliente, contendo o instalador (`run.bat`) e o coletor.

#### 4. 🚦 Status Atual e Próximos Passos
*   **Agente no Cliente**: Em fase de configuração de ambiente (ajuste de DLLs de 32/64 bits e caminhos de banco no `.env`).
*   **Interface**: O Painel Admin já exibe os tokens de acesso e permite a cópia rápida para configuração.
*   **Próximo Passo Sugerido**: Validar o recebimento do primeiro lote de dados remotos e exibi-los nos gráficos do dashboard principal.

