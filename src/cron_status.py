#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron_status -Health check for cc-autopilot scheduled tasks.

Data sources:
  ./jobs.json          Job definitions (id->name/cron_expr/timeout)
  ./logs/<id>-*.log    Execution logs written by run.ps1

Health states:
  [OK]         Completed with output >= 100 chars
  [silent-fail] Completed but output < 100 chars (likely 0-token response or CLI not in PATH)
  [timeout]    run.ps1 killed with taskkill after timeout
  [failed]     No END line found in log
  [not-run]    No log file exists

Usage:
  python cron_status.py              # Show latest run for each job
  python cron_status.py --rerun      # Re-trigger stale jobs via schtasks
  python cron_status.py --dry        # Dry-run rerun (list candidates without triggering)
"""
import json, re, sys, os, argparse, glob
from datetime import datetime, timedelta
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK workaround
except Exception:
    pass

# WHY these paths are relative:
# User should run this script from project root. Adjust if your layout differs.
JOBS_JSON = "jobs.json"
LOG_DIR = "logs"

END_RE = re.compile(r"\] END status=(\S+) exit=(-?\d+) out_chars=(\d+) dur_s=(\d+)")


def load_jobs():
    """Load job definitions from jobs.json."""
    if not os.path.exists(JOBS_JSON):
        return {}
    with open(JOBS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    # Support both list and dict formats
    jobs = data if isinstance(data, list) else list(data.values())
    return {j["id"]: j for j in jobs}


def scan_logs():
    """Scan logs/*.log for execution history. Returns {id: [{start, status, out_len}]}.

    Each log file = one cron execution (written by run.ps1). Filename: <id>-<timestamp>.log.
    Parses structured END line: `END status=<ok|timeout|silent-fail> exit=<code> out_chars=<N> dur_s=<N>`.
    status: completed / timeout / failed / skipped (anti-reentry, not counted as real run).
    """
    runs = defaultdict(list)
    if not os.path.isdir(LOG_DIR):
        return runs

    for fpath in glob.glob(os.path.join(LOG_DIR, "*.log")):
        m = re.match(r"^(.+)-(\d{8}-\d{6})\.log$", os.path.basename(fpath))
        if not m:
            continue
        jid, ts_s = m.group(1), m.group(2)
        try:
            start = datetime.strptime(ts_s, "%Y%m%d-%H%M%S")
        except ValueError:
            continue

        try:
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception:
            continue

        em = END_RE.search(content)
        if em:  # Structured END line
            st, out_chars = em.group(1), int(em.group(3))
            if st == "skip-duplicate":
                status, out_len = "skipped", 0
            elif st == "timeout":
                status, out_len = "timeout", out_chars
            else:  # ok or silent-fail
                status, out_len = "completed", out_chars
        elif "[TIMEOUT]" in content:
            status, out_len = "timeout", len(content)
        elif "] END" in content:
            status, out_len = "completed", len(content)
        else:
            status, out_len = "failed", len(content)

        runs[jid].append({"start": start, "status": status, "out_len": out_len})

    return runs


def latest_status():
    """Return latest run status for each job. Used by health check + rerun logic.

    Returns: [{id, name, cron_expr, label, last_run, days_since_ok}]
    label: OK / silent-fail / timeout / failed / not-run
    """
    jobs = load_jobs()
    runs = scan_logs()
    now = datetime.now()
    out = []

    for jid, job in jobs.items():
        name = (job.get("description", "") or "")[:22]
        cron = job.get("cron_expr", "")

        # Exclude skipped runs (anti-reentry, not real execution)
        jruns = [r for r in runs.get(jid, []) if r["status"] != "skipped"]
        if not jruns:
            out.append({"id": jid, "name": name, "cron_expr": cron,
                        "label": "not-run", "last_run": None, "days_since_ok": None})
            continue

        jruns.sort(key=lambda r: r["start"], reverse=True)
        r0 = jruns[0]

        # WHY <100 chars threshold:
        # Silent-fail = completed but output too short, likely 0-token response or CLI absent from PATH.
        if r0["status"] == "timeout":
            label = "timeout"
        elif r0["status"] == "failed":
            label = "failed"
        elif r0["status"] == "completed" and r0["out_len"] < 100:
            label = "silent-fail"
        elif r0["status"] == "completed":
            label = "OK"
        else:
            label = "unknown"

        last_ok = next((r for r in jruns if r["status"] == "completed" and r["out_len"] >= 100), None)
        days_since_ok = (now - last_ok["start"]).days if last_ok else None

        out.append({"id": jid, "name": name, "cron_expr": cron, "label": label,
                    "last_run": r0["start"], "days_since_ok": days_since_ok})

    return out


def _field_match(field, val):
    """Check if cron field matches value. Supports *, single value, comma list, range (1-5)."""
    if field == '*':
        return True
    for part in field.split(','):
        part = part.strip()
        if '-' in part:
            lo, hi = part.split('-', 1)
            try:
                if int(lo) <= val <= int(hi):
                    return True
            except ValueError:
                continue
        else:
            try:
                if int(part) == val:
                    return True
            except ValueError:
                continue
    return False


def expected_today(cron_expr, now=None):
    """Check if cron_expr is scheduled to run today (only checks month/day/dow, not hour/min)."""
    now = now or datetime.now()
    parts = (cron_expr or "").split()
    if len(parts) != 5:
        return False
    _min, _hr, dom, mon, dow = parts

    if not _field_match(mon, now.month):
        return False
    if not _field_match(dom, now.day):
        return False
    if dow == '*':
        return True

    # cron dow: 0/7=Sun, 1=Mon..6=Sat. python weekday(): Mon=0..Sun=6.
    py_dow = now.weekday()
    cron_dows = set()
    for part in dow.split(','):
        part = part.strip()
        if '-' in part:
            lo, hi = part.split('-', 1)
            for d in range(int(lo), int(hi) + 1):
                cron_dows.add(d)
        else:
            try:
                cron_dows.add(int(part))
            except ValueError:
                pass
    py_dows = {6 if d in (0, 7) else d - 1 for d in cron_dows}
    return py_dow in py_dows


def scheduled_passed(cron_expr, now=None):
    """Check if today's scheduled time has passed (hour/min). Prevents premature evening job triggers.

    Takes earliest value in hour field (range/list uses lower bound); '*' = already passed.
    Conservative: parse failure returns True (maintains old behavior).
    """
    now = now or datetime.now()
    parts = (cron_expr or "").split()
    if len(parts) != 5:
        return True
    minute_f, hour_f = parts[0], parts[1]
    if hour_f == '*':
        return True

    def _earliest(field):
        vals = []
        for part in field.split(','):
            part = part.strip().split('/')[0]
            if '-' in part:
                part = part.split('-')[0]
            try:
                vals.append(int(part))
            except ValueError:
                pass
        return min(vals) if vals else None

    hh = _earliest(hour_f)
    if hh is None:
        return True
    mm = _earliest(minute_f) if minute_f != '*' else 0
    if mm is None:
        mm = 0
    return (now.hour, now.minute) >= (hh, mm)


# Rerun config
RERUN_COOLDOWN_SEC = 1800  # 30 min cooldown between rerun attempts
RERUN_MAX_DAY = 4          # Max 4 rerun attempts per day
RERUN_STATE = "rerun_state.json"


def _load_rerun_state():
    """Load rerun state (cooldown + daily count)."""
    try:
        with open(RERUN_STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_rerun_state(s):
    """Save rerun state."""
    try:
        with open(RERUN_STATE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[rerun] Failed to save state (non-blocking): {e}", file=sys.stderr)


def rerun_stale(dry_run=False):
    """Re-trigger stale jobs (silent-fail/failed/timeout/not-run if expected today) via schtasks.

    WHY schtasks /Run:
    Triggers the scheduled task asynchronously. ok=True means "trigger succeeded", not "task completed".
    Actual completion is checked by next health check run.

    Anti-reentry: 30min cooldown + daily limit (4 attempts). State stored in rerun_state.json.

    Returns: ([{id, name, label, ok}], reason)
    """
    import subprocess
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')

    st = _load_rerun_state()
    st.setdefault(today, {"count": 0, "reran": []})

    if st[today]["count"] >= RERUN_MAX_DAY:
        return [], f"Daily limit {RERUN_MAX_DAY} reached"

    last_ts = st.get("last_rerun_ts")
    if last_ts:
        try:
            lt = datetime.fromisoformat(last_ts)
            if (now - lt).total_seconds() < RERUN_COOLDOWN_SEC:
                return [], f"Cooldown active (last run {int((now - lt).total_seconds() / 60)}min ago)"
        except ValueError:
            pass

    statuses = latest_status()
    candidates = []
    for s in statuses:
        if s["label"] == "OK":
            continue
        if not expected_today(s["cron_expr"], now):
            continue
        if not scheduled_passed(s["cron_expr"], now):
            continue  # Scheduled time not reached yet, don't treat as missed

        dso = s["days_since_ok"]
        if dso is None or dso >= 1:  # No OK run today
            candidates.append(s)

    if not candidates:
        return [], "No stale jobs"

    if dry_run:  # Dry-run: list candidates without triggering
        return [{"id": s["id"], "name": s["name"], "label": s["label"], "ok": "dry"}
                for s in candidates], "ok"

    ran = []
    for s in candidates:
        if st[today]["count"] >= RERUN_MAX_DAY:
            break
        rec = {"id": s["id"], "name": s["name"], "label": s["label"], "ok": None}
        try:
            # WHY schtasks /Run:
            # Async trigger. Task runs in background, exit 0 = trigger succeeded.
            r = subprocess.run(["schtasks", "/Run", "/TN", f"Cron-{s['id']}"],
                               capture_output=True, text=True, timeout=60)
            rec["ok"] = (r.returncode == 0)
            if r.returncode != 0:
                rec["err"] = (r.stderr or r.stdout)[:120]
        except Exception as e:
            rec["ok"] = False
            rec["err"] = str(e)[:120]
        ran.append(rec)
        st[today]["count"] += 1
        st[today]["reran"].append(s["id"])

    st["last_rerun_ts"] = now.isoformat()
    _save_rerun_state(st)
    return ran, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun", action="store_true", help="Re-trigger stale jobs (silent-fail/failed/not-run if scheduled today)")
    ap.add_argument("--dry", action="store_true", help="With --rerun: list candidates without triggering")
    args = ap.parse_args()

    if args.rerun or args.dry:
        ran, reason = rerun_stale(dry_run=args.dry)
        print(f"== cron health rerun ({reason}){' [DRY]' if args.dry else ''} ==")
        for r in ran:
            mark = "[OK]" if r["ok"] is True else ("[DRY]" if r["ok"] == "dry" else "[FAIL]")
            err = f" {r.get('err', '')}" if not r["ok"] and r["ok"] != "dry" else ""
            print(f"  {mark} {r['id']} {r['name']} [{r['label']}]{err}")
        return

    # Default: show latest status
    statuses = latest_status()
    print("== cc-autopilot cron health ==")
    print(f"Total jobs: {len(statuses)}")
    print()

    print(f"{'Status':<12} {'ID':<12} {'Name':<24} {'Cron':<16} {'Last Run':<18} {'Days Since OK':<15}")
    print("-" * 110)

    counts = defaultdict(int)
    for s in statuses:
        counts[s["label"]] += 1
        lr = s["last_run"].strftime('%Y-%m-%d %H:%M') if s["last_run"] else "-"
        dso = str(s["days_since_ok"]) if s["days_since_ok"] is not None else "-"
        print(f"{s['label']:<12} {s['id']:<12} {s['name']:<24} {s['cron_expr']:<16} {lr:<18} {dso:<15}")

    print()
    print(f"Summary: " + " | ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()

