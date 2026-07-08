# CronHealthCheck - OS-level cron health check + stale-job rerun.
# Scheduled by schtasks after each cron cluster to monitor and recover failed tasks.
#
# WHY THIS EXISTS:
# - Detects silent failures (0-token responses, CLI not in PATH)
# - Auto-recovers stale jobs (silent-fail/timeout/missed) via schtasks /Run
# - Prevents duplicate runs via cooldown (30min) + daily limit (4 attempts)
#
# Usage: Schedule via schtasks to run after each cron cluster
# Example: schtasks /Create /TN "CronHealthCheck" /TR "powershell -File health_check.ps1" /SC DAILY /ST 09:05
#
# Pure ASCII (PS 5.1 GBK safety).
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'

# Decode python's UTF-8 stdout correctly (PS5.1 default = GBK console codepage -> mojibake in log)
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

$log = Join-Path $projectRoot 'health_check.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $log -Value "`n[$stamp] CronHealthCheck start" -Encoding UTF8

# Rerun today's stale cron jobs (silent-fail/timeout/missed)
$statusScript = Join-Path $scriptDir 'cron_status.py'
$rerunOut = python $statusScript --rerun 2>&1 | Out-String
Add-Content -Path $log -Value $rerunOut -Encoding UTF8

# Optional: Toast notification if any rerun trigger failed (requires pc_notify.ps1)
# Uncomment if you have a desktop notification script
<#
if ($rerunOut -match '\[FAIL\]') {
    $notifyScript = Join-Path $scriptDir 'pc_notify.ps1'
    if (Test-Path $notifyScript) {
        $title = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('cron rerun alert'))
        $body = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('CronHealthCheck: some stale jobs failed to re-trigger. See health_check.log'))
        Start-Process powershell -ArgumentList "-NoProfile","-WindowStyle","Hidden","-File",$notifyScript,"-TitleB64",$title,"-BodyB64",$body -WindowStyle Hidden
    }
}
#>

Add-Content -Path $log -Value "[$stamp] CronHealthCheck done" -Encoding UTF8
