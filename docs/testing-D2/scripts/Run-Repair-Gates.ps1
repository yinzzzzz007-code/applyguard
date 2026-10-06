param(
  [string]$EvidenceDir = ''
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $EvidenceDir) {
  $EvidenceDir = Join-Path $repo 'docs\testing-D2\evidence\20261006-repair-gates'
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$records = [System.Collections.Generic.List[object]]::new()

function Invoke-RepairGate {
  param([string]$Name, [string]$WorkingDir, [string]$Executable, [string[]]$Arguments)
  $started = (Get-Date).ToUniversalTime().ToString('o')
  Push-Location $WorkingDir
  try {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & $Executable @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
  } catch {
    $output = $_ | Out-String
    $code = 1
  } finally {
    $ErrorActionPreference = $previousPreference
    Pop-Location
  }
  $ended = (Get-Date).ToUniversalTime().ToString('o')
  $log = Join-Path $EvidenceDir "$Name.log"
  @("command: $Executable $($Arguments -join ' ')", "cwd: $WorkingDir", "started_utc: $started", "ended_utc: $ended", "exit_code: $code", '', $output) |
    Set-Content -LiteralPath $log -Encoding utf8
  $records.Add([ordered]@{ name = $Name; command = "$Executable $($Arguments -join ' ')"; cwd = $WorkingDir;
      started_utc = $started; ended_utc = $ended; exit_code = $code; log = (Split-Path $log -Leaf) })
  Write-Output "$Name : exit=$code"
}

$sha = (& git -C $repo rev-parse HEAD).Trim()
$status = (& git -C $repo status --short) -join "`n"
$files = @('data/career-vault.seed.json', 'eval/c_cases_zh_v2.json', 'requirements.txt', 'frontend/package-lock.json')
$hashes = [ordered]@{}
foreach ($file in $files) {
  $candidate = Join-Path $repo $file
  if (Test-Path -LiteralPath $candidate) {
    $hashes[$file] = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}
$environment = [ordered]@{
  captured_utc = (Get-Date).ToUniversalTime().ToString('o')
  timezone = [TimeZoneInfo]::Local.Id
  git_head = $sha
  git_status = $status
  os = [System.Environment]::OSVersion.VersionString
  python = (& python --version 2>&1 | Out-String).Trim()
  node = (& node --version 2>&1 | Out-String).Trim()
  npm = (& npm.cmd --version 2>&1 | Out-String).Trim()
  hashes = $hashes
}
$environment | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'environment.json') -Encoding utf8

Invoke-RepairGate 'backend-unittest' $repo 'python' @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
Invoke-RepairGate 'benchmark-zh-v2' $repo 'python' @('-m', 'eval.c_benchmark')
Invoke-RepairGate 'frontend-build' (Join-Path $repo 'frontend') 'npm.cmd' @('run', 'build')
Invoke-RepairGate 'frontend-lint' (Join-Path $repo 'frontend') 'npm.cmd' @('run', 'lint')
Invoke-RepairGate 'frontend-smoke' (Join-Path $repo 'frontend') 'npm.cmd' @('run', 'smoke')

$ignored = (& git -C $repo check-ignore 'data/local/cand_demo_001.json' 2>&1 | Out-String).Trim()
$tracked = (& git -C $repo ls-files 'data/local/' | Out-String).Trim()
$privacyPass = ($LASTEXITCODE -eq 0 -and $ignored -eq 'data/local/cand_demo_001.json' -and -not $tracked)
$privacyLog = "check-ignore: $ignored`ntracked data/local/: $tracked`nresult: $privacyPass"
$privacyLog | Set-Content -LiteralPath (Join-Path $EvidenceDir 'private-draft-git.log') -Encoding utf8
$records.Add([ordered]@{ name = 'private-draft-git'; command = 'git check-ignore / git ls-files'; cwd = $repo;
    started_utc = (Get-Date).ToUniversalTime().ToString('o'); ended_utc = (Get-Date).ToUniversalTime().ToString('o');
    exit_code = $(if ($privacyPass) { 0 } else { 1 }); log = 'private-draft-git.log' })

$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'gate-results.json') -Encoding utf8
if ($records.Where({ $_.exit_code -ne 0 }).Count) { exit 1 }
