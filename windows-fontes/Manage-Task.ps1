#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory = $true)][ValidateSet('Install', 'Start', 'Stop', 'EnableAutostart', 'Uninstall', 'Status')][string]$Action)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Execute no Windows Server.' }
$pigoInfo = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'task.json') -Raw | ConvertFrom-Json
if ($pigoInfo.name -notmatch '^Pigo[A-Za-z0-9_-]{1,60}$' -or $pigoInfo.task_path -ne '\' -or $pigoInfo.port -lt 1 -or $pigoInfo.port -gt 65535) { throw 'Perfil de tarefa invalido.' }
if ($Action -eq 'Status') {
    Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name | Select-Object TaskName, State
    Get-ScheduledTaskInfo -TaskPath '\' -TaskName $pigoInfo.name | Select-Object LastRunTime, LastTaskResult
    return
}
$pigoIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$pigoPrincipal = New-Object Security.Principal.WindowsPrincipal($pigoIdentity)
if (-not $pigoPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Execute no PowerShell como administrador.' }
function Grant-PigoTaskPath([string]$Path, [string]$Permission) {
    $pigoResolved = (Resolve-Path -LiteralPath $Path).Path
    if ($pigoResolved.TrimEnd('\') -eq [IO.Path]::GetPathRoot($pigoResolved).TrimEnd('\')) { throw 'Nao sera concedido acesso na raiz do disco.' }
    & icacls.exe $pigoResolved /grant ('*S-1-5-19:' + $Permission) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw ('Falha ao conceder acesso LocalService: ' + $pigoResolved) }
}
switch ($Action) {
    'Install' {
        if (Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name -ErrorAction SilentlyContinue) { throw 'Tarefa ja existente; nao sera substituida.' }
        if (Get-Service -Name $pigoInfo.name -ErrorAction SilentlyContinue) { throw 'Ja existe um servico com esse nome. Preserve-o e informe o retorno.' }
        & $pigoInfo.executable (Join-Path $PSScriptRoot 'run_pigo.py') --app-root $pigoInfo.app_root --port $pigoInfo.port --check
        if ($LASTEXITCODE -ne 0) { throw 'Configuracao incompleta; tarefa nao registrada.' }
        $pigoBasePython = & $pigoInfo.executable -c 'import sys; print(sys.base_prefix)'
        if ($LASTEXITCODE -ne 0) { throw 'Runtime Python nao identificado.' }
        Grant-PigoTaskPath $PSScriptRoot '(OI)(CI)RX'
        Grant-PigoTaskPath $pigoInfo.log_directory '(OI)(CI)M'
        Grant-PigoTaskPath $pigoInfo.app_root '(OI)(CI)RX'
        Grant-PigoTaskPath $pigoInfo.executable 'RX'
        Grant-PigoTaskPath (([string]$pigoBasePython).Trim()) '(OI)(CI)RX'
        $pigoTaskAction = New-ScheduledTaskAction -Execute $pigoInfo.executable -Argument $pigoInfo.arguments -WorkingDirectory $pigoInfo.working_directory
        $pigoTaskPrincipal = New-ScheduledTaskPrincipal -UserId 'S-1-5-19' -LogonType ServiceAccount -RunLevel Limited
        $pigoSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval ([TimeSpan]::FromMinutes(1)) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $pigoTask = New-ScheduledTask -Action $pigoTaskAction -Principal $pigoTaskPrincipal -Settings $pigoSettings -Description 'PIGO em segundo plano; teste 4010, inicialmente sem disparo automatico.'
        Register-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name -InputObject $pigoTask | Out-Null
        Write-Output 'Tarefa registrada sem disparo automatico, ainda nao iniciada.'
    }
    'Start' {
        $pigoTask = Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name
        if ($pigoTask.State -eq 'Running') { Write-Output 'Tarefa ja em execucao.'; return }
        if (Get-NetTCPConnection -State Listen -LocalPort $pigoInfo.port -ErrorAction SilentlyContinue) { throw 'Porta ocupada. O processo atual nao sera encerrado.' }
        Start-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name
        Write-Output 'Aguardando a API da tarefa...'
        Add-Type -AssemblyName System.Net.Http
        $pigoHandler = New-Object System.Net.Http.HttpClientHandler
        $pigoHandler.UseProxy = $false
        $pigoHandler.AllowAutoRedirect = $false
        $pigoClient = New-Object System.Net.Http.HttpClient($pigoHandler)
        $pigoClient.Timeout = [TimeSpan]::FromSeconds(2)
        $pigoOk = $false
        try {
            for ($pigoAttempt = 0; $pigoAttempt -lt 20; $pigoAttempt++) {
                try {
                    $pigoResponse = $pigoClient.GetAsync(('http://127.0.0.1:' + $pigoInfo.port + '/api/health')).GetAwaiter().GetResult()
                    try {
                        $pigoHealth = $pigoResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
                        if ([int]$pigoResponse.StatusCode -eq 200 -and $pigoHealth.status -eq 'ok' -and $pigoHealth.service -eq 'pigo') { $pigoOk = $true; break }
                    } finally { $pigoResponse.Dispose() }
                } catch { }
                Start-Sleep -Milliseconds 500
            }
        } finally { $pigoClient.Dispose() }
        if (-not $pigoOk) {
            Stop-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name
            throw ('A API nao ficou pronta. Tarefa de teste interrompida. Confira ' + $pigoInfo.log_directory)
        }
        try { & (Join-Path $PSScriptRoot 'Test-PigoInstance.ps1') -Port $pigoInfo.port }
        catch { Stop-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name; throw }
        Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name | Select-Object TaskName, State
    }
    'Stop' { Stop-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name }
    'EnableAutostart' {
        if ((Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name).State -ne 'Running') { throw 'Valide a tarefa iniciada antes de habilitar inicio automatico.' }
        & (Join-Path $PSScriptRoot 'Test-PigoInstance.ps1') -Port $pigoInfo.port
        $pigoTrigger = New-ScheduledTaskTrigger -AtStartup
        $pigoTrigger.Delay = 'PT30S'
        Set-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name -Trigger $pigoTrigger | Out-Null
        Write-Output 'Disparo ao iniciar o Windows habilitado com atraso de 30s; validar apos reboot em janela acordada.'
    }
    'Uninstall' {
        if ((Get-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name).State -eq 'Running') { throw 'Pare somente esta tarefa antes de remove-la.' }
        Unregister-ScheduledTask -TaskPath '\' -TaskName $pigoInfo.name -Confirm:$false
        Write-Output 'Tarefa removida. Aplicacao, dados, configuracoes, logs e permissoes adicionadas preservados.'
    }
}
