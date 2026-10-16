#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 4010,
    [ValidateRange(1, 30)][int]$TimeoutSeconds = 8
)
$ErrorActionPreference = 'Stop'
$pigoBaseUrl = 'http://127.0.0.1:' + $Port
Add-Type -AssemblyName System.Net.Http
$pigoHandler = New-Object System.Net.Http.HttpClientHandler
# This checker only contacts loopback. Do not send local tests through an
# inherited system proxy or follow redirects to a different host.
$pigoHandler.UseProxy = $false
$pigoHandler.AllowAutoRedirect = $false
$pigoClient = New-Object System.Net.Http.HttpClient($pigoHandler)
$pigoClient.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
function Get-PigoResponse([string]$Route, [string]$Accept) {
    $pigoUrl = $pigoBaseUrl + $Route
    Write-Host ('Verificando GET ' + $pigoUrl + ' (sem proxy)...')
    $pigoRequest = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, $pigoUrl)
    $null = $pigoRequest.Headers.TryAddWithoutValidation('Accept', $Accept)
    $pigoResponse = $null
    try {
        $pigoResponse = $pigoClient.SendAsync($pigoRequest).GetAwaiter().GetResult()
        $pigoBody = $pigoResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $pigoStatus = [int]$pigoResponse.StatusCode
        Write-Host ('GET ' + $Route + ': HTTP ' + $pigoStatus)
        return [PSCustomObject]@{
            Status = $pigoStatus
            ContentType = [string]$pigoResponse.Content.Headers.ContentType
            Body = $pigoBody
        }
    } catch {
        $pigoException = $_.Exception
        $pigoTimedOut = $false
        while ($pigoException) {
            if ($pigoException -is [System.OperationCanceledException] -or $pigoException -is [System.TimeoutException]) {
                $pigoTimedOut = $true
                break
            }
            $pigoException = $pigoException.InnerException
        }
        $pigoCause = $_.Exception.GetBaseException()
        if ($pigoTimedOut) {
            throw ('GET ' + $pigoUrl + ': tempo limite de ' + $TimeoutSeconds + 's. Confira se o terminal 4010 continua executando e sem texto selecionado.')
        }
        throw ('GET ' + $pigoUrl + ': falha de conexao (' + $pigoCause.GetType().Name + '). Confira o processo que escuta a porta.')
    } finally {
        if ($pigoResponse) { $pigoResponse.Dispose() }
        $pigoRequest.Dispose()
    }
}
try {
    $pigoHealthResponse = Get-PigoResponse '/api/health' 'application/json'
    if ($pigoHealthResponse.Status -ne 200 -or $pigoHealthResponse.ContentType -notmatch 'application/json') {
        throw ('GET /api/health: esperado HTTP 200 com JSON; recebido HTTP ' + $pigoHealthResponse.Status + '.')
    }
    $pigoHealth = $pigoHealthResponse.Body | ConvertFrom-Json
    if ($pigoHealth.status -ne 'ok' -or $pigoHealth.service -ne 'pigo') {
        throw 'GET /api/health: a porta nao respondeu como API do PIGO.'
    }
    foreach ($pigoRoute in @('/login', '/dashboard/vendas', '/funcionarios', '/performance', '/cadastros/produtos')) {
        $pigoResponse = Get-PigoResponse $pigoRoute 'text/html'
        if ($pigoResponse.Status -ne 200 -or $pigoResponse.ContentType -notmatch 'text/html') {
            throw ('GET ' + $pigoRoute + ': esperado HTTP 200 com HTML; recebido HTTP ' + $pigoResponse.Status + '.')
        }
    }
    $pigoProtected = Get-PigoResponse '/api/me/tenant' 'application/json'
    if ($pigoProtected.Status -ne 401) {
        throw ('GET /api/me/tenant: esperado HTTP 401 sem autenticacao; recebido HTTP ' + $pigoProtected.Status + '.')
    }
    Write-Output 'API, painel compilado, acesso direto as telas e autenticacao verificados. Nenhuma gravacao enviada.'
} finally {
    $pigoClient.Dispose()
}
