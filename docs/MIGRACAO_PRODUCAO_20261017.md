# Migração definitiva do PIGO aprovado

Autorizada pelo usuário após testar e aprovar os ajustes na porta 4023.
Ambiente confirmado: VM WIN-JG1E0O7FSBS, PostgreSQL 18.4 local na porta 5432,
banco `pigo-dashboard`. A consulta atual ao Caddy encontrou um grupo próprio
do PIGO, sem compartilhar host, destinos `127.0.0.1:4000` e `127.0.0.1:5176`,
arquivo `C:\Projetos\caddy\Caddyfile.production` existente e porta 4024 livre.

## Executar na VM

Baixar `deploy/manual/migrar_producao.py` no GitHub usando **Download raw file**,
com o Defender ativo, e salvar em:

`C:\Projetos\PIGO-VM-CONCILIADO-20261016\migrar_producao.py`

Abrir PowerShell **como Administrador** na VM correta e executar:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\migrar_producao.py' --cutover
```

Não encerrar o Caddy nem a instância atual durante a preparação. O script faz:

1. Confere os hashes da entrega aprovada e dos helpers. Exige pasta nova
   `C:\Projetos\PIGO-Producao-20261017` e porta 4024 livre; nunca substitui uma
   instalação existente ou encerra processos para liberar portas.
2. Compara o Caddyfile adaptado com a configuração ativa. Exige exatamente
   um grupo dedicado ao host PIGO e proxies para as portas já conhecidas.
   Prepara e valida candidato alterando somente os destinos dentro desse bloco.
   A configuração completa adaptada deve diferir apenas nesses destinos.
3. Cria um backup PostgreSQL custom **novo**, com snapshot somente de leitura,
   índice conferido e SHA256, na pasta privada `C:\ProgramData\PIGO Production`.
   Usa pg_dump/pg_restore 18 já instalados. Não cria nem promove outra cópia do banco.
4. Copia apenas os arquivos do manifesto para a pasta de produção e cria
   `backend\.venv-producao`, com dependências nas versões fixadas e `pip check`.
   O venv e o `.env` atuais ficam preservados. A configuração privada aponta
   para o **banco real atual**, mantendo JWT, chaves de integração e os demais
   parâmetros existentes; não usa as chaves da homologação.
5. Aplica somente `012`, `013` e `014` em uma transação PostgreSQL com limites
   de espera. Confere as contagens no mesmo snapshot da transação para não
   confundir atualizações concorrentes do agente com alterações da migração.
   Não executa seed, rebuild, exclusão de tabelas ou substituição de dados.
6. Registra e inicia `PigoDashboardProduction`, como SYSTEM, com início no boot
   após 30 segundos, sem limite de execução e com três tentativas de reinício.
   A API fica exclusivamente em `127.0.0.1:4024`, sem VS Code ou terminal próprio.
   Valida API e HTML das telas antes de trocar o domínio.
7. Reconfere se ninguém alterou configuração/arquivos durante o preparo.
   Substitui o Caddyfile de forma atômica, preservando sua ACL, e recarrega o
   Caddy sem parar o processo. Confere a configuração ativa e, via HTTPS com
   validação TLS, o health, o novo index e os assets compilados do domínio.

Se a verificação da troca falhar, retorna o arquivo e a rota anteriores, desde
que não haja uma alteração concorrente de outro administrador. Se houver,
interrompe para revisão, evitando sobrescrever configurações de outros domínios.
O banco não é restaurado automaticamente: as tabelas adicionais permanecem
compatíveis com a versão anterior, preservando os novos dados enviados pelo agente.

Resultado esperado: `MIGRACAO_CONCLUIDA`. Compartilhar **somente o JSON**.
Não enviar backup, `.env`, configuração privada do Caddy ou logs completos.

## Inicialização automática do Caddy compartilhado

Depois de confirmar `MIGRACAO_CONCLUIDA`, executar:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-Producao-20261017\migrar_producao.py' --action enable-caddy-autostart
```

Registra `LmdSharedCaddy` para o próximo boot, com a mesma conta do processo
Caddy atual, logon S4U, configuração e diretório atuais. Confere a identidade
do proprietário do processo e não substitui tarefa já existente. Não pede nem
armazena senha de Windows. A mesma conta preserva o contexto de acesso aos
certificados existentes; a inicialização real nessa conta ainda precisa ser
validada após um reinício programado.

**Não inicia nem interrompe o Caddy agora.** Manter o terminal do Caddy atual
aberto até o reinício programado da VM. Não é necessário reiniciar para trocar
o PIGO; um reboot também afeta os demais sistemas e não é executado pelo helper.
O terminal da homologação 4023 pode ser encerrado depois de conferir a produção.
Não apagar `P.I.G.O` nem parar processos Python/Node em lote. A tarefa antiga
4010 pode ser desativada após comprovar que nenhum outro domínio a utiliza.

## Conferir e retornar

Após a migração, acessar `https://pigo.lmdsistemasdev.qzz.io/`, atualizar com
Ctrl+F5 e conferir login, dados, Equipe, Performance, relatórios, Acesso e caixa.
O agente mantém o mesmo endereço e credenciais. Confirmar um novo envio normal
do agente pelo horário de sincronização; não reativar nem reinstalar o agente.

```powershell
# Somente estado e consultas de saúde:
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-Producao-20261017\migrar_producao.py' --action status

# Se for necessário retornar SOMENTE a rota:
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-Producao-20261017\migrar_producao.py' --action rollback
```

O retorno também exige configuração intacta para não desfazer alterações de
outros domínios. Não restaura backup por cima do banco em uso, não apaga as
tabelas novas e não encerra tarefas de terceiros.

O executável da API não é um instalador binário novo: usa Python e os fontes
já aprovados, com tarefas nativas do Windows. As gravações **no ERP pelo agente**
continuam bloqueadas, aguardando homologação dos procedimentos e regras reais.
Sincronização de entrada, ativação e consultas do PIGO permanecem habilitadas.

## Evidência e limites

Testes usam somente PostgreSQL descartável e um Caddy real isolado. Exercitam
backup, migrações, venv/pip, login, sincronização autenticada, bloqueio de writeback,
troca de proxies, manutenção de outro host, retorno manual e automático, recusa
de alterações concorrentes e grupos de hosts compartilhados. O HTTPS público
é simulado no teste com tráfego HTTP para o Caddy isolado; TLS real é conferido
somente pela execução na VM, com verificação padrão habilitada.

Scripts das tarefas foram analisados pelo parser PowerShell, mas o registro
no Windows, as contas SYSTEM/S4U e o boot não podem ser executados na nuvem Linux.
A varredura complementar não substitui o Defender. Produção só será considerada
migrada após o JSON e a conferência real retornados pela VM.
