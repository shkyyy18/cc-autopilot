# Copyable operating recipes

These recipes are designed to answer one question quickly: can AgentCron make an unattended job observable and recoverable in your environment?

## Recipe 1: daily repository review on Windows

Use this when a coding agent should inspect one repository every weekday without leaving a visible console window running.

```powershell
python -m pip install "git+https://github.com/shkyyy18/cc-autopilot.git"
Set-Location C:\path\to\your\repository
agentcron init
agentcron add daily-review --tool codex --prompt prompts/daily-review.md --cron "0 18 * * 1-5"
```

Replace the generated prompt with a bounded task:

```markdown
# Daily repository review

Inspect the current working tree. Report failing tests, risky uncommitted changes, and the single highest-priority next action. Do not modify files.
```

Test before scheduling:

```powershell
agentcron run daily-review
agentcron status
agentcron install daily-review --dry-run
agentcron install daily-review
```

Success means the run is recorded as `ok`, the log is readable, and Task Scheduler contains the generated entry. Run `agentcron doctor` if the scheduled environment cannot find the agent CLI.

## Recipe 2: weekly changelog on Linux or macOS

```bash
python -m pip install "git+https://github.com/shkyyy18/cc-autopilot.git"
cd /path/to/repository
agentcron init
agentcron add weekly-changelog --tool codex --prompt prompts/changelog.md --cron "0 17 * * 5"
agentcron run weekly-changelog
agentcron install weekly-changelog --dry-run
agentcron install weekly-changelog
```

A useful prompt asks the agent to summarize merged commits since the previous tag and to write output only to stdout. AgentCron records that output in the local log; it does not publish or push changes by itself.

## Recipe 3: monitor health from another script

`status --json` emits a privacy-safe, versioned document and returns non-zero if any job is unhealthy.

```powershell
agentcron status --json | Set-Content agentcron-health.json -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Write-Error "At least one unattended job needs attention."
}
```

```bash
if ! agentcron status --json > agentcron-health.json; then
  echo "At least one unattended job needs attention" >&2
  exit 1
fi
```

The JSON excludes prompts, command output, command arguments, environment variables, and webhook credentials.

## Recipe 4: run a non-Codex command

Use an explicit command when the runner is not one of the built-in defaults:

```powershell
agentcron add docs-check `
  --tool custom `
  --command "python scripts/check_docs.py" `
  --prompt prompts/docs-check.md `
  --cron "0 9 * * 1"
```

Custom commands run with the current user's permissions. AgentCron is a watchdog, not a sandbox; keep the command narrow and apply least privilege.

## Ten-minute evaluation checklist

- [ ] `agentcron doctor` identifies the expected Python, config, runner, and scheduler.
- [ ] A manual run writes a readable local log.
- [ ] A deliberately tiny output is classified as `silent-fail`.
- [ ] `install --dry-run` shows the expected scheduler command.
- [ ] `status --json` can be consumed without exposing prompt or output content.
- [ ] Failure notifications, if enabled, contain metadata only by default.

If one of these steps fails, open a Discussion and include the operating system, runner version, `agentcron doctor` output, and a sanitized config.
