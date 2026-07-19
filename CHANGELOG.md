# Changelog

## 0.3.1 - 2026-07-14

- Added a stable, versioned, privacy-safe JSON schema for `agentcron status --json`.
- Added JSON-output tests for valid job data, empty configurations, and secret-field exclusion.
- Removed the obsolete built-in runner and script wrapper that depended on unsafe broad-permission defaults; custom runners remain explicit.
- Repaired the copyable Windows example so it uses the supported Python CLI.

## 0.3.0 - 2026-07-13

- Added dependency-free webhook notifications for failed, timed-out, and silent-fail jobs, contributed by @lesbass.
- Kept prompts and output private by default; explicit opt-in is required to include either.
- Restricted webhook targets to HTTP(S), bounded notification timeouts, and added security tests.
- Added notification documentation, release/community templates, and a visible first-contribution path.
- Added release and community calls to action to the project homepage.

## 0.2.0 - 2026-07-12

- Added the dependency-free `agentcron` CLI.
- Added Codex, Gemini CLI, and custom-command runners.
- Added retries, timeouts, silent-failure detection, structured UTF-8 logs, health status, and diagnostics.
- Added Windows Task Scheduler and POSIX cron installers.
- Added Windows/Linux CI and tests.

## 0.1.0 - 2026-07-08

- Initial Windows PowerShell reliability scripts.
