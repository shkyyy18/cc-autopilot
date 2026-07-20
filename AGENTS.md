# AGENTS.md — cc-autopilot (AgentCron)

## 项目定位

无人值守 AI 编程 Agent（Codex、Gemini CLI 或任意自定义命令）的定时调度 + 看门狗可靠性层：按 cron 计划跑任务，检测"退出码 0 但输出为空"的静默失败，带超时杀进程树、有限重试、结构化日志。纯本地运行、零运行时依赖、Windows 一等公民。

## 技术栈

- Python ≥ 3.9，纯标准库，**零运行时依赖**
- setuptools 构建，包在仓库根 `agentcron/`（非 src 布局）
- 测试：unittest（不是 pytest）；**无任何 lint/format 配置**
- Windows 调度走 `schtasks`，Linux/macOS 走用户 crontab

## 常用命令

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
agentcron --version
```

Windows 下一键验证：`powershell -File verify.ps1`（跑测试 + status/install dry-run）。

## 本仓库 agent 的搜索范围与要求

- 只允许改动本仓库；`src/` 目录是**已弃用**的旧脚本（STRUCTURE.md 有说明），不要修改也不要当作现行接口参考。
- **Windows 兼容是硬约束**：任何涉及进程管理、调度、路径、编码的改动必须保持 Windows 可用（`taskkill /T /F`、`CREATE_NEW_PROCESS_GROUP`、`schtasks` 等平台分支在 `agentcron/runner.py`、`agentcron/scheduler.py`），同时不能破坏 POSIX 路径。
- 零运行时依赖是红线：不得向 pyproject 增加任何 runtime dependency。
- 该工具调度的是真实 AI agent 命令，改动 runner/scheduler 时禁止用未验证的"应该能跑"结论交付，必须实际跑 `python -m unittest discover -s tests -v`。

## 升级建议有效性 / 采纳规则（本仓定制）

1. 涉及进程杀树、超时、重试逻辑的改动建议：必须有对应 unittest 用例，且在 Windows 上实际验证过（或明确标注"仅 POSIX 验证"），否则无效。
2. 任何引入第三方运行时依赖的建议：默认**记录不做**，除非用户明确批准（零依赖是项目卖点）。
3. 调度集成（schtasks/crontab）变更：必须保持已有用户任务的向后兼容， Breaking change 需用户确认。
4. 文档/示例类改进（examples、docs、README）：有效即可排期做，成本低优先。

## 升级建议 backlog

（暂无。近期问题已修复；后续发现按全局规则 `docs/agent-collab-rules.md`（github-project-evaluation 仓）收录。）
