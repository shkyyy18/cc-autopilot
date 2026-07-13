import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentcron.config import command_for, get_job, load_config, save_config
from agentcron.notify import _send_webhook, notify_failure
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


class NotifyTests(unittest.TestCase):
    def test_noop_when_no_config(self):
        result = {"job": "test", "status": "failed", "exit_code": 1,
                  "output_chars": 0, "duration_seconds": 1.0,
                  "attempt": 1, "started_at": "", "finished_at": ""}
        notify_failure(result, None, output_text="output", prompt_text="prompt")
        # Should not raise; nothing to assert beyond no error.

    def test_noop_when_ok_status(self):
        result = {"job": "test", "status": "ok", "exit_code": 0,
                  "output_chars": 100, "duration_seconds": 1.0,
                  "attempt": 1, "started_at": "", "finished_at": ""}
        config = {"webhook_url": "http://example.com/hook"}
        notify_failure(result, config, output_text="output", prompt_text="prompt")
        # No webhook sent for ok status.

    @patch("agentcron.notify.urllib.request.urlopen")
    def test_webhook_sent_on_failure(self, mock_urlopen):
        result = {"job": "test", "tool": "codex", "status": "failed",
                  "exit_code": 1, "output_chars": 10, "duration_seconds": 2.5,
                  "attempt": 2, "started_at": "2026-01-01T00:00:00+00:00",
                  "finished_at": "2026-01-01T00:01:00+00:00"}
        config = {"webhook_url": "http://example.com/hook"}
        notify_failure(result, config, output_text="some output", prompt_text="some prompt")
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        payload = json.loads(call_args.data)
        self.assertEqual(payload["job"], "test")
        self.assertEqual(payload["status"], "failed")
        self.assertNotIn("output", payload)
        self.assertNotIn("prompt", payload)

    @patch("agentcron.notify.urllib.request.urlopen")
    def test_webhook_includes_output_when_configured(self, mock_urlopen):
        result = {"job": "test", "status": "timeout",
                  "exit_code": -1, "output_chars": 0, "duration_seconds": 30.0,
                  "attempt": 1, "started_at": "", "finished_at": ""}
        config = {"webhook_url": "http://example.com/hook", "include_output": True}
        notify_failure(result, config, output_text="agent output", prompt_text="")
        payload = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(payload["output"], "agent output")

    @patch("agentcron.notify.urllib.request.urlopen")
    def test_webhook_includes_prompt_when_configured(self, mock_urlopen):
        result = {"job": "test", "status": "silent-fail",
                  "exit_code": 0, "output_chars": 5, "duration_seconds": 1.0,
                  "attempt": 1, "started_at": "", "finished_at": ""}
        config = {"webhook_url": "http://example.com/hook", "include_prompt": True}
        notify_failure(result, config, output_text="", prompt_text="the prompt")
        payload = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(payload["prompt"], "the prompt")

    @patch("agentcron.notify.urllib.request.urlopen", side_effect=OSError("network down"))
    def test_notification_failure_does_not_raise(self, mock_urlopen):
        result = {"job": "test", "status": "failed",
                  "exit_code": 1, "output_chars": 0, "duration_seconds": 1.0,
                  "attempt": 1, "started_at": "", "finished_at": ""}
        config = {"webhook_url": "http://example.com/hook"}
        # Must not raise; notification failure is silently ignored.
        notify_failure(result, config, output_text="", prompt_text="")

    @patch("agentcron.notify.urllib.request.urlopen")
    def test_send_webhook_returns_true_on_success(self, mock_urlopen):
        self.assertTrue(_send_webhook("http://example.com/hook", {"key": "val"}))

    @patch("agentcron.notify.urllib.request.urlopen", side_effect=OSError("down"))
    def test_send_webhook_returns_false_on_error(self, mock_urlopen):
        self.assertFalse(_send_webhook("http://example.com/hook", {"key": "val"}))


class NotificationSecurityTests(unittest.TestCase):
    def test_non_http_webhook_is_rejected(self):
        self.assertFalse(_send_webhook("file:///tmp/leak", {"status": "failed"}))

    @patch("agentcron.notify.urllib.request.urlopen")
    def test_webhook_has_bounded_timeout_and_user_agent(self, mock_urlopen):
        self.assertTrue(_send_webhook("https://example.com/hook", {"status": "failed"}, timeout=999))
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 60)
        self.assertEqual(request.get_header("User-agent"), "AgentCron/0.3")


if __name__ == "__main__":
    unittest.main()
