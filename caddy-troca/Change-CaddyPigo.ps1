#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Preparar', 'Aplicar', 'Reverter')][string]$Action,
    [string]$OutputDirectory = 'C:\ProgramData\PIGO Changes\Pigo-4010'
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ne 'WIN-JG1E0O7FSBS') { throw 'Execute somente na VM WIN-JG1E0O7FSBS.' }
$pigoIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$pigoPrincipal = New-Object Security.Principal.WindowsPrincipal($pigoIdentity)
if (-not $pigoPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Execute como administrador.' }
$pigoPython = 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe'
$pigoConfig = 'C:\Projetos\caddy\Caddyfile.production'
$pigoCaddy = 'C:\Projetos\caddy\caddy.exe'
$pigoIndex = 'C:\Projetos\P.I.G.O\frontend\dist\index.html'
$pigoCheck = 'C:\ProgramData\PIGO Tasks\PigoDashboardTest\Test-PigoInstance.ps1'
$pigoExpectedHash = 'B5B3CC32BCC33999C647B75459F9FEFD795B0E924892D3D91D2F9773DD6F619C'
if ($Action -ne 'Reverter') {
    if ((Get-ScheduledTask -TaskPath '\' -TaskName 'PigoDashboardTest').State -ne 'Running') { throw 'A tarefa PIGO precisa estar em execucao antes da troca.' }
    & $pigoCheck -Port 4010
}
if ($Action -eq 'Preparar') {
    if (Test-Path -LiteralPath $OutputDirectory) { throw 'Pasta de preparacao ja existente; preserve-a. Informe outra -OutputDirectory se precisar de nova analise.' }
    $pigoParent = Split-Path -Parent $OutputDirectory
    if (-not (Test-Path -LiteralPath $pigoParent)) { $null = New-Item -ItemType Directory -Path $pigoParent -Force }
    $null = New-Item -ItemType Directory -Path $OutputDirectory
    & icacls.exe $OutputDirectory /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' ('*' + $pigoIdentity.User.Value + ':(OI)(CI)F') | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel proteger os backups; nenhuma configuracao sera copiada.' }
    & $pigoPython (Join-Path $PSScriptRoot 'caddy_cutover.py') prepare --output $OutputDirectory --config $pigoConfig --caddy $pigoCaddy --index $pigoIndex --expected-hash $pigoExpectedHash
} elseif ($Action -eq 'Aplicar') {
    & $pigoPython (Join-Path $PSScriptRoot 'caddy_cutover.py') apply --output $OutputDirectory
} else {
    & $pigoPython (Join-Path $PSScriptRoot 'caddy_cutover.py') rollback --output $OutputDirectory
}
if ($LASTEXITCODE -ne 0) { throw 'Operacao nao concluida. Envie somente o resumo acima; preserve os backups e mantenha os processos anteriores abertos.' }
