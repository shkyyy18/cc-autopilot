# cc-autopilot run wrapper
# Wraps Claude Code CLI with GBK encoding bypass, silent-fail detection, timeout handling.
#
# WHY THIS EXISTS:
# - PowerShell 5.1 on Windows uses GBK console encoding by default
# - Piping UTF-8 stdin/stdout through PS string layer causes mojibake on non-ASCII text
# - Claude CLI may exit 0 but produce no output (0-token response, rate limit, binary not in PATH)
# - We need structured logging with start/end markers for health monitoring
#
# SOLUTION:
# - Route I/O through temp files via cmd.exe (chcp 65001 = UTF-8 codepage)
# - Never let claude's stdin/stdout touch PowerShell's string layer
# - Detect silent failures: exit 0 but output < 100 chars
# - Write structured END line: status=<ok|timeout|silent-fail> exit=<code> out_chars=<N> dur_s=<N>
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1 -Prompt <file> -Output <file> [-TimeoutMin <N>]
#
param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [Parameter(Mandatory = $true)][string]$Output,
    [int]$TimeoutMin = 30
)
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'

# Resolve paths
$promptFile = [System.IO.Path]::GetFullPath($Prompt)
$outputFile = [System.IO.Path]::GetFullPath($Output)
$workDir = Get-Location

if (-not (Test-Path $promptFile)) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] ERROR prompt file not found: $promptFile" | Out-File -FilePath $outputFile -Encoding UTF8
    exit 1
}

$runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$outTmp = Join-Path $env:TEMP "cc-autopilot-$runStamp.out"

# WHY cmd.exe wrapper:
# chcp 65001 sets UTF-8 codepage; < feeds prompt file as stdin; > captures claude stdout verbatim.
# This bypasses PowerShell's GBK string layer entirely (lesson learned from 2026-07-05 migration).
$inner = "chcp 65001 > nul & claude -p --permission-mode bypassPermissions < `"$promptFile`" > `"$outTmp`" 2>&1"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.Arguments = "/c $inner"
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = $workDir

$startTime = Get-Date
$timedOut = $false
$proc = $null

try {
    $proc = [System.Diagnostics.Process]::Start($psi)
} catch {
    $errMsg = $_.Exception.Message
    "[$stamp] ERROR process-start-failed: $errMsg`r`n[$stamp] END status=error exit=-2 out_chars=0 dur_s=0" |
        Out-File -FilePath $outputFile -Encoding UTF8
    Remove-Item $outTmp -Force -ErrorAction SilentlyContinue
    exit 1
}

# WHY this null check:
# Process::Start returns $null when UseShellExecute=false and the binary is not found.
# Without this guard, WaitForExit() throws NullReferenceException, crashes the script,
# and the END line is never written — leaving a broken log (root cause: 2026-07-06 failure).
if ($null -eq $proc) {
    "[$stamp] ERROR Process::Start returned null (cmd.exe not found or access denied)`r`n[$stamp] END status=error exit=-2 out_chars=0 dur_s=0" |
        Out-File -FilePath $outputFile -Encoding UTF8
    Remove-Item $outTmp -Force -ErrorAction SilentlyContinue
    exit 1
}

# WHY taskkill /T:
# Kills the whole process tree (cmd + claude + any tool subprocesses).
# Without /T, child processes become orphans and hold file locks.
if (-not $proc.WaitForExit($TimeoutMin * 60 * 1000)) {
    & taskkill /PID $proc.Id /T /F 2>&1 | Out-Null
    $timedOut = $true
}

$out = if (Test-Path $outTmp) { Get-Content -Path $outTmp -Raw -Encoding UTF8 } else { '(no output file)' }
$tail = if ($timedOut) { "`r`n[TIMEOUT] killed after $TimeoutMin min" } else { '' }

# WHY <100 chars threshold:
# Silent-fail: claude exited 0 but produced <100 chars — likely 0-token response (rate limit,
# quota exhausted) or claude binary absent from PATH in the schtasks execution context.
# Real output is always >100 chars (even "I cannot do that" is ~50 chars + metadata).
$status = if ($timedOut) { 'timeout' } elseif ($out.Length -lt 100) { 'silent-fail' } else { 'ok' }
$exitCode = if ($timedOut) { -1 } else { $proc.ExitCode }
$durS = [int]((Get-Date) - $startTime).TotalSeconds

$warn = if ($status -eq 'silent-fail') {
    "`r`n[WARNING] out_chars=$($out.Length) lt 100: possible 0-token response or claude not in PATH"
} else { '' }

# WHY three separate writes:
# Never interpolate $out inside a PS double-quoted string; claude output may contain backtick
# sequences or $(...) that PS re-evaluates, silently crashing the log write (62-byte bug,
# root cause confirmed 2026-07-08).
"[$stamp] START timeout=${TimeoutMin}min" | Out-File -FilePath $outputFile -Encoding UTF8
[System.IO.File]::AppendAllText($outputFile, ($out + $tail + $warn + "`r`n"), [System.Text.Encoding]::UTF8)
"[$stamp] END status=$status exit=$exitCode out_chars=$($out.Length) dur_s=$durS" | Out-File -FilePath $outputFile -Append -Encoding UTF8

Remove-Item $outTmp -Force -ErrorAction SilentlyContinue
