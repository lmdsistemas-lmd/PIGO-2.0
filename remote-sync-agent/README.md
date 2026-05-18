# Agente de Sincronismo LMD Dashboard

Este é um serviço independente projetado para rodar em máquinas locais (clientes) que possuem o banco de dados Firebird. Ele coleta indicadores e os envia automaticamente para o Dashboard Central.

## Instalação (No Cliente)

1. **Requisitos**:
   - Python 3.8 ou superior instalado.
   - DLL do Firebird (`fbclient.dll`) disponível na máquina.

2. **Configuração**:
   - Copie a pasta `remote-sync-agent` para o computador do cliente.
   - Edite o arquivo `.env` (ou renomeie o `.env.example` para `.env` se não existir).
   - Preencha as informações:
     - `FB_DATABASE`: Caminho completo do arquivo `.FDB`.
     - `FB_CLIENT_PATH`: Caminho da `fbclient.dll`.
     - `API_BASE_URL`: O endereço IP/URL do seu servidor Dashboard (ex: `http://seu-ip:3000/api`).
     - `API_TOKEN`: O token gerado no Admin para esta empresa.
     - `COMPANY_CNPJ`: O CNPJ da empresa cadastrada.

3. **Execução**:
   - Execute o arquivo `run.bat`. Ele criará o ambiente virtual e instalará as dependências na primeira execução.

## Estrutura de Dados Enviada

O agente envia dois tipos de indicadores por padrão:
- `VENDAS`: Faturamento do mês e contagem de pedidos.
- `FINANCEIRO`: Total de inadimplência (contas vencidas).

Você pode adicionar novos indicadores editando o arquivo `agent.py` e criando novas funções `fetch_...`.

## Logs
Verifique o arquivo `agent.log` para conferir se o sincronismo está ocorrendo corretamente ou se há erros de conexão/banco de dados.
