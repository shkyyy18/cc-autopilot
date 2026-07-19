# Repository structure

```text
agentcron/                  Dependency-free Python CLI
  cli.py                    Commands: init/add/run/status/doctor/install
  config.py                 Config discovery, validation, runner defaults
  runner.py                 Execution, timeout, retry, logs, health parsing
  scheduler.py              Task Scheduler and crontab integration
examples/                   Ready-to-copy config and prompts
src/                        Deprecated health helpers for old script-only installs
tests/                      Unit and integration-style runner tests
docs/architecture.md        Design overview
.github/workflows/ci.yml    Python 3.9/3.12 on Windows and Linux
```

The Python CLI is the only supported runner interface. The remaining `src/` files are deprecated health helpers for existing installations and do not provide an agent runner.
