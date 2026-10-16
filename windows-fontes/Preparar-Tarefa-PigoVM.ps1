#Requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ne 'WIN-JG1E0O7FSBS') { throw 'Execute somente na VM WIN-JG1E0O7FSBS.' }
$pigoOutput = 'C:\ProgramData\PIGO Tasks\PigoDashboardTest'
if (Test-Path -LiteralPath $pigoOutput) { throw 'A pasta de tarefa ja existe; preserve-a e informe o retorno.' }
if ((Get-ScheduledTask -TaskPath '\' -TaskName 'PigoDashboardTest' -ErrorAction SilentlyContinue) -or (Get-Service -Name 'PigoDashboardTest' -ErrorAction SilentlyContinue)) { throw 'Ja existe uma tarefa/servico de teste com esse nome; preserve e informe o retorno.' }
& (Join-Path $PSScriptRoot 'Test-PigoInstance.ps1') -Port 4010
$pigoPython = 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe'
& $pigoPython (Join-Path $PSScriptRoot 'run_pigo.py') --app-root 'C:\Projetos\P.I.G.O' --port 4010 --check
if ($LASTEXITCODE -ne 0) { throw 'Configuracao incompleta; nenhuma tarefa registrada.' }
& $pigoPython (Join-Path $PSScriptRoot 'task_config.py') --app-root 'C:\Projetos\P.I.G.O' --python $pigoPython --port 4010 --output $pigoOutput
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar arquivos; nenhuma tarefa registrada.' }
