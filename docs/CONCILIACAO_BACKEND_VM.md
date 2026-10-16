# Conciliação com o backend em execução

Entrada: PIGO-backend-VM-20261016-203041-221132.zip, 129 arquivos coletados da VM
WIN-JG1E0O7FSBS. A referência da main do GitHub permanece para comparação, mas
não foi usada para substituir as diferenças encontradas na instalação real.

## Resultado

A ativação do agente, instalação/revogação/tokens, limite de tentativas, contrato
LicenseControl, configurações e logs da VM foram integrados. A administração de
instalações agora respeita o tenant autenticado e as permissões do PIGO, impedindo
que um administrador altere a instalação de outra empresa.

A classe e a API cash_register da VM foram preservadas. O adaptador novo do modal
fica em cash_closing_details_service.py. Ambos consultam os registros físicos do
mesmo fechamento; os testes conferem valores, isolamento e exportações Excel/PDF.
As chaves e aliases de empresa mantêm compatibilidade com erp_company_id, campos
FCX/FCXI/FCXV/MOV e a validação de sequências obrigatórias.

Vendas mantém os filtros de status e novos clientes da VM. O resumo e o
histórico consideram o faturamento até o final do último dia. As agregações separadas de pedidos/itens e a
propagação do contexto de tenant foram preservadas. A cache mantém a invalidação
por tenant após sincronização confirmada e impede que uma consulta anterior
reponha dados invalidados.

O catálogo/coordenadas e as correções manuais da VM permanecem disponíveis.
O adaptador React reconhece seus campos e coordenadas com origem confirmada,
mantendo o catálogo municipal local como alternativa. As duas folhas de estilo
compiladas são byte a byte iguais às aprovadas; não houve alteração de layout.

## Migrações

Preservadas 006_agent_installations, 009_municipality_geocodes,
010_cash_register_sync e 011_cash_register_closing_optional_fields, além das
migrações anteriores. As adições foram numeradas 012_sales_goals,
013_erp_commands e 014_pigo_access. Não há dois arquivos com o mesmo prefixo
numérico nesta entrega. A reaplicação foi testada mantendo fechamentos existentes.

## Verificação

- 81 testes unitários/regressão passaram;
- 7 testes de integração com o contrato da VM passaram;
- 7 testes de integração do esquema físico do ERP passaram;
- os 7 testes da VM também passaram importando o código de dentro do pacote;
- 16 testes frontend e 11 grupos de navegação/HTTP da prévia passaram, com 33 telas;
-inspeção de ambiente verificada em conexão PostgreSQL somente de leitura,
  sem exibir credenciais nem importar a aplicação instalada.

Os testes de ativação simulam o LicenseControl externo. PostgreSQL e dados usados
na nuvem são descartáveis/sintéticos; nenhuma credencial ou banco real foi usado.
Há 14 integrações ignoradas na descoberta unitária padrão, executadas separadamente
nos conjuntos acima. A validação Windows e a instalação real ainda dependem da VM.

## Distribuição

O ZIP de execução inclui backend, migrações, somente o executor normal de
migração e o painel compilado, sem .env, bancos, logs, venv, snapshots, fontes
React ou instalador do agente. Scripts de seed/reconstrução ficam apenas nos
fontes; não são executados no pacote. A inspeção inicial não altera banco,
processos ou Caddy. A instalação anterior e a prévia aprovada permanecem como estão.

A conclusão desta conciliação resolve a ausência do código atual da VM. A próxima
etapa é verificar o ambiente, preparar backup/restauração em homologação e testar
a instância paralela, antes da troca do domínio PIGO ou de sua tarefa automática.
