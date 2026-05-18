@echo off
setlocal

title Iniciando Dashboard Offline

echo ==========================================
echo   DASHBOARD WEB - MODO DEMONSTRACAO
echo ==========================================
echo.

cd /d %~dp0

if not exist backend\venv\Scripts\python.exe (
    echo ERRO: Ambiente virtual nao encontrado em backend\venv
    echo Crie o ambiente virtual antes de continuar.
    pause
    exit /b 1
)

if not exist frontend\dist\index.html (
    echo Build do frontend nao encontrado.
    echo Gerando build de producao...
    echo.

    cd /d %~dp0frontend
    call npm run build

    if errorlevel 1 (
        echo.
        echo ERRO: Falha ao gerar o build do frontend.
        pause
        exit /b 1
    )

    cd /d %~dp0
)

echo.
echo Iniciando backend...
echo.

start "Backend Dashboard" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak > nul

echo.
echo Dashboard iniciado.
echo Acesse nesta maquina: http://127.0.0.1:8000
echo Acesse na rede:      http://192.168.1.12:8000
echo.
echo Dica: descubra o IP com o comando ipconfig
echo.

start http://127.0.0.1:8000

endlocal