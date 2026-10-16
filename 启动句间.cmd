@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "%~dp0dist\句间\_internal\python311.dll" if exist "%~dp0dist\句间\句间.pkg" (
  start "" /D "%~dp0dist\句间" "%~dp0dist\句间\句间.exe" %*
  exit /b 0
)
call "%~dp0run.cmd" %*
exit /b %errorlevel%
