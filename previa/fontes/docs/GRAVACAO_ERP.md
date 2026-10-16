# Gravação pelo remote sync agent

A estrutura real foi recebida; [ESTRUTURA_ERP_CONFIRMADA.md](ESTRUTURA_ERP_CONFIRMADA.md) registra o que ela confirma e por que ainda não define a geração de IDs nem as validações de cadastro.

## Preparação no ERP

Não habilite `WRITEBACK_ENABLED` antes de mapear e homologar as regras de negócio no banco de teste do ERP. O repositório recebido contém consultas, não as rotinas de cadastro do ERP.

O administrador do banco instala uma vez [001_command_receipt.sql](../remote-sync-agent/sql/001_command_receipt.sql), usando uma cópia de teste antes de produção. A tabela `PIGO_COMMAND_RECEIPT` guarda solicitação, hash e retorno; não deve ser apagada enquanto houver possibilidade de reenvio. Depois, implementa um procedimento executável específico para o ERP com sete parâmetros de entrada, nesta ordem:

| Entrada | Tipo recomendado | Conteúdo |
| --- | --- | --- |
| REQUEST_ID | VARCHAR(36) | Identificador estável da solicitação |
| COMPANY_ID | INTEGER | Empresa do ERP, a ser validada na origem |
| RESOURCE | VARCHAR(40) | clientes, fornecedores, produtos, departamentos, grupos, subgrupos, marcas ou plano-contas |
| ACTION | VARCHAR(10) | create ou update |
| RECORD_ID | VARCHAR(100), nullable | Código existente; criação deve gerar o código conforme o ERP |
| PAYLOAD_JSON | BLOB SUB_TYPE TEXT | Campos alterados, no vocabulário do PIGO |
| EXPECTED_JSON | BLOB SUB_TYPE TEXT | Valores anteriores dos campos alterados; vazio na criação |

Retorno de uma única linha: `RESULT_STATUS VARCHAR(20)` com `applied` ou `rejected`, `RECORD_ID VARCHAR(100)` e `MESSAGE VARCHAR(300)`. Uma confirmação exige código do ERP. Recusa deve trazer mensagem útil sem senha, SQL interno ou detalhes de conexão.

O procedimento deve validar empresa, acesso ao registro, tipos, referências, campos obrigatórios e regras do ERP. Para edição, compara os valores anteriores dentro da transação e recusa conflito, incluindo registro excluído ou movido de empresa. Criação deve usar os geradores/rotinas oficiais e criar vínculos dependentes. Os campos do formulário são o conjunto comum inicial e podem precisar de extensão após conhecer os requisitos reais.

**Não use transações autônomas para a alteração de negócio.** O executor confirma gravação e recibo juntos. Se houver exceção, ambos são desfeitos e o comando pode ser retomado após o prazo da reserva. Se a rotina retornar `rejected`, o executor desfaz a transação de negócio e confirma apenas um recibo da recusa em outra transação.

O agente não oferece execução arbitrária de SQL e não escolhe o procedimento a partir de dados enviados pela internet. O nome é configurado localmente e validado como identificador. O procedimento e sua análise de JSON devem ser implementados de acordo com a versão do Firebird e a lógica do ERP, que ainda precisam ser confirmadas.

## Configuração local do agente

```dotenv
WRITEBACK_ENABLED=false
WRITEBACK_PROCEDURE=
WRITEBACK_RESOURCES=clientes,fornecedores,produtos,grupos,marcas,departamentos,subgrupos,plano-contas
OPERATIONS_MAP_FILE=operations-map.json
```

Após instalar e homologar o procedimento, informe seu nome em `WRITEBACK_PROCEDURE`, mantenha apenas os recursos efetivamente suportados em `WRITEBACK_RESOURCES` e ative `WRITEBACK_ENABLED=true`. O agente verifica a presença do procedimento e da tabela de recibos antes de buscar comandos. A consulta ocorre a cada 15 segundos entre ciclos de leitura. Como o agente tem um único agendador, uma carga de sincronização longa pode adiar essa consulta. O PIGO considera o anúncio do agente recente por dez minutos.

O API token e o CNPJ existentes continuam vinculados ao mesmo tenant e passam pela validação de licença. Não coloque valores reais no repositório.

## Correspondência das consultas operacionais

O catálogo permitido está em [operational_sync.py](../remote-sync-agent/operational_sync.py). O agente atual sincroniza os contratos físicos de fechamento separadamente desse catálogo operacional. Quando os nomes auxiliares do ERP coincidirem com os canônicos, a leitura é automática. Caso contrário, um `operations-map.json` local pode declarar `table` e `fields`, por tabela canônica. As chaves de `fields` são os nomes canônicos e os valores são nomes reais confirmados no diagnóstico. Não são aceitas expressões SQL. Campos de saldo e conferência devem representar o valor correto na origem; não mapeie valor nominal como saldo.

As formas de fechamento usam `TB_FECHAMENTO_CAIXA_FORMA` e os movimentos normalizados usam `TB_PIGO_CAIXA_MOVIMENTO`, sempre com empresa e fechamento. `FCI_TIPO` deve ser normalizado na origem para `vendas`, `produtos`, `recebimentos`, `pagamentos`, `sangrias`, `suprimentos` ou `canceladas`. Se a origem exige junções/cálculos, crie um adaptador revisado; uma simples troca de nomes não resolve essa semântica.

Os campos financeiros `REC/PAG_VALOR_ABERTO`, `REC/PAG_VALOR_BAIXADO` e `REC/PAG_DT_PAGAMENTO` são reconhecidos quando presentes com esses nomes. Nomes diferentes e saldos calculados por procedimentos exigem um adaptador adicional. Ausência desses dados mantém a previsão indisponível.

## API e retomada

- Administradores: `GET/POST /api/erp/cadastros/{resource}`. O POST usa `request_id` UUID, `empresa_id`, `action`, `record_id`, `payload` e `expected`. O mesmo ID/conteúdo retorna a solicitação existente; conteúdo diferente é recusado.
- Agente: `POST /api/sync/commands/claim`, com CNPJ e recursos, e `POST /api/sync/commands/{id}/ack`, com CNPJ, `lease_token` e resultado. O JWT de usuário não substitui o API token do agente.
- Após erro temporário, a solicitação permanece em processamento até expirar a reserva de cinco minutos. Outra tentativa reutiliza o recibo Firebird se a gravação já tiver ocorrido.
- Solicitações recusadas são finais. Corrija os campos e envie uma nova solicitação; o mesmo ID não representa uma nova intenção.

Na versão atual, configuração desktop/cofre e agendamento pelo owner são descritos em [AGENTE_ATUAL.md](AGENTE_ATUAL.md). A configuração desktop de `writeback` tem prioridade sobre variáveis herdadas.

Os formulários não editam estoque físico nem títulos financeiros. O código do ERP é atribuído pela origem. A confirmação de gravação e a atualização da consulta por sincronização são etapas distintas.

## Testes

```bash
cd remote-sync-agent
API_TOKEN=test-agent-token COMPANY_CNPJ=00000000000191 API_BASE_URL=https://pigo.example.invalid/api python -m unittest
```

Os valores acima são fictícios e as chamadas HTTP dos testes unitários são simuladas. Foram testados separadamente transações e recibos em Firebird 5 real descartável, com procedimento sintético, e o protocolo da fila contra PostgreSQL local. Nenhum desses testes homologa as regras de cadastro do ERP de produção.
