from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = "agentcron.json"
DEFAULTS: dict[str, Any] = {
    "version": 1,
    "defaults": {"timeout_minutes": 30, "min_output_chars": 80, "retries": 1},
    "jobs": [],
}
TOOL_COMMANDS = {
    "codex": ["codex", "exec", "-"],
    "claude": ["claude", "-p", "--permission-mode", "bypassPermissions"],
    "gemini": ["gemini", "-p"],
}


def find_config(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("AGENTCRON_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        for name in (DEFAULT_CONFIG, "jobs.json"):
            candidate = directory / name
            if candidate.exists():
                return candidate
    return current / DEFAULT_CONFIG


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}. Run 'agentcron init'.")
    with path.open(encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        data = {"version": 1, "jobs": data}
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), (list, dict)):
        raise ValueError("Config must contain a 'jobs' list or object.")
    if isinstance(data["jobs"], dict):
        data["jobs"] = list(data["jobs"].values())
    data.setdefault("defaults", {})
    return data


def save_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def get_job(data: dict[str, Any], job_id: str) -> dict[str, Any]:
    for job in data["jobs"]:
        if job.get("id") == job_id:
            merged = dict(data.get("defaults", {}))
            merged.update(job)
            return merged
    raise KeyError(f"Unknown job: {job_id}")


def command_for(job: dict[str, Any]) -> list[str]:
    command = job.get("command")
    if command:
        if isinstance(command, list):
            return [str(part) for part in command]
        return shlex.split(str(command), posix=os.name != "nt")
    tool = str(job.get("tool", "custom")).lower()
    if tool not in TOOL_COMMANDS:
        raise ValueError(f"Tool '{tool}' needs an explicit command.")
    return TOOL_COMMANDS[tool].copy()
