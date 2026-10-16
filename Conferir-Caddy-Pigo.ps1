#Requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ne 'WIN-JG1E0O7FSBS') { throw 'Execute somente na VM WIN-JG1E0O7FSBS.' }
$pigoTargetHost = 'pigo.lmdsistemasdev.qzz.io'
$pigoResults = New-Object 'System.Collections.Generic.List[string]'
$pigoHostMatches = 0
$pigoSharedHostGroup = $false
function Find-PigoProxy([object]$Node, [bool]$InPigo) {
    if ($null -eq $Node -or $Node -is [string] -or $Node -is [ValueType]) { return }
    if ($Node -is [System.Collections.IEnumerable] -and $Node -isnot [PSCustomObject]) {
        foreach ($pigoItem in $Node) { Find-PigoProxy $pigoItem $InPigo }
        return
    }
    $pigoHere = $InPigo
    $pigoMatchProperty = $Node.PSObject.Properties['match']
    if ($pigoMatchProperty) {
        $pigoHosts = @($pigoMatchProperty.Value | ForEach-Object { $_.PSObject.Properties['host'] } | ForEach-Object { $_.Value } | Where-Object { $_ -is [string] -and $_.Length -gt 0 })
        if ($pigoHosts.Count -gt 0) {
            $pigoHere = $pigoHosts -contains $pigoTargetHost
            if (-not $pigoHere) { return }
            if ($pigoHere) {
                $script:pigoHostMatches++
                if ($pigoHosts.Count -gt 1) { $script:pigoSharedHostGroup = $true }
            }
        }
    }
    $pigoHandler = $Node.PSObject.Properties['handler']
    $pigoUpstreams = $Node.PSObject.Properties['upstreams']
    if ($pigoHere -and $pigoHandler -and $pigoHandler.Value -eq 'reverse_proxy' -and $pigoUpstreams) {
        foreach ($pigoUpstream in $pigoUpstreams.Value) {
            $pigoDial = [string]$pigoUpstream.dial
            # Only local host:port values are printed. Other configuration,
            # credentials, headers and addresses stay inside this process.
            if ($pigoDial -match '^(?:localhost|127\.0\.0\.1|\[::1\]):[0-9]{1,5}$') {
                $pigoResults.Add($pigoDial)
            } else { $pigoResults.Add('(destino diferente de loopback; valor omitido)') }
        }
    }
    foreach ($pigoProperty in $Node.PSObject.Properties) { Find-PigoProxy $pigoProperty.Value $pigoHere }
}
Add-Type -AssemblyName System.Net.Http
$pigoHandler = New-Object System.Net.Http.HttpClientHandler
$pigoHandler.UseProxy = $false
$pigoHandler.AllowAutoRedirect = $false
$pigoClient = New-Object System.Net.Http.HttpClient($pigoHandler)
$pigoClient.Timeout = [TimeSpan]::FromSeconds(5)
$pigoResponse = $null
try {
    $pigoResponse = $pigoClient.GetAsync('http://127.0.0.1:2019/config/').GetAwaiter().GetResult()
    if ([int]$pigoResponse.StatusCode -ne 200) { throw 'API local do Caddy nao respondeu200.' }
    if ([string]$pigoResponse.Content.Headers.ContentType -notmatch 'application/json') { throw 'A porta2019 nao retornou configuracao JSON.' }
    $pigoConfig = $pigoResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
    $pigoApps = $pigoConfig.PSObject.Properties['apps']
    if (-not $pigoApps -or -not $pigoApps.Value.PSObject.Properties['http']) { throw 'Sem estrutura HTTP reconhecida.' }
    Find-PigoProxy $pigoApps.Value.http $false
    [PSCustomObject]@{
        Fonte = 'Caddy em execucao: API local2019'
        Dominio = $pigoTargetHost
        GruposComHostPigo = $pigoHostMatches
        CompartilhaGrupoComOutroHost = $pigoSharedHostGroup
        DestinosPigo = (@($pigoResults | Sort-Object -Unique) -join ', ')
    } | Format-List
} catch {
    Write-Output 'Nao foi possivel obter a rota pela API local2019. Isso nao prova falha no Caddy; a administracao pode usar outro endereco ou estar desativada.'
    Write-Output ('Tipo do retorno: ' + $_.Exception.GetBaseException().GetType().Name)
} finally {
    if ($pigoResponse) { $pigoResponse.Dispose() }
    $pigoClient.Dispose()
}
$pigoConfigFile = 'C:\Projetos\caddy\Caddyfile.production'
if (Test-Path -LiteralPath $pigoConfigFile -PathType Leaf) {
    [PSCustomObject]@{ Arquivo = $pigoConfigFile; SHA256 = (Get-FileHash -LiteralPath $pigoConfigFile -Algorithm SHA256).Hash } | Format-List
}
Write-Output 'Somente leitura: nenhuma rota, arquivo ou processo foi alterado.'
