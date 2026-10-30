@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please create .venv and install requirements.txt. See UI-README.md.
  pause
  exit /b 1
)
set "APPLYGUARD_HOST=127.0.0.1"
set "APPLYGUARD_PORT=8870"
echo ApplyGuard: http://127.0.0.1:8870
echo Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m backend.app
endlocal
