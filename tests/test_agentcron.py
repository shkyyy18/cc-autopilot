import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentcron.config import command_for, get_job, load_config, save_config
from agentcron.runner import read_latest, run_job
from agentcron.scheduler import _windows_schedule


class ConfigTests(unittest.TestCase):
    def test_round_trip_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agentcron.json"
            save_config(path, {"defaults": {"retries": 2}, "jobs": [{"id": "x", "tool": "codex"}]})
            job = get_job(load_config(path), "x")
            self.assertEqual(job["retries"], 2)
            self.assertEqual(command_for(job), ["codex", "exec", "-"])

    def test_custom_command(self):
        self.assertEqual(command_for({"tool": "custom", "command": ["python", "task.py"]}), ["python", "task.py"])


class RunnerTests(unittest.TestCase):
    def test_ok_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompt.md").write_text("hello", encoding="utf-8")
            script = "import sys; sys.stdin.read(); print('x' * 100)"
            job = {"id": "demo", "tool": "custom", "command": [sys.executable, "-c", script], "prompt": "prompt.md", "min_output_chars": 10, "retries": 0}
            result, log = run_job(job, root)
            self.assertEqual(result["status"], "ok")
            self.assertTrue(log.exists())
            self.assertEqual(read_latest(root, "demo")["status"], "ok")

    def test_silent_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "p").write_text("hello", encoding="utf-8")
            result, _ = run_job({"id": "short", "tool": "custom", "command": [sys.executable, "-c", "print('no')"], "prompt": "p", "min_output_chars": 20, "retries": 0}, root)
            self.assertEqual(result["status"], "silent-fail")


class SchedulerTests(unittest.TestCase):
    def test_weekdays(self):
        self.assertEqual(_windows_schedule("0 18 * * 1-5"), ["/SC", "WEEKLY", "/D", "MON,TUE,WED,THU,FRI", "/ST", "18:00"])


if __name__ == "__main__":
    unittest.main()
