@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM One-click stop: backend :8000 + Vite :5173 / :5174 + leftover python/node
echo [ApplyGuard] Stopping local demo listeners...

powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "taskkill /FI 'WINDOWTITLE eq ApplyGuard-Backend*' /T /F | Out-Null;" ^
  "taskkill /FI 'WINDOWTITLE eq ApplyGuard-Frontend*' /T /F | Out-Null;" ^
  "$ids = New-Object 'System.Collections.Generic.HashSet[int]';" ^
  "foreach ($p in 8000,5173,5174) {" ^
  "  Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {" ^
  "    if ($_.OwningProcess -gt 0) { [void]$ids.Add([int]$_.OwningProcess) }" ^
  "  }" ^
  "};" ^
  "Get-CimInstance Win32_Process | Where-Object {" ^
  "  $_.CommandLine -like '*backend.app*' -or $_.CommandLine -like '*vite*' -and ($_.CommandLine -like '*--port 5173*' -or $_.CommandLine -like '*--port 5174*')" ^
  "} | ForEach-Object { [void]$ids.Add([int]$_.ProcessId) };" ^
  "foreach ($id in $ids) { if ($id -gt 0) { & taskkill /PID $id /T /F | Out-Null; Write-Host \"[ApplyGuard] stopped PID $id\" } };" ^
  "Start-Sleep -Milliseconds 400;" ^
  "$left = @(); foreach ($p in 8000,5173,5174) {" ^
  "  if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $left += $p }" ^
  "};" ^
  "if ($left.Count) { Write-Host \"[ApplyGuard] still listening: $($left -join ', ')\" } else { Write-Host '[ApplyGuard] 8000 / 5173 / 5174 are free.' }"

echo.
pause
endlocal
