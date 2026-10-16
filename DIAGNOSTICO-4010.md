# Recuperar somente o teste temporário 4010

O usuário confirmou que o terminal permanece aberto, mas o navegador também deixou de responder. A causa ainda não foi determinada. O instalador parou antes de criar o serviço.

No terminal que iniciou o teste 4010, pressione **Ctrl+C**. Não encerre os terminais da porta 4000, Vite ou Caddy. Depois que o prompt voltar:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    if ($env:COMPUTERNAME -ne 'WIN-JG1E0O7FSBS') { throw 'Execute na VM WIN-JG1E0O7FSBS.' }
    if (Get-NetTCPConnection -State Listen -LocalPort 4010 -ErrorAction SilentlyContinue) { throw 'O teste anterior ainda ocupa a porta 4010. Nao inicie outra copia.' }
    Set-Location 'C:\Projetos\P.I.G.O\backend'
    & '.\venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 4010 --workers 1
}
```

Quando aparecer `Application startup complete`, execute em **outro PowerShell da mesma VM**:

```powershell
@'
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError
opener = build_opener(ProxyHandler({}))
for route in ("/api/health", "/login"):
    try:
        with opener.open("http://127.0.0.1:4010" + route, timeout=5) as response:
            response.read(4096)
            print(route, "HTTP", response.status, flush=True)
    except HTTPError as error:
        print(route, "HTTP", error.code, flush=True)
    except Exception as error:
        print(route, type(error).__name__, flush=True)
'@ | & 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' -
```

Envie a saída desse teste e as linhas de erro que aparecerem no terminal 4010. O resultado esperado é HTTP200 em ambas as URLs. Não aumente o timeout nem pule a verificação para instalar o serviço. Não envie arquivos .env, senhas ou tokens.
