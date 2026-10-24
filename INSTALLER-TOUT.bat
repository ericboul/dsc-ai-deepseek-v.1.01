@echo off
rem ============================================================
rem  DCS RYZEN Copilote - installateur automatique (point d'entree)
rem  Double-clique sur ce fichier : il installe tout puis propose
rem  de lancer le copilote. Options possibles :
rem    INSTALLER-TOUT.bat -Provider ollama -NoPrompt
rem    INSTALLER-TOUT.bat -SkipDcs -SkipModels
rem ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title DCS RYZEN Copilote - installation automatique

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0eb_install.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Installation terminee sans erreur.
) else (
  echo Installation terminee avec des avertissements ^(code %RC%^).
  echo Voir EB-INSTALLATION-LOG.txt dans ce dossier.
)
echo.
pause
exit /b %RC%
