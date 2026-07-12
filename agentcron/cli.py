from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULTS, find_config, get_job, load_config, save_config
from .runner import read_latest, run_job
from .scheduler import install_job


def cmd_init(args, path: Path) -> int:
    if path.exists() and not args.force:
        print(f"Config already exists: {path}")
        return 0
    save_config(path, DEFAULTS)
    (path.parent / "prompts").mkdir(exist_ok=True)
    (path.parent / "logs").mkdir(exist_ok=True)
    print(f"Created {path}")
    return 0


def cmd_add(args, path: Path) -> int:
    data = load_config(path)
    if any(job.get("id") == args.id for job in data["jobs"]):
        raise ValueError(f"Job already exists: {args.id}")
    job = {"id": args.id, "tool": args.tool, "prompt": args.prompt, "cron": args.cron, "cwd": args.cwd}
    if args.command:
        job["command"] = args.command
    data["jobs"].append(job)
    save_config(path, data)
    prompt = path.parent / args.prompt
    prompt.parent.mkdir(parents=True, exist_ok=True)
    if not prompt.exists():
        prompt.write_text(f"# {args.id}\n\nDescribe the task for your AI coding agent here.\n", encoding="utf-8")
    print(f"Added {args.id}; edit {prompt}")
    return 0


def cmd_run(args, path: Path) -> int:
    job = get_job(load_config(path), args.id)
    result, log = run_job(job, path.parent)
    print(f"[{result['status']}] {args.id} attempt={result['attempt']} exit={result['exit_code']} chars={result['output_chars']} duration={result['duration_seconds']}s")
    print(f"log: {log}")
    return 0 if result["status"] == "ok" else 1


def cmd_status(args, path: Path) -> int:
    data = load_config(path)
    rows = []
    for raw in data["jobs"]:
        job = get_job(data, raw["id"])
        latest = read_latest(path.parent, raw["id"], str(job.get("log_dir", "logs")))
        rows.append({"id": raw["id"], "tool": job.get("tool", "custom"), "cron": job.get("cron", job.get("cron_expr", "-")), "status": latest.get("status") if latest else "not-run", "last_run": latest.get("finished_at") if latest else None})
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print(f"{'JOB':24} {'TOOL':10} {'STATUS':14} {'SCHEDULE':18} LAST RUN")
        print("-" * 90)
        for row in rows:
            print(f"{row['id'][:24]:24} {str(row['tool'])[:10]:10} {row['status']:14} {str(row['cron'])[:18]:18} {row['last_run'] or '-'}")
    return 1 if any(row["status"] not in {"ok", "not-run"} for row in rows) else 0


def cmd_doctor(args, path: Path) -> int:
    checks = [("Python", True, sys.version.split()[0]), ("Config", path.exists(), str(path))]
    if path.exists():
        data = load_config(path)
        for tool in sorted({str(job.get("tool", "custom")) for job in data["jobs"]}):
            if tool != "custom":
                found = shutil.which(tool)
                checks.append((tool, bool(found), found or "not found in PATH"))
    scheduler = "schtasks" if os.name == "nt" else "crontab"
    checks.append(("Scheduler", bool(shutil.which(scheduler)), scheduler))
    failed = False
    for name, ok, detail in checks:
        print(f"{'OK' if ok else 'FAIL':4} {name:12} {detail}")
        failed |= not ok
    return 1 if failed else 0


def cmd_install(args, path: Path) -> int:
    data = load_config(path)
    ids = [job["id"] for job in data["jobs"]] if args.all else args.ids
    if not ids:
        raise ValueError("Pass job IDs or --all.")
    for job_id in ids:
        print(install_job(get_job(data, job_id), path, args.dry_run))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentcron", description="Reliable scheduling for unattended AI coding agents.")
    parser.add_argument("--config", help="Path to agentcron.json")
    parser.add_argument("--version", action="version", version=f"agentcron {__version__}")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    init = sub.add_parser("init", help="Create config and directories"); init.add_argument("--force", action="store_true")
    add = sub.add_parser("add", help="Add a job"); add.add_argument("id"); add.add_argument("--tool", choices=["codex", "claude", "gemini", "custom"], default="codex"); add.add_argument("--prompt", required=True); add.add_argument("--cron", required=True); add.add_argument("--cwd", default="."); add.add_argument("--command")
    run = sub.add_parser("run", help="Run one job now"); run.add_argument("id")
    status = sub.add_parser("status", help="Show latest job health"); status.add_argument("--json", action="store_true")
    sub.add_parser("doctor", help="Check configuration and installed tools")
    install = sub.add_parser("install", help="Install Task Scheduler or cron jobs"); install.add_argument("ids", nargs="*"); install.add_argument("--all", action="store_true"); install.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser(); args = parser.parse_args(); path = find_config(args.config)
    handlers = {"init": cmd_init, "add": cmd_add, "run": cmd_run, "status": cmd_status, "doctor": cmd_doctor, "install": cmd_install}
    try:
        code = handlers[args.subcommand](args, path)
    except (FileNotFoundError, KeyError, ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr); code = 2
    raise SystemExit(code)
