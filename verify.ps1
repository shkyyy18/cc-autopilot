# Quick verification script for cc-autopilot
# Run this after installation to verify everything works

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== cc-autopilot Verification ===" -ForegroundColor Cyan
Write-Host ""

# Check 1: Python available
Write-Host "[1/5] Checking Python..." -NoNewline
try {
    $pyVer = python --version 2>&1
    Write-Host " OK ($pyVer)" -ForegroundColor Green
} catch {
    Write-Host " FAIL (Python not found in PATH)" -ForegroundColor Red
    exit 1
}

# Check 2: Claude CLI available
Write-Host "[2/5] Checking Claude CLI..." -NoNewline
try {
    $claudeVer = claude --version 2>&1
    Write-Host " OK ($claudeVer)" -ForegroundColor Green
} catch {
    Write-Host " FAIL (Claude CLI not found in PATH)" -ForegroundColor Red
    Write-Host "  Install from: https://docs.anthropic.com/claude/docs/claude-cli" -ForegroundColor Yellow
    exit 1
}

# Check 3: Core files exist
Write-Host "[3/5] Checking core files..." -NoNewline
$coreFiles = @(
    "src\run.ps1",
    "src\run_hidden.vbs",
    "src\cron_status.py",
    "src\health_check.ps1"
)
$missing = @()
foreach ($f in $coreFiles) {
    $fullPath = Join-Path $scriptDir $f
    if (-not (Test-Path $fullPath)) {
        $missing += $f
    }
}
if ($missing.Count -gt 0) {
    Write-Host " FAIL (Missing: $($missing -join ', '))" -ForegroundColor Red
    exit 1
} else {
    Write-Host " OK (4 files)" -ForegroundColor Green
}

# Check 4: Create test directories
Write-Host "[4/5] Creating test directories..." -NoNewline
$dirs = @("logs", "prompts")
foreach ($d in $dirs) {
    $fullPath = Join-Path $scriptDir $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-Host " OK" -ForegroundColor Green

# Check 5: Test run
Write-Host "[5/5] Running test..." -NoNewline
$testPrompt = Join-Path $scriptDir "prompts\test.txt"
$testLog = Join-Path $scriptDir "logs\test.log"
"Say hello and confirm you received this message." | Out-File -FilePath $testPrompt -Encoding UTF8

$runScript = Join-Path $scriptDir "src\run.ps1"
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runScript -Prompt $testPrompt -Output $testLog -TimeoutMin 2
    if (Test-Path $testLog) {
        $logContent = Get-Content -Path $testLog -Raw
        if ($logContent -match "END status=(\S+)") {
            $status = $matches[1]
            if ($status -eq "ok") {
                Write-Host " OK (status=$status)" -ForegroundColor Green
            } else {
                Write-Host " WARNING (status=$status)" -ForegroundColor Yellow
                Write-Host "  Check $testLog for details" -ForegroundColor Yellow
            }
        } else {
            Write-Host " FAIL (No END line in log)" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host " FAIL (No log file created)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== All checks passed! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Copy examples\jobs.json to project root and customize"
Write-Host "2. Create prompt files in prompts\ directory"
Write-Host "3. Schedule tasks with: schtasks /Create ..."
Write-Host "4. Run health check: python src\cron_status.py"
Write-Host ""
Write-Host "See README.md for detailed setup guide."
