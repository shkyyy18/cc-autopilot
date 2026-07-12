<div align="center">

# AgentCron

### Cron + watchdog for unattended AI coding agents

Run **Codex, Claude Code, Gemini CLI, or any command** on schedule. Detect silent failures, retry safely, kill hung process trees, and inspect every run from one CLI.

[![CI](https://github.com/shkyyy18/cc-autopilot/actions/workflows/ci.yml/badge.svg)](https://github.com/shkyyy18/cc-autopilot/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero dependencies](https://img.shields.io/badge/runtime%20dependencies-0-brightgreen)](pyproject.toml)

**Windows-first · Cross-platform · Local-only · Zero runtime dependencies**

</div>

![AgentCron terminal dashboard](docs/assets/agentcron-demo.svg)

```text
$ agentcron status
JOB                      TOOL       STATUS         SCHEDULE           LAST RUN
------------------------------------------------------------------------------------------
daily-review             codex      ok             0 18 * * 1-5       2026-07-12T18:02:41+08:00
weekly-changelog         claude     silent-fail    0 17 * * 5         2026-07-11T17:00:09+08:00
```

## Why AgentCron?

A scheduler can tell you that a process started. It cannot tell you whether your AI agent did useful work.

Unattended agent jobs fail differently from ordinary scripts:

- the CLI exits successfully but returns an empty or tiny response;
- a tool call hangs and leaves child processes behind;
- Windows Task Scheduler runs with a different PATH or encoding;
- a visible console window gets closed by accident;
- failures remain invisible until someone checks the result.

AgentCron is the small reliability layer between your scheduler and your coding agent.

## 30-second quick start

```powershell
# Install directly from GitHub
python -m pip install "git+https://github.com/shkyyy18/cc-autopilot.git"

# In any repository
agentcron init
agentcron add daily-review --tool codex --prompt prompts/daily-review.md --cron "0 18 * * 1-5"

# Edit the generated prompt, then test and schedule it
agentcron run daily-review
agentcron install daily-review
agentcron status
```

Use `--tool claude`, `--tool gemini`, or `--tool custom --command "your command"` for another runner.

## What you get

| Capability | Raw cron / Task Scheduler | AgentCron |
|---|:---:|:---:|
| Start a process on schedule | Yes | Yes |
| Codex, Claude, Gemini, custom commands | Manual | Built in |
| UTF-8 prompt and output handling | Manual | Yes |
| Timeout with process-tree cleanup | Manual | Yes |
| Detect exit-0-but-empty responses | No | Yes |
| Bounded automatic retries | Manual | Yes |
| Structured run logs | No | Yes |
| One health view for every job | No | Yes |
| Local-only; no hosted control plane | Yes | Yes |

## Configuration

`agentcron init` creates `agentcron.json`:

```json
{
  "version": 1,
  "defaults": {
    "timeout_minutes": 30,
    "min_output_chars": 80,
    "retries": 1
  },
  "jobs": [
    {
      "id": "daily-review",
      "tool": "codex",
      "prompt": "prompts/daily-review.md",
      "cwd": ".",
      "cron": "0 18 * * 1-5"
    }
  ]
}
```

Each job may override `timeout_minutes`, `min_output_chars`, `retries`, `log_dir`, `env`, or `command`.

### Runner defaults

| Tool | Default invocation |
|---|---|
| Codex | `codex exec -` |
| Claude Code | `claude -p --permission-mode bypassPermissions` |
| Gemini CLI | `gemini -p` |
| Custom | Your explicit `command` |

Commands are configurable because agent CLIs evolve. If your installed version uses different flags, set a command list in the job:

```json
{
  "id": "review",
  "tool": "custom",
  "command": ["my-agent", "run", "--stdin"],
  "prompt": "prompts/review.md",
  "cron": "0 9 * * *"
}
```

## CLI

```text
agentcron init [--force]                       Create a project config
agentcron add ID --tool TOOL --prompt FILE     Add a job and prompt template
agentcron run ID                               Run now with retries and logging
agentcron status [--json]                      Inspect latest health
agentcron doctor                               Check config, tools, and scheduler
agentcron install ID... [--all] [--dry-run]   Install scheduler entries
```

Use a config outside the current directory with `--config PATH` or `AGENTCRON_CONFIG`.

## Failure model

Every attempt ends in one explicit state:

- `ok` — exit code 0 and output meets the configured minimum;
- `silent-fail` — exit code 0 but output is suspiciously short;
- `failed` — non-zero exit code or launch failure;
- `timeout` — deadline exceeded; the process tree was terminated.

Logs are stored as `logs/<job>-<timestamp>.log`. Each contains readable agent output plus machine-readable JSON event lines. Prompts, logs, configs, and credentials are ignored by Git by default.

## Scheduling support

- **Windows 10/11:** installs daily and weekly fixed-time jobs into Task Scheduler via `schtasks`.
- **Linux/macOS:** installs standard five-field expressions into the user's `crontab`.
- Run `agentcron install --all --dry-run` before installation to inspect generated commands.

The original battle-tested PowerShell wrappers remain in [`src/`](src/) for users who need a script-only Windows setup. The new Python CLI is the recommended interface.

## Safety

AgentCron runs the configured command with your current user permissions. It does not sandbox the agent. Review prompts, use least-privilege agent settings, and never commit secrets or private logs. See [SECURITY.md](SECURITY.md).

## Development

```powershell
git clone https://github.com/shkyyy18/cc-autopilot.git
cd cc-autopilot
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [architecture](docs/architecture.md), [roadmap](ROADMAP.md), [changelog](CHANGELOG.md), and [contributing guide](CONTRIBUTING.md).

## Built from real failures

This project grew out of thousands of unattended Windows agent runs: silent 0-token responses, GBK/UTF-8 corruption, orphaned child processes, hidden Task Scheduler failures, and black console windows. The goal is simple: **scheduled agents should be boring to operate.**

## License

MIT
