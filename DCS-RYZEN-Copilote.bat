@echo off
rem ============================================================
rem  DCS RYZEN Copilote - lanceur unique
rem  - si le copilote tourne deja : ouvre seulement l'interface
rem  - 1er demarrage : installe automatiquement ce qui manque
rem  - sinon         : demarre l'interface web + le copilote
rem ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title DCS RYZEN Copilote

rem --- une seule instance a la fois (evite le plantage "port 5010 deja utilise") ---
set "STATE="
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue) { 'RUNNING' } else { 'FREE' }"`) do set "STATE=%%A"
if /i "%STATE%"=="RUNNING" (
  echo.
  echo   ============================================================
  echo    Le copilote tourne DEJA - pas besoin de le relancer.
  echo    Ouverture de l'interface de configuration...
  echo    Cette fenetre va se fermer dans 6 secondes.
  echo   ============================================================
  start "" "http://127.0.0.1:5001"
  ping -n 7 127.0.0.1 >nul
  exit /b 0
)

if not exist "python\python.exe" goto install
if not exist "libs\.installed"  goto install
if not exist "config.json"      goto install
goto run

:install
echo.
echo   Premiere utilisation : installation automatique des composants...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0eb_install.ps1" -NoPrompt
if errorlevel 1 (
  echo.
  echo   Installation incomplete. Relance INSTALLER-TOUT.bat pour voir le detail.
  pause
  exit /b 1
)

:run
rem Charge les cles API eventuelles depuis les fichiers du dossier
if not defined DEEPSEEK_API_KEY if exist "deepseek_key.txt" set /p DEEPSEEK_API_KEY=<deepseek_key.txt
if not defined OPENAI_API_KEY   if exist "openai_key.txt"   set /p OPENAI_API_KEY=<openai_key.txt
if not defined ANTHROPIC_API_KEY if exist "apikey.txt"      set /p ANTHROPIC_API_KEY=<apikey.txt

call "%~dp0run.bat"
exit /b %ERRORLEVEL%
