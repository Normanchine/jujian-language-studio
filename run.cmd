@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Dependencies are not installed. Run setup.ps1 first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
