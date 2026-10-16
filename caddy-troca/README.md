# Encaminhar somente o PIGO para a tarefa4010

O diagnóstico da VM confirmou tarefa PigoDashboardTest Running, testes HTTP
completos passando e disparo ao iniciar o Windows com30s de atraso. O Caddy
continua no terminal e tem um grupo exclusivo do domínio PIGO, com destinos
127.0.0.1:4000 e127.0.0.1:5176. O SHA256 do arquivo informado é
B5B3CC32BCC33999C647B75459F9FEFD795B0E924892D3D91D2F9773DD6F619C.

Este pacote contém somente dois scripts de texto e esta documentação. Usa o
Python e o Caddy já instalados na VM. Não instala executáveis, não altera o
antivírus e não encerra processos. A migração do Caddy para execução automática
continua separada desta troca de encaminhamento.

## Executar na VM

Extraia o ZIP em C:\Temp, formando C:\Temp\PIGO-Caddy-troca. No PowerShell
**como administrador**:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Temp\PIGO-Caddy-troca'
    .\Change-CaddyPigo.ps1 -Action Preparar
    .\Change-CaddyPigo.ps1 -Action Aplicar
}
```

Se alguma etapa falhar, o bloco para. Envie somente o resumo impresso. Não
envie os arquivos de configuração, backups ou logs completos, pois podem
conter credenciais dos sites. Mantenha Caddy, VSCode e processos antigos
abertos; não reinicie a VM nesta etapa.

Ao concluir, abra https://pigo.lmdsistemasdev.qzz.io/, faça login, confira os
dados e atualize a tela com F5. Confira também seus outros domínios. Envie
o resultado para seguir com a execução automática do Caddy e a identificação
dos processos antigos que poderão ser encerrados.

## O que o preparo confere

- A tarefa PIGO precisa estar Running e passar novamente nos testes locais.
- O hash do Caddyfile precisa ser o mesmo informado no diagnóstico.
- O Caddyfile adaptado pelo executável atual precisa equivaler à configuração
  efetivamente carregada pela API local2019. Se houver diferenças, não aplica.
- Somente dois destinos literais no bloco exclusivo do PIGO são substituídos
  por127.0.0.1:4010. Compartilhamento de host, imports que guardem os destinos,
  heredocs ou estrutura não reconhecida interrompem a automação para revisão.
- A candidata adaptada precisa equivaler exatamente à configuração ativa
  alterada somente nesses dois valores. Todos os demais campos são comparados.

A preparação deixa backups e candidata em pasta com acesso restrito a
administradores, SYSTEM e ao usuário que a executou:
C:\ProgramData\PIGO Changes\Pigo-4010. Não altera o arquivo ativo nem recarrega
o Caddy até a ação Aplicar. Não apaga nem sobrescreve preparação existente.

## Aplicação, verificação e retorno

Aplicar confere novamente os hashes e a configuração carregada. A escrita do
Caddyfile usa ReplaceFileW do Windows, preservando as permissões existentes.
A recarga usa POST/config/ com If-Match/ETag, recusando alterações concorrentes.
O próprio Caddy valida a configuração e recarrega sem encerrar seu processo.
O Caddyfile original passa a guardar os mesmos destinos persistentes; não é
uma alteração somente em memória.

São verificados HTTPS público, os arquivos do build nas telas de login/vendas e as respostas JS/CSS,
saúde da API e retorno401 na consulta sem token. A validação TLS permanece
ativa. Se a verificação falhar, o script tenta restaurar o arquivo e a
configuração anterior. Se outra alteração ocorrer fora desta operação, o
retorno automático não sobrescreve essa alteração e informa retorno incompleto.
Os processos anteriores devem permanecer disponíveis durante essa etapa.

Para restaurar manualmente a preparação, se necessário:

```powershell
Set-Location 'C:\Temp\PIGO-Caddy-troca'
.\Change-CaddyPigo.ps1 -Action Reverter
```

O retorno exige que os arquivos/estado ainda correspondam aos valores desta
operação. Se a pasta padrão já existir após falha de preparo, preserve-a e
informe o erro antes de criar outra preparação. A opção -OutputDirectory
permite uma nova pasta, mas deve ser usada igualmente nas três ações.

## Validação realizada

Oito testes cobriram alteração somente dos destinos PIGO, preservação de outros
hosts, comentários/CRLF/BOM, recusa de estruturas não reconhecidas, integridade
do plano, concorrência, idempotência e retorno por falha. Com Caddy2.10.2Linux
oficial, cinco grupos funcionais validaram preparo com imports relativos,
recarga real pela API, ETag obsoleta recusada com412, domínio independente
continuando acessível e retorno explícito/automático de arquivo e configuração.
O binário de teste foi conferido contra SHA512 oficial e não está neste ZIP.
PowerShell7.4.6Linux analisou a sintaxe. ReplaceFileW/ACLs no Windows e HTTPS
real do domínio precisam da validação nesta VM. Não houve varredura antivírus
na nuvem; mantenha a proteção ativa e não libere um arquivo que seja bloqueado.
