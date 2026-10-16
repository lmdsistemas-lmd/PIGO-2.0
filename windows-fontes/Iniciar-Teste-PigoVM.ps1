#Requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ne 'WIN-JG1E0O7FSBS') {
    throw 'Execute somente na VM WIN-JG1E0O7FSBS.'
}
if (Get-NetTCPConnection -State Listen -LocalPort 4010 -ErrorAction SilentlyContinue) {
    throw 'A porta 4010 esta ocupada. Use Ctrl+C somente no terminal do teste anterior e tente novamente.'
}
$pigoPython = 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pigoPython -PathType Leaf)) { throw 'Python do backend nao encontrado nesta VM.' }
& $pigoPython (Join-Path $PSScriptRoot 'run_pigo.py') --app-root 'C:\Projetos\P.I.G.O' --port 4010
if ($LASTEXITCODE -ne 0) { throw 'O teste nao iniciou ou terminou com erro. Envie as mensagens acima sem incluir credenciais.' }
