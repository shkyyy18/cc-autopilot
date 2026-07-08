# cc-autopilot

> Stable cron scheduler for Claude Code / Cursor / Cline on Windows

## Why?

Running AI agents 24/7 on Windows hits 6 critical issues:

- ❌ **Silent failures**: Agent exits 0 but produces no output (0-token response, rate limit, CLI not in PATH)
- ❌ **GBK encoding hell**: PowerShell 5.1 mangles UTF-8 stdin/stdout on Chinese/non-ASCII text
- ❌ **Black window popups**: Task Scheduler shows visible cmd windows that users close, killing tasks
- ❌ **No health monitoring**: Missed/failed tasks go unnoticed until you manually check logs
- ❌ **No auto-recovery**: Failed tasks stay failed; you manually re-trigger them
- ❌ **UAC permission traps**: Interactive prompts block scheduled tasks

cc-autopilot solves them all.

## Features

✅ **Silent-fail detection**: Catches 0-token responses (`out_chars < 100`)  
✅ **GBK bypass**: Routes I/O through `cmd.exe` UTF-8 codepage, never touches PowerShell strings  
✅ **Black window elimination**: VBScript wrapper hides all console windows  
✅ **Health monitoring**: `cron_status.py` scans logs, reports OK/silent-fail/timeout/failed  
✅ **Auto-recovery**: `health_check.ps1` re-triggers stale jobs via `schtasks` (30min cooldown, 4/day limit)  
✅ **Structured logging**: Every run writes `START` + output + `END status=<ok|timeout|silent-fail> exit=<N> out_chars=<N> dur_s=<N>`

## Quick Start

```powershell
# 1. Clone
git clone https://github.com/shkyyy18/cc-autopilot
cd cc-autopilot

# 2. Create a prompt file
mkdir prompts
echo "Summarize today's git commits in this repository." > prompts\test.txt

# 3. Test run
mkdir logs
.\src\run.ps1 -Prompt "prompts\test.txt" -Output "logs\test-output.log"

# 4. Check output
cat logs\test-output.log
```

Expected output structure:
```
[2026-07-08 14:23:45] START timeout=30min
<claude's response here>
[2026-07-08 14:24:12] END status=ok exit=0 out_chars=1523 dur_s=27
```

## Scenario Templates

5 ready-to-use prompt templates in `examples/` — copy, schedule, done.

| Template | What it does | Schedule | File |
| ---------- | ------------- | ---------- | ------ |
| 📝 Daily summary | Summarize the latest commit's changes | Daily 09:00 | `examples/daily_summary.txt` |
| 🔍 Code review | Review latest commit: bugs, security, style | Weekdays 18:00 | `examples/code_review.txt` |
| 📋 Changelog | Auto changelog since last tag (Keep a Changelog) | Fridays 17:00 | `examples/changelog.txt` |
| 🐛 Error digest | Scan `logs/` for silent-fails / timeouts / failures | Daily 08:30 | `examples/error_digest.txt` |
| 📊 Weekly report | 200-word dev report for the team channel | Mondays 10:00 | `examples/weekly_report.txt` |

All 5 are registered in `examples/jobs.json`. Try one right now:

```powershell
.\src\run.ps1 -Prompt examples\code_review.txt -Output logs\code_review.log -TimeoutMin 20
```

To schedule a template as a Windows task, see the [Setup Guide](#setup-guide) below.

## How It Works

### Core Components

1. **`run.ps1`**: Cron wrapper with silent-fail detection
   - Routes stdin/stdout through temp files via `cmd.exe` (bypasses PowerShell GBK layer)
   - Detects silent failures: `exit 0` but `out_chars < 100`
   - Writes structured `END` line for health monitoring
   - Kills task tree on timeout (`taskkill /T /F`)

2. **`run_hidden.vbs`**: Black window eliminator
   - VBScript wrapper launches PowerShell with `windowStyle=0` (hidden)
   - Prevents user from closing visible cmd window and killing task

3. **`cron_status.py`**: Health monitoring
   - Scans `logs/*.log` for execution history
   - Reports: OK / silent-fail / timeout / failed / not-run
   - Powers auto-recovery logic

4. **`health_check.ps1`**: Auto-recovery
   - Runs after each cron cluster (schedule via `schtasks`)
   - Calls `cron_status.py --rerun` to re-trigger stale jobs
   - Cooldown: 30min between attempts; daily limit: 4 attempts

### Scheduling Flow

```
Task Scheduler (schtasks)
  └─> run_hidden.vbs <script.bat>
        └─> cmd /c <script.bat>  (hidden window)
              └─> powershell -File run.ps1 -Prompt prompts/job.txt -Output logs/job.log
                    └─> cmd /c chcp 65001 & claude -p < prompt > output
                          └─> (UTF-8 I/O, never touches PowerShell strings)

After cron cluster:
  └─> health_check.ps1
        └─> cron_status.py --rerun
              └─> schtasks /Run /TN Cron-<id>  (re-trigger stale jobs)
```

## Setup Guide

### 1. Install Dependencies

- **Windows 10/11** (PowerShell 5.1+ built-in)
- **Python 3.8+** (for `cron_status.py`)
- **Claude Code CLI** (or Cursor/Cline) in PATH

```powershell
# Verify claude is in PATH
claude --version
```

### 2. Create Job Definition

Create `jobs.json` in project root:

```json
[
  {
    "id": "daily_summary",
    "description": "Daily git commit summary",
    "cron_expr": "0 9 * * *",
    "timeout_mins": 30
  },
  {
    "id": "stock_monitor",
    "description": "A-share market monitor",
    "cron_expr": "30 9 * * 1-5",
    "timeout_mins": 45
  }
]
```

Cron format: `minute hour day month day_of_week`

### 3. Create Prompt Files

```powershell
mkdir prompts
echo "Summarize today's git commits." > prompts\daily_summary.txt
echo "Check A-share market status." > prompts\stock_monitor.txt
```

### 4. Schedule Tasks

```powershell
# Create wrapper batch file
echo @echo off > run_daily_summary.bat
echo powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\run.ps1" -Prompt "%~dp0prompts\daily_summary.txt" -Output "%~dp0logs\daily_summary.log" >> run_daily_summary.bat

# Schedule via schtasks
schtasks /Create /TN "Cron-daily_summary" /TR "wscript.exe //B \"%CD%\src\run_hidden.vbs\" \"%CD%\run_daily_summary.bat\"" /SC DAILY /ST 09:00 /RU SYSTEM

# Schedule health check (runs 30min after last cron cluster)
schtasks /Create /TN "CronHealthCheck" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"%CD%\src\health_check.ps1\"" /SC DAILY /ST 09:35
```

**Important**: Use `/RU SYSTEM` to avoid UAC prompts. For user context, use `/RU %USERNAME%`.

### 5. Test Run

```powershell
# Trigger manually
schtasks /Run /TN "Cron-daily_summary"

# Check status
python src\cron_status.py

# Check logs
cat logs\daily_summary-*.log
```

## Usage

### Check Cron Health

```powershell
python src\cron_status.py
```

Output:
```
== cc-autopilot cron health ==
Total jobs: 2

Status       ID           Name                     Cron             Last Run           Days Since OK
--------------------------------------------------------------------------------------------------------------
OK           daily_summary Daily git commit summar  0 9 * * *        2026-07-08 09:00   0
silent-fail  stock_monitor A-share market monitor   30 9 * * 1-5     2026-07-08 09:30   1

Summary: OK 1 | silent-fail 1
```

### Manual Rerun

```powershell
# Dry-run (list candidates without triggering)
python src\cron_status.py --rerun --dry

# Actually re-trigger stale jobs
python src\cron_status.py --rerun
```

### View Logs

```powershell
# Latest log for a job
cat logs\daily_summary-*.log | Select-Object -Last 1

# All logs for today
Get-ChildItem logs\*-$(Get-Date -Format yyyyMMdd)-*.log
```

## Troubleshooting

### Silent-fail: `out_chars < 100`

**Cause**: Claude CLI not in PATH, rate limit, or 0-token response.

**Fix**:
1. Check `claude --version` works in Task Scheduler context:
   ```powershell
   schtasks /Run /TN "Cron-daily_summary"
   cat logs\daily_summary-*.log
   ```
2. If "command not found", add Claude to System PATH (not User PATH)
3. Check API quota/rate limits

### Timeout after 30min

**Cause**: Prompt too complex or agent stuck in loop.

**Fix**:
1. Increase timeout: `.\src\run.ps1 -Prompt ... -TimeoutMin 60`
2. Simplify prompt (break into smaller tasks)
3. Check if agent is waiting for user input (use `--permission-mode bypassPermissions`)

### Task doesn't run (not-run)

**Cause**: Task Scheduler not triggered or task disabled.

**Fix**:
1. Check task exists: `schtasks /Query /TN "Cron-daily_summary"`
2. Check task status: Open Task Scheduler GUI, verify "Ready" not "Disabled"
3. Check trigger: Right-click task → Properties → Triggers
4. Manually trigger: `schtasks /Run /TN "Cron-daily_summary"`

### Black window still appears

**Cause**: Not using `run_hidden.vbs` wrapper.

**Fix**:
```powershell
# Wrong (shows window):
schtasks /Create /TR "powershell -File run.ps1 ..."

# Right (hidden):
schtasks /Create /TR "wscript //B run_hidden.vbs run_job.bat"
```

### GBK mojibake in logs

**Cause**: PowerShell string interpolation touching UTF-8 content.

**Fix**: Already handled by `run.ps1` (routes I/O through `cmd.exe` UTF-8 codepage). If you modified the script, ensure:
1. Never interpolate `$out` in double-quoted strings
2. Use `[System.IO.File]::AppendAllText()` with UTF-8 encoding
3. Set `$env:PYTHONUTF8 = '1'` before running Python scripts

## Advanced Configuration

### Custom Timeout per Job

Edit `run.ps1` call in batch file:
```batch
powershell -File src\run.ps1 -Prompt prompts\heavy_task.txt -Output logs\heavy_task.log -TimeoutMin 60
```

### Email Alerts on Failure

Modify `health_check.ps1` to send email when `$rerunOut -match '\[FAIL\]'`:
```powershell
if ($rerunOut -match '\[FAIL\]') {
    Send-MailMessage -To "admin@example.com" -From "cron@example.com" -Subject "Cron failure" -Body $rerunOut -SmtpServer "smtp.example.com"
}
```

### Multiple Cron Clusters

Schedule health check after each cluster:
```powershell
# Morning cluster: 09:00, 09:30
# Health check: 10:05
schtasks /Create /TN "CronHealthCheck-Morning" /TR "..." /SC DAILY /ST 10:05

# Evening cluster: 17:00, 18:00, 20:00
# Health check: 20:35
schtasks /Create /TN "CronHealthCheck-Evening" /TR "..." /SC DAILY /ST 20:35
```

## Project Status

🚧 **MVP** — Battle-tested in production (10,000+ runs), but APIs may change.

Feedback welcome! Open an issue on GitHub.

## Contributing

PRs welcome for:
- [ ] Linux/macOS support (replace `schtasks` with `cron`, `cmd.exe` with `bash`)
- [ ] Web dashboard for log viewing
- [ ] Configurable notification channels (Slack, Discord, etc.)
- [ ] Pre-built task registration script (`register_cron.ps1`)

## License

MIT

## Acknowledgments

Lessons learned from 6 months of 24/7 AI agent scheduling on Windows:
- GBK encoding bug root cause: 2026-07-05 (PowerShell string layer interpolation)
- Silent-fail detection: 2026-07-06 (0-token GLM responses went unnoticed for weeks)
- Black window fix: 2026-06-15 (users kept closing "stuck" windows, killing tasks)
- Auto-recovery: 2026-07-04 (manual re-triggering was 50% of maintenance time)

---

Built with lessons from real-world 24/7 AI agent operations. If it saved you time, star the repo ⭐
