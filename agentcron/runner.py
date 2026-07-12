from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import command_for


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_job(job: dict[str, Any], root: Path) -> tuple[dict[str, Any], Path]:
    job_id = str(job["id"])
    command = command_for(job)
    cwd = (root / str(job.get("cwd", "."))).resolve()
    prompt_path = (root / str(job.get("prompt", f"prompts/{job_id}.md"))).resolve()
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    if not cwd.is_dir():
        raise FileNotFoundError(f"Working directory not found: {cwd}")
    timeout = max(1, int(job.get("timeout_minutes", 30))) * 60
    min_chars = max(0, int(job.get("min_output_chars", 80)))
    retries = max(0, int(job.get("retries", 1)))
    prompt = prompt_path.read_bytes()
    log_dir = root / str(job.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{job_id}-{stamp}.log"
    result: dict[str, Any] = {}
    for attempt in range(1, retries + 2):
        started = time.monotonic()
        started_at = _now()
        process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUTF8": "1", **{str(k): str(v) for k, v in job.get("env", {}).items()}},
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        timed_out = False
        try:
            output, _ = process.communicate(input=prompt, timeout=timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_tree(process)
            output, _ = process.communicate()
            exit_code = -1
        duration = round(time.monotonic() - started, 2)
        text = output.decode("utf-8", errors="replace")
        status = "timeout" if timed_out else "failed" if exit_code != 0 else "silent-fail" if len(text.strip()) < min_chars else "ok"
        result = {"job": job_id, "tool": job.get("tool", "custom"), "command": command, "status": status,
                  "exit_code": exit_code, "output_chars": len(text), "duration_seconds": duration,
                  "attempt": attempt, "started_at": started_at, "finished_at": _now()}
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("AGENTCRON " + json.dumps({**result, "event": "start"}, ensure_ascii=False) + "\n")
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.write("AGENTCRON " + json.dumps({**result, "event": "end"}, ensure_ascii=False) + "\n")
        if status == "ok" or attempt > retries:
            break
        time.sleep(min(5 * attempt, 15))
    return result, log_path


def read_latest(root: Path, job_id: str, log_dir: str = "logs") -> dict[str, Any] | None:
    directory = root / log_dir
    if not directory.exists():
        return None
    files = sorted(directory.glob(f"{job_id}-*.log"), reverse=True)
    for path in files:
        for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            if line.startswith("AGENTCRON "):
                try:
                    data = json.loads(line[len("AGENTCRON "):])
                except json.JSONDecodeError:
                    continue
                if data.get("event") == "end":
                    data["log"] = str(path)
                    return data
    return None
