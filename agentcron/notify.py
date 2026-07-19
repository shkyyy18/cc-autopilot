from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.parse import urlsplit


def _send_webhook(url: str, payload: dict[str, Any], timeout: int = 10) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    timeout = min(60, max(1, int(timeout)))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "AgentCron/0.3"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def notify_failure(result: dict[str, Any], notify_config: dict[str, Any] | None,
                   output_text: str = "", prompt_text: str = "") -> None:
    if not notify_config:
        return

    if result.get("status") == "ok":
        return

    payload: dict[str, Any] = {
        "job": result.get("job"),
        "tool": result.get("tool"),
        "status": result["status"],
        "exit_code": result.get("exit_code"),
        "output_chars": result.get("output_chars"),
        "duration_seconds": result.get("duration_seconds"),
        "attempt": result.get("attempt"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
    }

    if notify_config.get("include_output"):
        payload["output"] = output_text

    if notify_config.get("include_prompt"):
        payload["prompt"] = prompt_text

    webhook_url = notify_config.get("webhook_url")
    if webhook_url:
        _send_webhook(str(webhook_url), payload,
                      timeout=int(notify_config.get("timeout", 10)))
