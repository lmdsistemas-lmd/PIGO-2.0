# P.I.G.O Dashboard Remote Sync Agent

Este agente deve rodar na maquina do cliente onde o ERP/Firebird esta acessivel.
Ele nao precisa ficar na mesma maquina do P.I.G.O Dashboard.

## Configuracao

1. Copie `.env.example` para `.env`.
2. Configure os dados reais do ERP:
   - `FB_HOST`
   - `FB_PORT`
   - `FB_DATABASE`
   - `FB_USER`
   - `FB_PASS`
   - `FB_CLIENT_PATH`
3. Configure a API oficial:
   - `API_BASE_URL=https://pigo.lmdsistemasdev.qzz.io/api`
   - `API_TOKEN=<token exclusivo do tenant fornecido pela LMD>`
   - `COMPANY_CNPJ=<cnpj somente numeros>`
4. Execute `run.bat`.

## Tabelas

O agente sincroniza as tabelas espelhadas do ERP, incluindo `TB_USUARIO` com:

- `USU_ID`
- `USU_LOGIN`
- `USU_NOME`
- `USU_SENHA`
- `USU_ADMINISTRADOR`

Esses campos sao usados pelo dashboard para autenticar com as mesmas credenciais do ERP.

## Financeiro adaptativo

Antes de sincronizar o financeiro, o agente le o schema real do Firebird e gera
`schema_diagnostics.json` com:

- todas as tabelas;
- campos das tabelas usadas;
- chaves primarias;
- chaves estrangeiras.

Para contas a receber, o agente envia sempre o formato canonico `TB_RECEBIMENTO`.
Se `TB_CONTAS_RECEBER` nao existir, ele procura automaticamente equivalentes como:

- `TB_RECEBIMENTO`
- `TB_CONTA_RECEBER`
- `TB_TITULO_RECEBER`
- `TB_RECEBER`

Para contas a pagar, o agente envia sempre o formato canonico `TB_PAGAMENTO`.
Ele procura equivalentes como:

- `TB_PAGAMENTO`
- `TB_CONTAS_PAGAR`
- `TB_CONTA_PAGAR`
- `TB_TITULO_PAGAR`
- `TB_PAGAR`

O mapeamento tambem valida campos usados em pessoas, recebimentos, pagamentos,
contas, plano de contas, borderos e movimentos financeiros. Quando uma tabela
esperada nao existe, o log informa a tabela equivalente encontrada.

## Logs

O agente grava `agent.log`. O log nao deve conter senha ou token. Em caso de erro, valide porta,
caminho do `.FDB`, DLL do Firebird e conectividade HTTPS com `https://pigo.lmdsistemasdev.qzz.io/health`.

Os logs financeiros incluem SQL executado, tabela utilizada, quantidade de
registros, tempo de execucao e erro completo quando houver falha.
