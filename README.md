# PIGO em segundo plano com o Agendador de Tarefas do Windows

[**Baixar pacote somente com scripts**](PIGO-Windows-fontes-v1.zip): abra o arquivo e clique em **Download raw file**. [Revisar os arquivos individualmente](windows-fontes).

Os ZIPs anteriores com executável foram retirados da versão atual desta branch após o bloqueio informado no download. Os manifestos antigos permanecem somente como registro de integridade; não são uma recomendação de restaurar o arquivo bloqueado.

Esta entrega contém somente scripts de texto. Usa o Python já instalado na VM
e o Agendador de Tarefas nativo, sem WinSW ou outro executável no pacote.
O alerta do download anterior não foi identificado; não foi confirmado como
falso positivo. Não restaure o pacote bloqueado nem desative o antivírus.
Se esta entrega também for bloqueada, interrompa o download e informe o alerta.

O resultado será uma **tarefa do Windows**, não um serviço do SCM. Ela pode
iniciar o PIGO sem VS Code ou login interativo. A instalação inicial não cria
um disparo automático; primeiro é necessário validar a execução manual da
tarefa. O início ao ligar a VM será habilitado numa etapa posterior.

## 1. Testar a correção das telas

Extraia `PIGO-Windows-fontes-v1.zip` em `C:\Temp`. A pasta final deve ser
`C:\Temp\PIGO-Windows-fontes`. Os scripts também estão disponíveis para leitura
individual na pasta `windows-fontes` do GitHub. Nenhum fonte vai para a pasta
ativa da aplicação.

Pressione **Ctrl+C somente no terminal do teste temporário da porta4010**.
Mantenha os terminais da produção, Vite e Caddy abertos. No terminal do teste:

```powershell
Set-Location 'C:\Temp\PIGO-Windows-fontes'
.\Iniciar-Teste-PigoVM.ps1
```

O launcher lê `C:\Projetos\P.I.G.O\backend\.env` localmente, sem copiar seus
segredos para os perfis. Se faltar uma configuração, informe só o nome/erro.
Nunca envie .env, senhas ou tokens pelo chat.

Após **Application startup complete**, em OUTRO PowerShell da mesma VM:

```powershell
Set-Location 'C:\Temp\PIGO-Windows-fontes'
.\Test-PigoInstance.ps1 -Port 4010
```

O esperado é saúde200, as telas200 e API protegida401. A correção serve somente
o index compilado nas URLs React. API, autenticação, licença, ativação e sync
continuam no backend existente. Isso não adiciona funcionalidades ao build.

## 2. Preparar e registrar a tarefa

Se o teste passou, no PowerShell **como administrador**, mantendo o teste4010
aberto:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Temp\PIGO-Windows-fontes'
    .\Preparar-Tarefa-PigoVM.ps1
    & 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action Install
}
```

O preparo exige pasta nova e recusa tarefa/serviço existente com o mesmo nome.
O registro é como LocalService, sem pedir senha, sem iniciar a tarefa e sem
disparo automático. Concede leitura/execução nas ferramentas, aplicação e
runtime Python, e gravação na pasta de logs. Não altera Caddy, fontes do app,
configurações ou banco. A aplicação mantém suas próprias ações de startup.

## 3. Iniciar e conferir

Se aparecer **Tarefa registrada sem disparo automático**, pressione Ctrl+C
somente no teste temporário4010. No PowerShell administrador:

```powershell
& 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action Start
```

Confira login, dados e atualização com F5 em `http://127.0.0.1:4010` no navegador
da VM. Envie o resultado. A troca do domínio e o disparo ao iniciar o Windows
ficam para depois dessa validação. Não reinicie a VM nesta etapa.

O gerenciador recusa porta ocupada e não encerra processos antigos. Se a nova
tarefa não responder corretamente, para somente essa tarefa. Logs da aplicação
e do Uvicorn ficam em `C:\ProgramData\PIGO Tasks\PigoDashboardTest\logs\pigo.log`,
com rotação de10MB/5 backups. Não envie logs completos sem revisar seu conteúdo.

## Etapas posteriores e retorno

Após validar a tarefa e a configuração definitiva, `Manage-Task.ps1 -Action
EnableAutostart` adiciona disparo na inicialização da VM, com30s de atraso.
A tarefa usa uma única instância, sem limite de duração e até3 reinícios após
falha com intervalo de1min. O Caddy com seus outros domínios continua na
configuração atual e requer migração própria; não é alterado por este pacote.

Para remover somente esta tarefa, se necessário:

```powershell
& 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action Stop
& 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action Uninstall
```

Os arquivos, logs, dados e permissões adicionadas são preservados.

## Validação e limites

Gerador do perfil e launcher foram executados na nuvem contra o backend do
upload original, reproduzindo a correção do404 e mantendo a API protegida401.
Logging em arquivo, preservação da configuração, argumentos com espaços e
recusa de sobrescrita foram verificados. PowerShell7.4.6Linux validou sintaxe
e executou o verificador HTTP. Registro de tarefa, ACLs, LocalService e reboot
precisam de validação no Windows Server. Não houve varredura antivírus desta
entrega nesta nuvem; o manifesto de hashes identifica os arquivos, sem atestar
ausência de malware. A proteção local deve permanecer ativa.

SHA256 do pacote atual:

```text
f572cf98580b178dccd07b772fd34963238f6d19ed73c566af1c0fd8adceb832
```

## Após validar a tarefa em segundo plano

O usuário informou que o teste com a tarefa aparentemente está funcionando. Confirme a tarefa e habilite o disparo ao iniciar o Windows no PowerShell administrador:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    & 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action Status
    & 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Manage-Task.ps1' -Action EnableAutostart
}
```

O comando exige tarefa Running e repete a verificação HTTP antes de alterar somente o seu disparo. Isso ainda não migra o Caddy, que permanece em terminal. Mantenha Caddy e processos de produção abertos e não reinicie a VM nesta etapa.

Baixe [Conferir-Caddy-Pigo.ps1](Conferir-Caddy-Pigo.ps1) pelo botão Download raw file e salve em `C:\Temp\PIGO-Windows-fontes`. Depois:

```powershell
& 'C:\Temp\PIGO-Windows-fontes\Conferir-Caddy-Pigo.ps1'
```

Esse diagnóstico é somente leitura: consulta a configuração HTTP atual pela API local2019 do Caddy e imprime apenas os destinos loopback do domínio PIGO, se encontrados. Não imprime cabeçalhos, tokens ou configuração completa e não altera arquivos/processos/rotas. Também identifica grupos que compartilham PIGO e outros hosts e imprime somente o hash do Caddyfile já localizado. Ausência de API2019 ou de correspondência exata não prova que o site está fora do ar; exige diagnóstico da configuração efetiva antes de preparar qualquer troca. Envie o resumo para preparar a mudança somente do PIGO.
