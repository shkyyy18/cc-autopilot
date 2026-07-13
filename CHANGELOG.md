# Changelog

## 0.3.0 - 2026-07-13

- Added dependency-free webhook notifications for failed, timed-out, and silent-fail jobs, contributed by @lesbass.
- Kept prompts and output private by default; explicit opt-in is required to include either.
- Restricted webhook targets to HTTP(S), bounded notification timeouts, and added security tests.
- Added notification documentation, release/community templates, and a visible first-contribution path.
- Added release and community calls to action to the project homepage.

## 0.2.0 - 2026-07-12

- Added the dependency-free `agentcron` CLI.
- Added Codex, Claude Code, Gemini CLI, and custom-command runners.
- Added retries, timeouts, silent-failure detection, structured UTF-8 logs, health status, and diagnostics.
- Added Windows Task Scheduler and POSIX cron installers.
- Added Windows/Linux CI and tests.

## 0.1.0 - 2026-07-08

- Initial Windows PowerShell reliability scripts.
