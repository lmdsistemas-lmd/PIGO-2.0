# PIGO: pacote de serviço para Windows Server

Esta branch entrega somente as ferramentas para executar o PIGO atual como serviço de teste na VM. Ela não contém o código integrado do dashboard.

## Baixar

Clique em `PIGO-servico-VM-v1.zip` e depois em **Download raw file**. Outra opção é **Code > Download ZIP**, extrair esse download e então extrair o ZIP do serviço em `C:\Temp`. A pasta final deve ser `C:\Temp\PIGO-servico-VM`.

O pacote usa a aplicação existente em `C:\Projetos\P.I.G.O`, sua venv e a porta local 4010. Não troca fontes da aplicação nem a configuração do Caddy. O teste manual 4010 deve permanecer aberto durante a preparação.

## Preparar e instalar

No PowerShell **como administrador**:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Temp\PIGO-servico-VM'
    .\Preparar-PigoVM.ps1
    & 'C:\ProgramData\PIGO Services\PigoDashboardTest\Manage-Service.ps1' -Action Install
}
```

Se houver erro, pare nessa etapa e envie o retorno. Se terminar corretamente, pressione Ctrl+C somente no terminal do teste temporário4010 e execute:

```powershell
& 'C:\ProgramData\PIGO Services\PigoDashboardTest\Manage-Service.ps1' -Action Start
```

Confira login, dados e atualização de tela com F5 no navegador da VM em `http://127.0.0.1:4010`. O serviço começa em modo manual; a troca do domínio será feita depois da validação. Mantenha Caddy e os processos de produção atuais abertos. Não reinicie o servidor nesta etapa.

A pasta inclui `LEIA-ME.txt`, licença e origem do WinSW e manifesto de hashes. O preparo verifica o binário WinSW antes de uso. Não envie `.env`, senhas ou tokens ao chat.

## Integridade

SHA256 do ZIP:

```text
62c334e34bf99e7f6c866517e210042b4748a5c6316ca00153abbe4f7021477e
```

Gerador, launcher e verificador HTTP foram validados na nuvem. Instalação nativa, permissões LocalService e reinicialização dependem da validação nesta VM.
