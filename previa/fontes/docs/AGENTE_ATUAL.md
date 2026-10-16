# Integração com o agente atual e o desktop

## Fontes recebidos e preservados

Esta revisão incorpora `remote-sync-agent.rar`, `remote-sync-desktop.rar` e `electron.rar` enviados pelo usuário. A base recebida identifica o agente como `2026.08.10-sales-keys-cash-sync` e o desktop como `0.2.12-rc.2`. Os fontes originais e a revisão anterior foram preservados fora do checkout para comparação. Ambientes virtuais e logs recebidos não foram importados para o código.

O agente atual já possui resolução de configuração, dois drivers Firebird, cofre compartilhado com DPAPI, instalação/ativação, proprietário único de execução, serviço Windows, comunicação autenticada por named pipe e diagnósticos de caixa. Esses recursos foram mantidos. A nova identificação do agente integrado é `2026.10.16-confirmed-erp-schema`; o protocolo IPC continua na versão 1 com campos adicionais de status.

## Estrutura real recebida

O diagnóstico foi recebido da instalação 0.2.12-rc.2 no computador IZABELLA. A correspondência e os limites confirmados estão em [ESTRUTURA_ERP_CONFIRMADA.md](ESTRUTURA_ERP_CONFIRMADA.md). O procedimento abaixo permanece como referência para novas exportações; não é necessário repetir a exportação já entregue.

## Como gerar o diagnóstico sem substituir o agente instalado

O arquivo [export_schema.py](../remote-sync-agent/export_schema.py) pode ser colocado sozinho na pasta `remote-sync-agent` que já existe na máquina do ERP. Ele foi testado também com os fontes originais recebidos, sem exigir a substituição de `agent.py`.

No terminal aberto nessa pasta, execute:

```powershell
.\venv\Scripts\python.exe .\export_schema.py
```

O arquivo gerado é `schema_diagnostics.json`. A saída informa o caminho completo; normalmente fica em:

```text
C:\ProgramData\PIGO Remote Sync\diagnostics\schema_diagnostics.json
```

Esse caminho respeita `PIGO_REMOTE_SYNC_DATA_DIR` quando configurado. O arquivo contém tabelas, campos, tipos, obrigatoriedade, chaves, nomes de geradores, triggers e parâmetros de procedimentos. Não contém linhas de clientes/produtos, senhas, tokens ou os corpos SQL dos procedimentos. O exportador usa a conexão que o agente já conhece, consulta somente os catálogos de estrutura e não ativa licença, inicia sincronização ou grava no ERP.

Na versão integrada, o mesmo recurso está na etapa **Teste → Exportar estrutura do ERP** do desktop e em `agent.py --export-schema`. O botão salva a configuração preenchida e executa a exportação, exibindo o caminho do JSON. Não é necessário instalar essa revisão completa para usar o exportador avulso acima.

## Gravação dentro do proprietário existente

As solicitações do PIGO são verificadas pelo worker existente, entre ciclos de sincronização, a cada 15 segundos. Não foi criado um segundo sincronizador em paralelo. Pausar o agente interrompe também novas consultas à fila; gravação e leitura não usam o Firebird simultaneamente nesse worker. Após uma confirmação, o proprietário agenda a leitura que atualiza o espelho. O estado `WRITING` e os horários da fila são repassados pelo IPC.

O executor usa `active_api_token()` e `remote_sync_headers()`, preservando o token do cofre e o cabeçalho de instalação do agente atual. Nenhum segredo passou a ser gravado em `config.json`. A configuração desktop aceita:

```json
{
  "writeback": {
    "enabled": false,
    "procedure": "",
    "resources": ["clientes", "fornecedores", "produtos"]
  }
}
```

Esse trecho complementa a configuração existente; não substitua o arquivo inteiro por ele. O modo legado reconhece as variáveis `WRITEBACK_*` em `.env.example`. A gravação permanece desativada até existir procedimento de negócio homologado. IDs, vínculos, campos obrigatórios e comparação dos valores anteriores continuam sendo responsabilidade desse adaptador, descrito em [GRAVACAO_ERP.md](GRAVACAO_ERP.md).

## Caixa e chaves físicas

O backend agora reconhece os contratos recebidos do agente:

- Itens de venda: empresa, pedido e `PEVI_SEQUENCIA`.
- Parcelas/formas da venda: empresa, pedido e `PEVF_SEQUENCIA`.
- Formas do fechamento: `FCXI_EMPRESA`, `FCXI_FECHAMENTO`, `FCXI_SEQUENCIA`.
- Composição de vendas no fechamento: campos `FCXV_*`.
- Movimentos: `MOV_EMPRESA`, `MOV_ID` e vínculo `MOV_FECHAMENTO`.

Linhas repetidas do mesmo produto e parcelas da mesma forma não são reduzidas a uma só. Totais, valor de caixa e diferenças nativos são exibidos como informados pelo ERP. Débitos e créditos mantêm esses nomes: a direção de entrada/saída não é presumida. Tipos e origens dos movimentos também permanecem como códigos até confirmar suas regras.

Os movimentos normalizados da primeira revisão passaram a usar `TB_PIGO_CAIXA_MOVIMENTO`, separadamente de `TB_FECHAMENTO_CAIXA_ITEM`, que no agente real representa formas/valores do fechamento. A leitura do formato anterior continua reconhecida quando presente. Pedidos e itens individuais agora usam o vínculo confirmado PEV_FECHAMENTO; cancelamentos com data registrada são exibidos separadamente. A classificação dos movimentos em recebimentos, pagamentos, sangrias e suprimentos ainda exige as regras dos códigos do ERP. A composição por forma recebida em `FCXV_*` não é apresentada como lista de pedidos individuais.

O envio de pessoas contempla o cadastro completo para que alterações em clientes antigos cheguem ao PIGO. O custo dessa leitura deve ser medido na base real.

## Migração do espelho PostgreSQL

Contratos completos de agentes antigos continuam reconhecidos. Quando a chave recebida mudar para a física, o backend só troca a chave do espelho se todos os registros armazenados já tiverem os valores necessários, incluindo empresa e local/variação quando aplicáveis, e a nova chave for única. A alteração de chave é transacional.

Se um espelho antigo não tiver sequências, a carga é bloqueada com `MIRROR_KEY_MIGRATION_REQUIRED` (HTTP 409). Nenhuma sequência é inventada e nenhum registro é apagado. Nesse caso, preserve o espelho e homologue uma carga/migração com as sequências reais do ERP antes de atualizar a instalação. Não misture versões com chaves diferentes no mesmo espelho. O exportador avulso não altera esse espelho.

## Ativação e homologação pendentes

O agente recebido chama `POST /api/agent/activate`. A implementação dessa rota não está no backend do ZIP inicial. O fluxo cliente de ativação foi preservado; não foi criado um substituto para as validações do LicenseControl. Precisamos confirmar a versão correspondente do backend e obter esse contrato/implementação para homologar a ativação automática com a base completa.

O diagnóstico da instalação real foi recebido. Ainda dependemos das rotinas/regras de cadastro para implementar o procedimento de gravação do cliente. Os testes com procedimentos sintéticos não resolvem essa dependência.

## Validação e limites da plataforma

Foram executados build do dashboard e do desktop, testes do backend, agente e Electron e testes de navegador. A fila/executor e a exportação foram exercitados em Firebird 5 descartável. Contratos físicos, chave composta, bloqueio de migração incompleta e isolamento foram testados em PostgreSQL descartável com dados sintéticos. O exportador avulso foi exercitado com o agente original recebido.

A validação do renderer desktop usa uma ponte nativa sintética no navegador. Testes reais de named pipes, DPAPI e runtimes Windows não foram executados na nuvem Linux; os testes específicos dessa plataforma permanecem identificados como ignorados. Não foi gerado instalador Windows. As pastas de runtimes/recursos binários da instalação existente devem ser preservadas para empacotar e homologar no Windows.

Nenhuma conexão ao ERP ou LicenseControl de produção foi feita nesta revisão. Nenhum segredo recebido foi copiado para o pacote ou a configuração da nuvem.
