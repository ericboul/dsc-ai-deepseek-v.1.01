@echo off
setlocal
cd /d "%~dp0"

REM --- Environnement portable : tout est relatif a ce dossier ---
set "HF_HUB_DISABLE_SYMLINKS=1"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

REM --- 1er demarrage : Python embarque (via PowerShell, avant que Python existe) ---
if not exist "python\python.exe" (
  echo Premier demarrage : installation de Python embarque...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_python.ps1"
  if errorlevel 1 (
    echo.
    echo Echec du telechargement de Python. Verifie ta connexion puis relance run.bat.
    pause
    exit /b 1
  )
)

REM --- 1er demarrage : librairies Python (libs\) + Piper (piper\) ---
set "NEEDBOOT="
if not exist "libs\.installed" set "NEEDBOOT=1"
if not exist "piper\piper\piper.exe" set "NEEDBOOT=1"
if defined NEEDBOOT (
  "%~dp0python\python.exe" "%~dp0bootstrap.py"
  if errorlevel 1 (
    echo.
    echo Installation impossible. Verifie ta connexion internet puis relance run.bat.
    pause
    exit /b 1
  )
)

REM --- Cles API : chargees depuis les fichiers si presents. Sinon, saisis-la dans
REM l'interface (carte "Cerveau (IA)") au 1er demarrage : le copilote attend.
if "%DEEPSEEK_API_KEY%"=="" if exist "deepseek_key.txt" set /p DEEPSEEK_API_KEY=<deepseek_key.txt
if "%ANTHROPIC_API_KEY%"=="" if exist "apikey.txt" set /p ANTHROPIC_API_KEY=<apikey.txt
if "%OPENAI_API_KEY%"=="" if exist "openai_key.txt" set /p OPENAI_API_KEY=<openai_key.txt

echo Lancement du DCS AI DeepSeek (interface + copilote)...
"%~dp0python\python.exe" "%~dp0app.py"
echo.
pause
