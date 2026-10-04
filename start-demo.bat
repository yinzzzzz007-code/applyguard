@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM One-click local demo: backend :8000 + Vite :5173
set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [ApplyGuard] .venv not found. Creating and installing requirements...
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ApplyGuard] ERROR: python not found on PATH.
    pause
    exit /b 1
  )
  python -m venv .venv
  if errorlevel 1 (
    echo [ApplyGuard] ERROR: failed to create .venv
    pause
    exit /b 1
  )
  "%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
  if errorlevel 1 (
    echo [ApplyGuard] ERROR: pip install failed
    pause
    exit /b 1
  )
)

if not exist "%ROOT%frontend\node_modules\" (
  echo [ApplyGuard] frontend/node_modules missing. Running npm install...
  where npm >nul 2>&1
  if errorlevel 1 (
    echo [ApplyGuard] ERROR: npm not found on PATH.
    pause
    exit /b 1
  )
  pushd "%ROOT%frontend"
  call npm install
  if errorlevel 1 (
    popd
    echo [ApplyGuard] ERROR: npm install failed
    pause
    exit /b 1
  )
  popd
)

REM Optional: load applyguard\.env into this process (KEY=VALUE lines; # comments ok)
if exist "%ROOT%.env" (
  echo [ApplyGuard] Loading "%ROOT%.env" for backend...
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ROOT%.env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
  )
) else (
  echo [ApplyGuard] No .env found. Offline demo still works. For model path, copy .env.example to .env and set APPLYGUARD_AI_API_KEY.
)

echo [ApplyGuard] Freeing ports 8000 / 5173 if stale backends are holding them...
powershell -NoProfile -Command ^
  "foreach ($p in 8000,5173) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*backend.app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [ApplyGuard] Starting backend on http://127.0.0.1:8000 ...
start "ApplyGuard-Backend" /D "%ROOT%" cmd /k ".\.venv\Scripts\python.exe -m backend.app"

echo [ApplyGuard] Starting frontend on http://127.0.0.1:5173 ...
start "ApplyGuard-Frontend" /D "%ROOT%frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"

echo [ApplyGuard] Waiting for Vite, then opening browser...
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 40;$i++){ try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {} ; Start-Sleep -Milliseconds 500 }; if(-not $ok){ Write-Host '[ApplyGuard] Frontend not ready yet; opening anyway.' }; Start-Process 'http://127.0.0.1:5173/'"

echo.
echo [ApplyGuard] Backend window: ApplyGuard-Backend
echo [ApplyGuard] Frontend window: ApplyGuard-Frontend
echo [ApplyGuard] Close those two windows to stop the servers.
echo.
pause
endlocal
