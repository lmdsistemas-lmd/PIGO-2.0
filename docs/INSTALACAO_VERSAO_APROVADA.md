# PIGO conciliado com o backend da VM

> Atualização da interface em 17/10/2026: [aplicar o ajuste compacto](AJUSTES_INTERFACE_20261017.md).
> Na homologação já instalada, basta aplicar o patch e usar `--action start`.
> Em instalação nova, aplicar o patch ao ZIP base antes de usar o instalador atual.

Base recebida: ZIP PIGO-backend-VM-20261016-203041-221132.zip, 129 arquivos,
coletado em WIN-JG1E0O7FSBS. Os fontes do backend em execução foram comparados
com a main do GitHub e com as alterações do painel aprovado. A ativação do
agente, a API/campos de caixa, as coordenadas e a sincronização atuais foram
integrados, preservando a configuração por backend/.env.

## O que está nesta entrega

Backend real e painel compilado com o layout aprovado. O adaptador do mapa
reconhece também as coordenadas confirmadas e correções manuais da VM; as folhas
de estilo continuam idênticas às aprovadas. O pacote não inclui dados de clientes,
credenciais, banco, ambiente virtual, fontes React ou instalador do agente.

A API legada /api/cash-register foi preservada. O detalhamento do fechamento novo
usa um adaptador separado, evitando substituir a classe do caixa existente.
A ativação continua usando o LicenseControl atual; revogação e regeneração de
token são limitadas ao tenant autenticado e à permissão administrativa.
Instalação revogada continua bloqueada na sincronização. Campos/chaves físicos
do caixa reconhecem erp_company_id e o campo de empresa correspondente.

As migrações da VM 006 e 009–011 foram preservadas. As adições são:

- 012_sales_goals.sql: metas;
- 013_erp_commands.sql: fila de comandos;
- 014_pigo_access.sql: usuários e perfis próprios PIGO.

Nenhuma rotina de reconstrução de espelho, seed ou ativação é executada na
inicialização. Essas rotinas de manutenção permanecem nos fontes para revisão,
fora do pacote de execução. Gravações no ERP seguem dependendo da homologação
dos procedimentos e regras reais; não habilitar writeback nesta etapa.

## Primeiro passo na VM: conferir o ambiente

Após verificar o ZIP com o Defender ativo, extrair a pasta
PIGO-VM-CONCILIADO-20261016 em C:\Projetos, ao lado de P.I.G.O.
A pasta atual e a tarefa 4010 permanecem como estão. Executar:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\inspecionar_vm.py' --current-root 'C:\Projetos\P.I.G.O'
```

O comando confere os fontes da VM com os 129 hashes recebidos e inspeciona os
pré-requisitos. Lê a configuração existente para uma conexão PostgreSQL com
transação somente de leitura, consultando apenas versão e nomes de tabelas.
Não exibe senhas, tokens ou a URL de conexão. Também localiza pg_dump/pg_restore
instalados e verifica a disponibilidade local da porta 4023. Não inicia o painel,
não aplica migrações, não copia banco e não altera o Caddy. Compartilhar somente
a saída JSON, sem anexar o .env.

## Etapa seguinte: homologação e instalação

### Backup e restauração em banco separado

A inspeção retornada em 17/10/2026 confirmou os 129 arquivos, PostgreSQL local
18.4 na porta 5432, banco `pigo-dashboard`, ferramentas 18.4 instaladas e porta
4023 livre. A versão em produção permanece intacta.

Baixar o arquivo de texto Python [preparar_homologacao.py](../deploy/manual/preparar_homologacao.py)
pelo botão **Download raw file**, mantendo o Defender ativo, e salvar em
`C:\Projetos\PIGO-VM-CONCILIADO-20261016\preparar_homologacao.py`.
Não é necessário baixar outro ZIP. Executar **na VM WIN-JG1E0O7FSBS**:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\preparar_homologacao.py' --current-root 'C:\Projetos\P.I.G.O'
```

O comando lê o `.env` atual sem exibir valores e usa as ferramentas PostgreSQL
18 já instaladas. Cria uma pasta privada sob `C:\ProgramData\PIGO Backups`, com
acesso restrito à conta executora, SYSTEM e administradores, antes de gravar dados.
Gera backup custom com snapshot consistente, verifica o índice e calcula SHA256.
Restaura o backup em um banco novo `pigo_homolog_DATA_IDENTIFICADOR`, conferindo
locale, lista de tabelas públicas e contagens de empresa, usuários, instalações,
coordenadas e caixa na mesma fotografia usada pelo backup.

Não substitui bancos existentes nem executa DROP, migrações, inicialização do
PIGO, alteração de tarefa ou Caddy. As únicas gravações PostgreSQL desta etapa
são a criação e a restauração do novo banco de homologação. O banco de origem
é acessado em transação somente de leitura e pelo pg_dump. Nenhum programa do
backend em produção é importado pelo helper. A cópia deixa de acompanhar o
agente após o instante do backup.

Se a conta não puder criar bancos ou alguma etapa falhar, interrompe e preserva
o backup concluído e eventual banco novo para diagnóstico, sem tentar apagar
ou corrigir dados automaticamente. A saída final deve informar
`BACKUP_E_RESTAURACAO_CONFERIDOS`. Compartilhar somente o JSON final: o backup,
os logs privados e o `.env` podem conter dados de clientes e não devem ser
anexados ao chat ou publicados no GitHub.

A rotina foi exercitada com PostgreSQL descartável na nuvem, inclusive chegada
de dados após a exportação do snapshot e falhas de backup/restauração. Os
argumentos da ACL Windows foram verificados com simulação, mas a aplicação
real da ACL e a execução no Windows/PostgreSQL 18.4 dependem desta etapa na VM.

### Instalação após confirmar o resultado

O backup/restauração da VM foi confirmado em 17/10/2026: 58 tabelas públicas,
460 fechamentos, 1.666 itens, 11 usuários, 2 instalações e 5.571 coordenadas.
O banco de homologação informado é `pigo_homolog_20261017_316ece6fe326`.

Baixar [instalar_homologacao.py](../deploy/manual/instalar_homologacao.py) pelo
botão **Download raw file**, mantendo a proteção ativa, e salvar ao lado de
`preparar_homologacao.py`, na pasta `C:\Projetos\PIGO-VM-CONCILIADO-20261016`.
Executar na VM:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\instalar_homologacao.py' --current-root 'C:\Projetos\P.I.G.O' --backup-result 'C:\ProgramData\PIGO Backups\homologacao_20261017T111012Z_b843c854\resultado.json' --start
```

O instalador confere o manifesto/hashes da entrega e do helper de backup,
recalcula o SHA256 do backup e exige o resultado de restauração conferida.
Cria `backend\.venv-homologacao`, instala as dependências com as versões já
fixadas em `requirements.txt` e executa `pip check`. O Python da instalação
atual só inicia o instalador; seus pacotes não são alterados.

Aplica somente `012`, `013` e `014` no banco separado, em transação com limites
de espera, e confere que as contagens restauradas foram preservadas. A configuração
fica na pasta privada de backup, com JWT e chaves de integração exclusivos para
esta homologação; o `.env` de produção permanece intacto. `homologacao.json`
na pasta nova contém apenas os caminhos e hashes necessários ao inicializador.
Não reutilizar essa configuração de homologação na implantação de produção.

Antes de liberar o início, testa a API em processo temporário próprio, o HTML
das telas, a exigência de autenticação e o bloqueio das integrações. O processo
temporário é encerrado pelo próprio instalador. Com `--start`, inicia então a
instância em primeiro plano exclusivamente em `127.0.0.1:4023`, usando
`homologacao_entry:app`, sem reload e sem alterar tarefas ou Caddy.

A entrada de homologação recusa banco fora do padrão de cópia, desabilita
Firebird direto e bloqueia sincronização, ativação/gestão de instalações,
atualizações internas do LicenseControl e envio de cadastros ao ERP. Consultas
e alterações próprias do PIGO usam somente a cópia. Não apontar o agente para
essa instância. A licença continua sendo validada pelos dados restaurados,
sem estender validade ou simular liberação.

Após aparecer `HOMOLOGACAO_INSTALADA_E_CONFERIDA` e a mensagem do Uvicorn,
manter o terminal aberto e acessar `http://127.0.0.1:4023/login` no navegador
**da própria VM**. Usar o usuário habitual, sem credenciais de demonstração.
Conferir consultas, Equipe, Performance, relatórios, Acesso e caixa. Se alguma
consulta falhar, compartilhar o status/erro da tela, sem tokens, `.env` ou logs
privados completos.

Para iniciar novamente depois de encerrar com Ctrl+C:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\instalar_homologacao.py' --action start
```

Não repetir `prepare` numa configuração já pronta: o script preserva os
arquivos existentes e orienta a usar `--action start`. Se houver falha antes
de concluir, o backup e a produção continuam preservados; revisar o JSON e
os diagnósticos privados antes de tentar novamente.

### Troca de produção após homologar

A homologação foi aprovada. Seguir [Migração definitiva](MIGRACAO_PRODUCAO_20261017.md),
que usa o banco real, backup novo, tarefa Windows e troca restrita ao domínio PIGO.

A conexão ao LicenseControl externo não foi exercitada com credenciais reais nos
testes da nuvem; foi simulada. Preservar o agente instalado e seu destino atual.
Na futura configuração de produção, preservar o JWT e os parâmetros de integração
atuais sem publicar valores; as chaves exclusivas de homologação não serão usadas.

Depois da homologação, planejar a aplicação das novas migrações e a troca do
backend de produção. Atualizar apenas a rota do domínio PIGO no Caddy, mantendo
os outros domínios, o backup e a configuração anterior disponíveis para retorno.
Configurar a tarefa automática da nova instância após validar o processo.
Nenhuma dessas alterações é efetuada por baixar ou inspecionar o pacote.

## Validação e limites

Testes em PostgreSQL descartável verificaram a ativação simulada, bloqueio de
instalação revogada, isolamento entre tenants, caixa legado e detalhamento novo,
exportações XLSX/PDF, chaves físicas e preservação dos dados ao reaplicar as
migrações, vendas/status/datas e catálogo municipal. O frontend passou pelos
testes funcionais e de navegação com dados sintéticos. Windows, banco real,
Caddy e o agente instalado ainda precisam da homologação na VM.

O alerta anterior do Defender em fontes de desenvolvimento React permanece sem
adjudicação. A distribuição convencional separa fontes e execução; isso não
confirma falso positivo nem liberação pelo Defender. Manter a proteção ativa e
suspender o uso se houver nova detecção. A varredura complementar não substitui
a proteção do Windows.
