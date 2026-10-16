# Comparação operacional e estado da ampliação

O painel acessível em `painel.lmdsistemasweb.com.br` foi consultado com o acesso autorizado pelo usuário. Foram observadas telas de Gestão, Financeiro, Cadastros de Pessoas/Produtos/Diversos e o detalhe de um fechamento. A primeira integração de Clientes, ABC e Metas não cobria essas áreas. O painel de referência tem funcionalidades mais amplas que a versão inicial do PIGO.

O usuário definiu como obrigatórios Relatórios com IA, Equipe e Performance. Também definiu fechamento **e** fluxo de caixa como prioridades e confirmou que cadastros devem ser gravados no ERP pelo remote sync agent, mantendo o banco do PIGO separado.

A revisão seguinte incorporou o agente atual e a pasta Electron recebidos. Veja [AGENTE_ATUAL.md](AGENTE_ATUAL.md): os contratos físicos de caixa/sequências agora são reconhecidos; o exportador avulso permite obter o diagnóstico sem substituir o agente instalado. A classificação dos movimentos e as regras de gravação ainda dependem do ERP real.

A estrutura real já foi recebida e aplicada. Veja [ESTRUTURA_ERP_CONFIRMADA.md](ESTRUTURA_ERP_CONFIRMADA.md) para os nomes corrigidos, estoque por posição, pedidos no caixa e regras ainda pendentes.

## Comparação

| Área | Observado na referência | Entregue nesta revisão | Dependência ou diferença restante |
| --- | --- | --- | --- |
| Gestão comercial | Clientes, produtos, metas, filiais e indicadores | Clientes, Curva ABC e metas mensais por empresa/vendedor, além dos dashboards existentes | Metas de outros indicadores e dashboard específico de filiais não estão completos |
| Pessoas | Clientes e fornecedores, busca, situação, novo/edição | Consultas separadas, detalhes, busca, situação, paginação, colunas, CSV/Excel e formulários com solicitações ao agente | Fornecedores e campos adicionais precisam de correspondência no ERP; gravação exige adaptador de negócio |
| Produtos | Código de barras, referência, preços, estoque atual/reservado e classificações | Consulta, estoque por local/variação, códigos de barras, preços, classificação, colunas opcionais e solicitações de novo/edição | Estoque reservado e filtros hierárquicos completos ainda não implementados; estoque físico não é editado pelo formulário |
| Cadastros de produtos | Departamentos, grupos, subgrupos e marcas | Consultas e solicitações de novo/edição para os quatro tipos | Departamentos comerciais são separados do RH; tabelas diferentes exigem mapeamento local |
| Diversos | Metas e plano de contas para DRE | Metas comerciais e consulta/solicitação de plano de contas | A árvore e o cálculo contábil da DRE ainda dependem da hierarquia e das regras reais |
| Contas a receber/pagar | Original, baixado, saldo, vencimentos, formas de pagamento, documentos e centro de custo | Consultas por empresa, filtros, total filtrado, detalhes, CSV/Excel; saldos e baixas opcionais | Documento, espécie, centro de custo e plano de contas agora aparecem na consulta; saldos ainda exigem validar as rotinas oficiais |
| Fechamentos de caixa | Lista e oito abas: Financeiro, Vendas, Produtos vendidos, Recebimentos, Pagamentos, Sangrias, Suprimentos e Vendas canceladas | Lista, período/situação, detalhes com oito abas, conferência por forma de pagamento e diferença | Pedidos/itens e cancelamentos com data já usam o vínculo real; a classificação dos demais movimentos exige regras dos códigos. Resumos completos e impressão do fechamento ainda não reproduzem toda a referência |
| Fluxo de caixa | Saldo de contas e fluxo consolidado por rubrica | Previsão diária por vencimento, entradas/saídas e acumulado dos saldos abertos | Saldo bancário inicial, extrato realizado, transferências e rubricas não estão incorporados. Previsão não representa saldo disponível |
| Cheques e sangrias | Listas e filtros operacionais | Consultas, detalhes e exportações | Requer tabelas/vínculos reais sincronizados; operações de emissão/baixa não foram adicionadas |
| Fiscal e capital de giro | Documentos fiscais, totais e ativos/passivos | Comparação e levantamento das dependências | Ainda não implementados; não há dados suficientes no agente original |
| IA, Equipe e Performance | Recursos próprios do PIGO que devem continuar | Implementação existente preservada, com rotas e navegação mantidas | Validação local não substitui homologação com dados de produção |

## Fechamento e fluxo: integridade dos valores

Fechamentos são identificados pelo código do ERP e pela empresa. Movimentos de outras empresas não entram no detalhe. No contrato normalizado, a diferença por forma é `conferência - (entradas - saídas)`. No contrato físico real, totais e diferenças FCX/FCXI/FCXV são preservados como enviados pelo ERP. Uma conferência ausente permanece desconhecida, representada por “—”. As sete categorias são reconhecidas quando um adaptador normalizado as fornecer. A estrutura real fornece pedidos/itens por PEV_FECHAMENTO e movimentos brutos MOV; não se usam vendas do dia para inventar um fechamento.

A previsão de fluxo exige `REC_VALOR_ABERTO` e `PAG_VALOR_ABERTO`, além de vencimento e indicador de aberto. Um título original de R$ 500 com R$ 200 recebidos contribui R$ 300. O saldo nominal não substitui o saldo atual. Títulos cancelados são excluídos. O intervalo máximo é de 366 dias, e o acumulado começa em zero. Títulos vencidos antes do início não são automaticamente transportados para a primeira data.

O financeiro e os modelos de carteira preexistentes ainda possuem consultas legadas baseadas em valores nominais; esta revisão não os apresenta como equivalentes à nova previsão por saldo. A homologação deve comparar cada indicador com a regra do ERP.

## Caminho da gravação

1. Um administrador envia novo cadastro ou campos alterados. O backend verifica tenant, empresa, cadastro de origem e valores anteriores e grava uma solicitação durável no PostgreSQL.
2. O agente se autentica com seu API token e CNPJ. Somente cadastros anunciados pelo agente são reservados, um por vez, com prazo de cinco minutos. Reservas expiradas podem ser retomadas.
3. Na máquina do ERP, o agente executa um procedimento de negócio configurado localmente. O PIGO não envia SQL nem altera diretamente o espelho para fingir que a gravação ocorreu.
4. A gravação e seu recibo de idempotência são confirmados na mesma transação Firebird. Uma resposta perdida pode ser reenviada sem repetir o cadastro. Uma recusa desfaz alterações parciais e mantém um recibo da recusa.
5. O agente devolve o código e o resultado. O PIGO mostra `aguardando`, `processando`, `confirmado` ou `recusado`. A sincronização subsequente atualiza os dados consultados.

O protocolo, a fila, os formulários e o executor estão implementados. **O procedimento de negócio específico do ERP do cliente ainda não está implementado/configurado. Portanto, gravação no ERP de produção não está habilitada nem homologada.** As regras de IDs, vínculos, campos obrigatórios e validações não constam no ZIP. Não é correto inferi-las apenas pelos nomes de colunas.

O contrato e o procedimento necessário estão em [GRAVACAO_ERP.md](GRAVACAO_ERP.md). O código mantém a arquitetura de LicenseControl como autoridade da licença.

## Dados necessários para concluir a integração real

- Estrutura recebida: 468 tabelas e 9.022 campos. Não é necessário pedir novamente o mesmo diagnóstico; faltam regras de negócio, não nomes de tabelas.
- Definições ou documentação das rotinas que o ERP utiliza para inserir/editar pessoas, vínculo de cliente/fornecedor e produtos, inclusive geração de IDs e validações.
- Correspondência entre caixas, turnos, formas de pagamento, conferência, títulos, baixas, sangrias e suprimentos. Os contratos canônicos novos não provam que existam tabelas com esses nomes no ERP.

Além dos contratos físicos FCX/FCXI/FCXV/MOV do agente atual, o módulo `operational_sync.py` aceita correspondências locais explícitas e usa somente tabelas/campos presentes no schema. Campos ausentes continuam ausentes. O envio de pessoas passou a contemplar o cadastro inteiro em cada ciclo para que a edição de um cliente antigo também apareça no espelho; o custo dessa leitura deve ser medido na instalação real.

## Validação e limites

Build, testes automatizados e navegação desktop/móvel foram executados no ambiente de desenvolvimento com dados sintéticos. A API foi exercitada com dois tenants e duas empresas, baixas parciais, conferência ausente, filtros, exportações, fila e confirmação autenticada. O executor também foi exercitado num Firebird 5 descartável com procedimento exclusivamente de teste, verificando transação, reenvio e rollback. Esse procedimento de teste não é o adaptador do ERP do cliente.

Nenhum registro do painel de referência foi criado, editado, excluído ou importado. Não houve conexão ao Firebird nem ao LicenseControl de produção. O código está disponível no workspace e no pacote de revisão; não foi enviado ao GitHub ou publicado.
