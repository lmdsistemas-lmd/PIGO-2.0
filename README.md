# PIGO: serviço de teste no Windows Server — v3

[**Baixar PIGO-servico-VM-v3.zip**](PIGO-servico-VM-v3.zip) — abra o arquivo e clique em **Download raw file**.

A v3 corrige o acesso direto às telas React no inicializador do teste/serviço. Na VM, `/api/health` e `/login` responderam200, mas `/dashboard/vendas` retornou404 no backend atual. O código recebido reproduz essa regra. O launcher da v3 publica o mesmo `frontend/dist/index.html` em uma lista explícita de URLs React. As chamadas da API continuam no backend atual, incluindo autenticação, licença, sincronização e ativação. Não substitui fontes da aplicação nem adiciona funcionalidades ao build.

## 1. Atualizar as ferramentas e reiniciar somente o teste

Extraia o ZIP em `C:\Temp`, atualizando os arquivos de ferramentas em `C:\Temp\PIGO-servico-VM`. Mantenha os processos de produção e Caddy abertos.

Pressione **Ctrl+C somente no terminal do teste temporário4010**. Quando o prompt voltar, execute:

```powershell
Set-Location 'C:\Temp\PIGO-servico-VM'
.\Iniciar-Teste-PigoVM.ps1
```

Esse comando recusa porta ocupada, carrega a configuração existente do backend e inicia o teste usando a mesma entrada que será usada no serviço. Mantenha o terminal aberto. Se faltar configuração no `.env`, informe o erro/nome da variável, nunca seu valor.

## 2. Preparar e instalar

Após **Application startup complete**, em OUTRO PowerShell **como administrador**:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Temp\PIGO-servico-VM'
    .\Preparar-PigoVM.ps1
    & 'C:\ProgramData\PIGO Services\PigoDashboardTest\Manage-Service.ps1' -Action Install
}
```

O verificador continua exigindo saúde JSON200, as cinco URLs HTML200 e API protegida401. Se falhar, não instala serviço. Envie o retorno. O serviço é registrado em modo manual/parado; nenhum processo existente é encerrado automaticamente.

## 3. Testar o serviço

Se aparecer **Serviço instalado em modo manual**, pressione Ctrl+C somente no terminal de `Iniciar-Teste-PigoVM.ps1`. Depois:

```powershell
& 'C:\ProgramData\PIGO Services\PigoDashboardTest\Manage-Service.ps1' -Action Start
```

Na VM, faça login em `http://127.0.0.1:4010`, confira os dados e atualize uma tela com F5. Envie o retorno. A troca do domínio e o início automático virão depois dessa validação. Não reinicie a VM nesta etapa.

## Escopo e validação

Esta branch entrega ferramentas de implantação; não contém o código integrado do dashboard. O launcher usa a aplicação atual de `C:\Projetos\P.I.G.O` e sua venv. Não altera fontes, banco, migrations ou configuração multi-domínio do Caddy. O backend mantém suas ações normais de startup. As permissões de LocalService são concedidas na instalação conforme o LEIA-ME.

11 testes do gerador/launcher e navegação passaram. A correção foi executada contra o backend do upload original, que antes retorna404/401 nas URLs React: depois, o verificador HTTP completo passou, mantendo a API protegida401. Os testes também conferem body/header/método da ativação, lifecycle, métodos de gravação e erros de API/assets. Ativação real, licença, conta LocalService, SCM e reboot dependem da validação na VM.

Os ZIPs v1/v2 permanecem preservados. Licença e proveniência do WinSW estão incluídas. Não envie .env, senhas ou tokens ao chat.

SHA256 v3:

```text
99b222e5ea039fbe9dda012d915fdab1ea7a6221cd9f4f84e8ab13286b4019de
```
