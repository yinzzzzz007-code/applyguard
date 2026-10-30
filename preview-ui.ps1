param([int]$Port = 8870)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '请先创建 .venv 并安装 requirements.txt；操作见 UI-README.md。'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend\dist\index.html'))) {
    throw '缺少构建文件，请在 frontend 目录执行 npm ci 和 npm run build。'
}
$env:APPLYGUARD_HOST = '127.0.0.1'
$env:APPLYGUARD_PORT = "$Port"
Write-Host "ApplyGuard: http://127.0.0.1:$Port"
Write-Host '按 Ctrl+C 停止。端口占用时可改用 -Port 参数。'
& $pythonPath -m backend.app
