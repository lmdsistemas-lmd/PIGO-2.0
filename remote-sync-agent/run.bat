@echo off
setlocal
cd /d %~dp0
title LMD Dashboard Sync Agent
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ==========================================
echo   LMD DASHBOARD - AGENTE DE SINCRONISMO
echo ==========================================
echo.

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe --version >nul 2>&1
    if errorlevel 1 (
        echo Ambiente virtual aponta para um Python removido. Recriando...
        rmdir /s /q venv
    )
)

if not exist venv\Scripts\python.exe (
    echo Criando ambiente virtual...
    python -m venv venv
)

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo Instalando/Atualizando dependencias...
python -m pip install -r requirements.txt

if not exist .env (
    echo ERRO: Arquivo .env nao encontrado!
    echo Copiando .env.example para .env...
    copy .env.example .env
    echo.
    echo [IMPORTANTE] Edite o arquivo .env com suas configuracoes antes de rodar.
    pause
    exit
)

echo Iniciando o Agente...
python agent.py

pause
