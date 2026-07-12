from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


def _windows_schedule(cron: str) -> list[str]:
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError("Expected standard five-field cron expression.")
    minute, hour, day, month, weekday = parts
    if day != "*" or month != "*" or not minute.isdigit() or not hour.isdigit():
        raise ValueError("Windows installer supports daily/weekly fixed-time schedules.")
    time_value = f"{int(hour):02d}:{int(minute):02d}"
    if weekday == "*":
        return ["/SC", "DAILY", "/ST", time_value]
    mapping = {"0": "SUN", "1": "MON", "2": "TUE", "3": "WED", "4": "THU", "5": "FRI", "6": "SAT", "7": "SUN"}
    days: list[str] = []
    for token in weekday.split(","):
        if "-" in token:
            start, end = map(int, token.split("-", 1))
            days.extend(mapping[str(i)] for i in range(start, end + 1))
        else:
            days.append(mapping.get(token.upper(), token.upper()))
    return ["/SC", "WEEKLY", "/D", ",".join(days), "/ST", time_value]


def install_job(job: dict[str, Any], config_path: Path, dry_run: bool = False) -> str:
    job_id = str(job["id"])
    cron = str(job.get("cron", job.get("cron_expr", "")))
    if not cron:
        raise ValueError(f"Job '{job_id}' has no cron schedule.")
    invocation = [sys.executable, "-m", "agentcron", "--config", str(config_path), "run", job_id]
    if os.name == "nt":
        command = ["schtasks", "/Create", "/F", "/TN", f"AgentCron-{job_id}", "/TR", subprocess.list2cmdline(invocation), *_windows_schedule(cron)]
        rendered = subprocess.list2cmdline(command)
        if not dry_run:
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError((completed.stderr or completed.stdout).strip())
        return rendered
    marker = f"# agentcron:{job_id}"
    rendered_invocation = " ".join(shlex.quote(part) for part in invocation)
    line = f"{cron} {rendered_invocation} {marker}"
    if not dry_run:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = current.stdout if current.returncode == 0 else ""
        kept = [item for item in existing.splitlines() if marker not in item]
        payload = "\n".join([*kept, line, ""])
        completed = subprocess.run(["crontab", "-"], input=payload, text=True, capture_output=True)
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout).strip())
    return line
