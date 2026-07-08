# Project Structure

```
cc-autopilot/
├── src/                      # Core scripts
│   ├── run.ps1              # Main cron wrapper (GBK bypass, silent-fail detection)
│   ├── run_hidden.vbs       # Black window eliminator (VBScript wrapper)
│   ├── cron_status.py       # Health monitoring (scan logs, report status)
│   └── health_check.ps1     # Auto-recovery (re-trigger stale jobs)
│
├── examples/                 # Example configurations
│   ├── jobs.json            # Job definitions template
│   ├── daily_summary.txt    # Example prompt file
│   └── run_daily_summary.bat # Example batch wrapper
│
├── logs/                     # Execution logs (created on first run)
│   └── <id>-<timestamp>.log # One log per execution
│
├── prompts/                  # Prompt files (user-created)
│   └── *.txt                # One prompt file per job
│
├── verify.ps1               # Installation verification script
├── README.md                # Main documentation
├── LICENSE                  # MIT License
└── .gitignore              # Git ignore patterns

# User-created files (not in git):
├── jobs.json                # Your job definitions (copy from examples/)
├── rerun_state.json         # Auto-recovery state (created by cron_status.py)
└── health_check.log         # Health check execution log
```

## File Relationships

### Execution Flow

```
User creates:
  prompts/daily_summary.txt   (What to run)
  jobs.json                   (When to run)
  run_daily_summary.bat       (How to run)

Task Scheduler triggers:
  wscript run_hidden.vbs run_daily_summary.bat
    └─> run.ps1 -Prompt prompts/daily_summary.txt -Output logs/daily_summary-20260708-090000.log
          └─> claude -p < prompt > output
                └─> Writes structured log with START/END markers

After cron cluster:
  health_check.ps1
    └─> cron_status.py --rerun
          └─> Scans logs/, detects stale jobs, re-triggers via schtasks
```

### Data Flow

```
INPUT:  prompts/*.txt         (User-written prompts)
CONFIG: jobs.json             (Job definitions: id, cron_expr, timeout)
OUTPUT: logs/<id>-<ts>.log    (Structured logs with status/exit/out_chars/dur_s)
STATE:  rerun_state.json      (Auto-recovery state: cooldown, daily count)
HEALTH: health_check.log      (Health check execution history)
```

## Key Design Decisions

### Why cmd.exe wrapper?

PowerShell 5.1 uses GBK console encoding by default. Piping UTF-8 stdin/stdout through PowerShell's string layer causes mojibake on Chinese/non-ASCII text. Solution: route I/O through temp files via `cmd.exe` with `chcp 65001` (UTF-8 codepage).

### Why VBScript wrapper?

Task Scheduler with InteractiveToken shows visible cmd windows. Users close them, killing tasks. VBScript runs under `wscript.exe` (GUI subsystem, no console), launches cmd with `windowStyle=0` (hidden).

### Why <100 chars threshold?

Silent failures (0-token response, rate limit, CLI not in PATH) exit 0 but produce no output. Real output is always >100 chars (even "I cannot do that" is ~50 chars + metadata). Threshold catches these failures.

### Why structured END line?

Health monitoring needs machine-readable status. Format: `END status=<ok|timeout|silent-fail> exit=<N> out_chars=<N> dur_s=<N>`. Parsed by `cron_status.py` for health reports and auto-recovery.

### Why 30min cooldown + 4/day limit?

Prevents infinite rerun loops when root cause is persistent (API quota exhausted, network down). Cooldown gives transient issues time to resolve; daily limit prevents runaway behavior.

## Extending the System

### Adding a new job

1. Create prompt file: `prompts/my_job.txt`
2. Add to `jobs.json`:
   ```json
   {
     "id": "my_job",
     "description": "My custom job",
     "cron_expr": "0 12 * * *",
     "timeout_mins": 30
   }
   ```
3. Create batch wrapper: `run_my_job.bat`
4. Schedule: `schtasks /Create /TN "Cron-my_job" /TR "wscript run_hidden.vbs run_my_job.bat" ...`

### Custom notification on failure

Edit `health_check.ps1`, add email/webhook logic when `$rerunOut -match '\[FAIL\]'`.

### Web dashboard

Parse `logs/*.log` + `jobs.json`, render HTML table with:
- Job name, last run time, status (color-coded)
- out_chars, duration, error message
- Historical trend (last 7 days)

See `cron_status.py` `latest_status()` for data structure.

## Maintenance

### Log rotation

Logs grow indefinitely. Add cleanup job:

```powershell
# Keep last 30 days only
Get-ChildItem logs\*.log | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
```

Schedule daily at midnight.

### State cleanup

`rerun_state.json` keeps all historical days. Clean up old entries:

```python
# Keep last 7 days only
import json
from datetime import datetime, timedelta

with open('rerun_state.json', 'r+') as f:
    state = json.load(f)
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    state = {k: v for k, v in state.items() if k >= cutoff or k == 'last_rerun_ts'}
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
```

### Monitoring

Check health check log for repeated failures:

```powershell
cat health_check.log | Select-String '\[FAIL\]'
```

If same job fails >3 times, investigate root cause (not just re-trigger).
