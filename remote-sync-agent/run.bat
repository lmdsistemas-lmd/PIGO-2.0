@echo off
cd /d %~dp0
title LMD Dashboard Sync Agent
echo ==========================================
echo   LMD DASHBOARD - AGENTE DE SINCRONISMO
echo ==========================================
echo.

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo Instalando/Atualizando dependencias...
pip install -r requirements.txt

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
