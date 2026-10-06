param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot '..\..\..'),
    [string]$Python = 'python',
    [string]$Executor = '未指定',
    [switch]$FinalizeOnly,
    [string]$RunDirectory
)
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Write-JsonFile($Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 18), $utf8)
}
function Finalize-Evidence([string]$Directory) {
    $absolute = (Resolve-Path -LiteralPath $Directory).Path
    $items = @(Get-ChildItem -LiteralPath $absolute -File -Recurse |
        Where-Object { $_.Name -notlike 'manifest*.json' } |
        Sort-Object FullName | ForEach-Object {
            [ordered]@{ path=$_.FullName.Substring($absolute.Length+1).Replace('\','/'); bytes=$_.Length; sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
        })
    $manifest = [ordered]@{generated_at=[DateTimeOffset]::UtcNow.ToString('o'); algorithm='SHA256'; files=$items}
    $revision = 'manifest-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,6) + '.json'
    Write-JsonFile (Join-Path $absolute $revision) $manifest
    Write-JsonFile (Join-Path $absolute 'manifest.sha256.json') $manifest
    Write-Output "Evidence: $absolute"
}
if ($FinalizeOnly) {
    if (-not $RunDirectory) { throw 'FinalizeOnly requires RunDirectory.' }
    Finalize-Evidence $RunDirectory
    return
}
$project = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $project 'backend/app.py'))) { throw 'Not an ApplyGuard project root.' }
$head = (& git -C $project rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify Git HEAD.' }
$runId = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + $head.Substring(0,7) + '-' + [guid]::NewGuid().ToString('N').Substring(0,6)
$runPath = Join-Path $project ('output/test-runs/' + $runId)
[void][IO.Directory]::CreateDirectory((Join-Path $runPath 'logs'))
[IO.File]::Copy($PSCommandPath, (Join-Path $runPath 'Collect-TestEvidence.ps1'))
$commands = New-Object System.Collections.Generic.List[object]
$started = [DateTimeOffset]::UtcNow.ToString('o')
$gitStatus = (& git -C $project status --short | Out-String)
[IO.File]::WriteAllText((Join-Path $runPath 'git-status.txt'), $gitStatus, $utf8)
[IO.File]::WriteAllText((Join-Path $runPath 'tracked-diff.patch'), (& git -C $project diff --no-ext-diff HEAD | Out-String), $utf8)
$inputHashes = @('frontend/package-lock.json','requirements.txt','data/career-vault.seed.json','frontend/public/data/career-vault.seed.json','eval/c_cases.json') | ForEach-Object {
    $full = Join-Path $project $_
    if (Test-Path -LiteralPath $full) { [ordered]@{path=$_;sha256=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()} }
}
Write-JsonFile (Join-Path $runPath 'hashes-input.json') $inputHashes
function Invoke-EvidenceCommand([string]$Id, [string]$Directory, [string]$Program, [string[]]$Arguments, [switch]$Metrics) {
    $begin = [DateTimeOffset]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $logPath = Join-Path $runPath ('logs/' + $Id + '.log')
    $exitCode = $null
    $state = 'ERROR'
    Push-Location -LiteralPath $Directory
    try {
        $null = Get-Command -Name $Program -ErrorAction Stop
        $global:LASTEXITCODE = $null
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $Program @Arguments *> $logPath
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousPreference
        if ($null -ne $exitCode) {
            $state = if ($exitCode -eq 0) { if ($Metrics) {'REVIEW_REQUIRED'} else {'PASS'} } else {'FAIL'}
        }
    } catch {
        [IO.File]::AppendAllText($logPath, ($_ | Out-String), $utf8)
        $state = 'ERROR'
    } finally {
        $ErrorActionPreference = 'Stop'
        Pop-Location
        $timer.Stop()
    }
    $commands.Add([ordered]@{id=$Id; program=$Program; args=$Arguments; cwd=$Directory; started_at=$begin.ToString('o'); finished_at=[DateTimeOffset]::UtcNow.ToString('o'); elapsed_ms=$timer.ElapsedMilliseconds; exit_code=$exitCode; status=$state; log=('logs/'+$Id+'.log')})
    Write-JsonFile (Join-Path $runPath 'commands.json') @($commands.ToArray())
    Write-Output "$Id : $state (exit=$exitCode)"
}
function Read-ToolVersion([string]$Program, [string[]]$Arguments) {
    try {
        $null = Get-Command -Name $Program -ErrorAction Stop
        return (& $Program @Arguments 2>&1 | Out-String).Trim()
    } catch { return 'UNAVAILABLE: ' + $Program }
}
$runtime = [ordered]@{
    run_id=$runId; commit=$head; executor=$Executor; started_at=$started;
    project=$project; os=[Environment]::OSVersion.VersionString;
    powershell=$PSVersionTable.PSVersion.ToString(); timezone=[TimeZoneInfo]::Local.Id;
    python=(Read-ToolVersion $Python @('--version')); node=(Read-ToolVersion 'node' @('--version'));
    npm=(Read-ToolVersion 'npm.cmd' @('--version')); mode='OFFLINE';
    note='No browser, PDF or real-model tests are implied by this command collector.'
}
Write-JsonFile (Join-Path $runPath 'run.json') $runtime
Invoke-EvidenceCommand 'backend-unittest' $project $Python @('-X','utf8','-m','unittest','discover','-s','tests','-v')
Invoke-EvidenceCommand 'frontend-build' (Join-Path $project 'frontend') 'npm.cmd' @('run','build')
Invoke-EvidenceCommand 'frontend-lint' (Join-Path $project 'frontend') 'npm.cmd' @('run','lint')
Invoke-EvidenceCommand 'frontend-smoke' (Join-Path $project 'frontend') 'npm.cmd' @('run','smoke')
Invoke-EvidenceCommand 'offline-benchmark' $project $Python @('-X','utf8','-m','eval.c_benchmark') -Metrics
$runtime.finished_at = [DateTimeOffset]::UtcNow.ToString('o')
Write-JsonFile (Join-Path $runPath 'run.json') $runtime
$summary = @('# 自动命令执行摘要', '', "运行编号：$runId", "代码：$head", '', '此文件只汇总命令；业务指标、浏览器案例和缺陷仍需人工判定。', '', '| 命令 | 状态 | 退出码 | 日志 |', '|---|---|---|---|')
foreach ($item in $commands) { $summary += "| $($item.id) | $($item.status) | $($item.exit_code) | $($item.log) |" }
[IO.File]::WriteAllText((Join-Path $runPath 'summary.md'), ($summary -join [Environment]::NewLine), $utf8)
Finalize-Evidence $runPath
if (@($commands | Where-Object { $_.status -in @('FAIL','ERROR') }).Count -gt 0) { exit 1 }
