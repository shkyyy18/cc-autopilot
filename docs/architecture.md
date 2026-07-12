# Architecture

```text
agentcron.json + prompt.md
          |
          v
   AgentCron CLI  <---- agentcron doctor / status
          |
          +---- runner adapter: Codex | Claude | Gemini | custom
          |
          +---- timeout + process-tree kill
          +---- silent-output detection
          +---- bounded retries
          |
          v
 structured UTF-8 run logs

Task Scheduler (Windows) / cron (Linux & macOS) invokes `agentcron run <job>`.
```

AgentCron deliberately stays outside the agent runtime. It does not replace Codex, Claude Code, or Gemini CLI; it makes unattended invocations observable and recoverable.
