@echo off
setlocal

title Build Frontend

cd /d %~dp0frontend

echo Gerando build de producao do frontend...
call npm run build

if errorlevel 1 (
    echo.
    echo ERRO no build do frontend.
    pause
    exit /b 1
)

echo.
echo Build concluido com sucesso.
echo Pasta gerada: frontend\dist
pause

endlocal