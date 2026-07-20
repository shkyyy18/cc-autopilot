from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any, Optional

DEFAULT_CONFIG = "agentcron.json"
DEFAULTS: dict[str, Any] = {
    "version": 1,
    "defaults": {"timeout_minutes": 30, "min_output_chars": 80, "retries": 1},
    "jobs": [],
}
TOOL_COMMANDS = {
    "codex": ["codex", "exec", "-"],
    "gemini": ["gemini", "-p"],
}


def find_config(explicit: Optional[str] = None) -> Path:
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


def _split_command(command: str) -> list[str]:
    if os.name == "nt":
        # shlex with posix=False keeps surrounding quotes in the tokens,
        # which subprocess then passes through literally (issue #12).
        # Strip one matched pair of quotes from each token.
        parts = shlex.split(command, posix=False)
        return [
            part[1:-1]
            if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'"
            else part
            for part in parts
        ]
    return shlex.split(command)


def command_for(job: dict[str, Any]) -> list[str]:
    command = job.get("command")
    if command:
        if isinstance(command, list):
            return [str(part) for part in command]
        return _split_command(str(command))
    tool = str(job.get("tool", "custom")).lower()
    if tool not in TOOL_COMMANDS:
        raise ValueError(f"Tool '{tool}' needs an explicit command.")
    return TOOL_COMMANDS[tool].copy()
