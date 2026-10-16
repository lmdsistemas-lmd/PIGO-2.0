# Correspondência com a estrutura recebida do ERP

O JSON recebido em 16/10/2026 contém 468 tabelas, 9.022 campos, 432 definições de chave primária, 189 relações de chave estrangeira, 11 geradores, 219 parâmetros de procedimentos e uma trigger. Ele permitiu confirmar os nomes e vínculos abaixo. Não contém registros comerciais, corpos SQL dos procedimentos, defaults ou regras de validação. O JSON completo permanece fora do código e do pacote.

## Contratos corrigidos

| Origem confirmada | Tratamento no PIGO |
| --- | --- |
| `TB_PROD_SUB_GRUPO` | Sincronizada no contrato `TB_PROD_SUBGRUPO`, incluindo a empresa |
| `PLC_PAI`, `PLC_TIPO_CONTA` | Correspondem a `PLC_CONTA_PAI`, `PLC_TIPO`; `PLC_DRE` continua ausente |
| `TB_CHEQUE_EMITIDO`, campos `CHE_*` | Correspondência explícita para o espelho `CHQ_*`; pessoa e nominal preservados sem pressupor fornecedor |
| Grupos, marcas, subgrupos e plano de contas | Consultas filtradas pela empresa além do tenant; espelhos antigos sem empresa precisam ser atualizados |
| `CLI_STATUS`, `CLI_DT_CADASTRO` | Preferidos no cadastro de clientes; campos de pessoa continuam como compatibilidade para espelhos antigos |
| `PRDE_PRODUTO/EMPRESA/LOCAL/VARIACAO` | Chave completa do estoque, preservando cada posição |
| `TB_PROD_CODIGO_BARRAS` | Códigos consultados por empresa/produto sem multiplicar a listagem nem presumir qual é o principal |
| `TB_PRODUTO_PRECO` | Campos de preço/custo por empresa sincronizados; os preços do cadastro do produto continuam identificados como tais |
| Empresa + ID de pedidos, títulos a receber e a pagar | Chaves compostas para impedir sobrescrita entre empresas |
| `PEV_FECHAMENTO` | Vínculo de pedidos ao fechamento; itens mantêm empresa/pedido/sequência |
| Documento, espécie, centro de custo e plano de contas dos títulos | Novas colunas de consulta; códigos da origem sem classificação presumida |

Correspondências locais explícitas em `OPERATIONS_MAP_FILE` continuam tendo prioridade. Campos canônicos existentes também são preservados quando presentes. Só são selecionadas colunas existentes e permitidas; não se usa `SELECT *` nos cadastros financeiros.

Não foi encontrada uma tabela de departamentos de produtos. `PRD_SETOR` não foi convertido em departamento sem confirmação. Grupos, subgrupos e marcas não têm os campos de status previstos no contrato antigo; a ausência continua visível. O código de barras desta instalação fica em tabela própria, separado do campo editável de um contrato legado.

## Estoque: posições, sem total presumido

O usuário não soube informar se o total do ERP considera todos os locais e variações. A listagem apresenta o número de posições e exibe uma quantidade somente quando existe exatamente uma posição. Múltiplas posições ou quantidade desconhecida produzem `null`, representado por “—”. Zero continua sendo zero.

O detalhe mostra local, variação e quantidade separadamente. A relação é agrupada antes da junção à listagem; dois códigos de barras e duas posições não viram quatro produtos. As consultas respeitam tenant, empresa e produto.

Os dashboards antigos de Estoque e o bloco de estoque crítico do Financeiro pressupunham uma posição por produto. Se a empresa tiver múltiplas posições ou quantidades desconhecidas, os indicadores que dependem do total ficam explicitamente indisponíveis. Isso inclui valores, alertas e tabelas do dashboard de Estoque. Os outros módulos continuam disponíveis. Essa restrição poderá ser removida após confirmar a consolidação oficial; não é correto escolher `MAX`, somar ou tratar ausência como zero sem essa regra.

## Fechamentos de caixa

Vendas exibe os pedidos vinculados por empresa e `PEV_FECHAMENTO`, com os status originais. Produtos vendidos mostra os itens desses pedidos, inclusive linhas repetidas e pedidos com cancelamento registrado, com identificação explícita desse estado. Vendas canceladas consulta os pedidos com data de cancelamento registrada; nenhum código de status desconhecido é convertido em cancelamento por inferência.

Totais, diferenças, débitos/créditos e composição por forma do fechamento continuam vindo de `FCX/FCXI/FCXV`. Não são recalculados somando pedidos. `MOV_TIPO` e `MOV_ORIGEM` continuam como códigos. O JSON não informa a semântica desses códigos para classificar recebimentos, pagamentos, sangrias ou suprimentos. `REC_FECHAMENTO` vincula um título, mas não prova uma entrada de caixa; seu valor nominal não é apresentado como recebimento.

O detalhe inclui somente o histórico efetivamente sincronizado. Consultas de detalhe limitam cada coleção a 10.000 linhas e informam truncamento; cancelamentos são consultados separadamente para não desaparecerem por causa do limite da lista geral de pedidos.

## Financeiro: saldos ainda dependem das rotinas oficiais

`REC_VALOR` e `PAG_VALOR` são valores nominais. Não existem os campos `REC/PAG_VALOR_ABERTO`, `VALOR_BAIXADO` e `DT_PAGAMENTO` esperados pelo contrato opcional anterior. Os itens `RIT/PIT` têm códigos de ação cuja semântica não foi exportada. Não são somados como se toda ação fosse baixa.

Foram encontrados os seguintes contratos de procedimentos:

| Procedimentos | Entradas | Saída |
| --- | --- | --- |
| `SP_REC_ABERTO`, `SP_RECEBIMENTO_ABERTO` | EMPRESA, RECEBIMENTO, DATA | VALOR_ABERTO |
| `SP_PAG_ABERTO`, `SP_PAGAMENTO_ABERTO` | EMPRESA, PAGAMENTO, DATA | VALOR_ABERTO |
| `SP_SALDO_CAIXA` | EMPRESA, CAIXA, DATA_SALDO | VALOR_SALDO |
| `SP_SALDO_CONTA_BANCARIA` | EMPRESA, BANCO, BANCO_AGENCIA, NUMERO_CONTA, DATA_SALDO | VALOR_SALDO |

Os corpos SQL ou a documentação dessas rotinas ainda são necessários para confirmar cálculo, cancelamentos, datas, efeitos colaterais e forma de chamada. Nenhuma foi executada automaticamente apenas pelo nome. Com o contrato atual desse ERP, a previsão por saldo permanece indisponível até existir um adaptador validado. O valor nominal não substitui o saldo, e a previsão não representa saldo bancário disponível.

## Gravação: dependência de negócio restante

O transporte PIGO → fila → agent → Firebird e o recibo transacional permanecem implementados, mas a gravação continua desligada. A estrutura confirma pessoas, vínculos de cliente/fornecedor e produtos, porém não explica como o ERP cria esses registros.

Há uma tabela `TB_SEQUENCIAL` com empresa, tabela e sequencial, sem chave primária exportada. Isso não prova se armazena o último ou o próximo número, nem como trata concorrência. Os geradores recebidos não fornecem uma regra genérica confirmada para esses cadastros. Não foi implementado `MAX + 1` nem uma atualização presumida de `TB_SEQUENCIAL`.

Para concluir o procedimento descrito em [GRAVACAO_ERP.md](GRAVACAO_ERP.md), faltam as rotinas ou regras oficiais para gerar IDs, preencher campos obrigatórios, validar alterações e criar vínculos dependentes, inclusive em concorrência. Essas regras devem ser homologadas em uma cópia de teste do ERP.

## Migração e validação

Não atualizar o agente de produção misturando escritores com chaves diferentes. Se o espelho antigo já perdeu local/variação ou empresa, a migração automática é bloqueada com `MIRROR_KEY_MIGRATION_REQUIRED` quando faltarem chaves em registros armazenados. É necessário preservar o espelho e homologar uma recarga com as chaves reais, em banco de teste ou espelho separado, antes da troca. O código não inventa chaves nem apaga registros para contornar o erro.

Os testes novos em [test_operations_real_schema.py](../backend/tests/test_operations_real_schema.py) usam PostgreSQL descartável com linhas sintéticas, dois tenants, empresas diferentes, múltiplos locais/variações, estoque zero/desconhecido, vários códigos de barras e itens repetidos de pedidos. Para executá-los, crie um banco local vazio com nome iniciado por `pigo_schema_test_`, configure `PIGO_SCHEMA_TEST_DATABASE_URL` com sua conexão SQLAlchemy e rode `python -m unittest discover -s tests -p test_operations_real_schema.py -v` na pasta backend. O teste recusa banco remoto, nome diferente ou schema já preenchido. Sem essa variável, esses testes ficam identificados como ignorados.

Relatórios com IA, Equipe e Performance permanecem preservados. Nenhuma consulta ou gravação no ERP de produção foi feita na nuvem; a estrutura foi fornecida pelo usuário. Não foi gerado instalador Windows nem publicada uma implantação.
