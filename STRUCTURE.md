# Repository structure

```text
agentcron/                  Dependency-free Python CLI
  cli.py                    Commands: init/add/run/status/doctor/install
  config.py                 Config discovery, validation, runner defaults
  runner.py                 Execution, timeout, retry, logs, health parsing
  scheduler.py              Task Scheduler and crontab integration
examples/                   Ready-to-copy config and prompts
src/                        Legacy Windows PowerShell implementation
tests/                      Unit and integration-style runner tests
docs/architecture.md        Design overview
.github/workflows/ci.yml    Python 3.9/3.12 on Windows and Linux
```

The Python CLI is the supported primary interface. The `src/` scripts are retained for existing script-only installations.
