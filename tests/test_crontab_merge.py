"""Fixture-backed regression tests for the Unix (Linux/macOS) crontab merge path.

These tests exercise ``agentcron.scheduler.install_job`` on the POSIX branch,
where AgentCron installs a job by rewriting the user's crontab: it drops any
line owned by the same job (identified by a ``# agentcron:<id>`` marker) and
appends a freshly rendered line, while leaving everything else untouched.

Every test mocks ``subprocess.run`` so the real user crontab is never read from
or written to. Existing-crontab inputs come from fixture files under
``tests/fixtures/crontab/``.
"""

import shlex
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentcron.scheduler import install_job

FIXTURES = Path(__file__).parent / "fixtures" / "crontab"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class CrontabRunRecorder:
    """Stand-in for ``subprocess.run`` covering the two crontab invocations.

    ``crontab -l`` returns the supplied fixture (or a non-zero exit to model an
    absent crontab); ``crontab -`` records the payload piped to stdin so tests
    can assert on the merged result. Any other command fails the test loudly.
    """

    def __init__(self, existing: str, list_returncode: int = 0):
        self._existing = existing
        self._list_returncode = list_returncode
        self.write_payloads: list[str] = []

    def __call__(self, cmd, *args, **kwargs):
        if cmd == ["crontab", "-l"]:
            return SimpleNamespace(returncode=self._list_returncode, stdout=self._existing, stderr="")
        if cmd == ["crontab", "-"]:
            self.write_payloads.append(kwargs["input"])
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess.run call: {cmd!r}")

    @property
    def payload(self) -> str:
        assert len(self.write_payloads) == 1, f"expected exactly one crontab write, got {len(self.write_payloads)}"
        return self.write_payloads[0]

    @property
    def payload_lines(self) -> list[str]:
        # Ignore the trailing blank line the installer always appends.
        return [ln for ln in self.payload.splitlines() if ln.strip()]


class CrontabMergeTests(unittest.TestCase):
    JOB = {"id": "daily-review", "cron": "0 18 * * 1-5"}
    CONFIG_PATH = Path("/home/user/agentcron.json")

    def install(self, recorder: CrontabRunRecorder, job=None, config_path=None) -> str:
        """Run install_job on the POSIX branch with subprocess.run mocked out."""
        job = job or self.JOB
        config_path = config_path or self.CONFIG_PATH
        # Force the crontab (non-Windows) branch regardless of host OS.
        with patch("agentcron.scheduler.os.name", "posix"), \
                patch("agentcron.scheduler.subprocess.run", recorder):
            return install_job(job, config_path)

    def expected_line(self, job=None, config_path=None) -> str:
        job = job or self.JOB
        config_path = config_path or self.CONFIG_PATH
        invocation = [sys.executable, "-m", "agentcron", "--config", str(config_path), "run", str(job["id"])]
        rendered = " ".join(shlex.quote(part) for part in invocation)
        return f"{job['cron']} {rendered} # agentcron:{job['id']}"

    # -- Acceptance: never touch the real crontab -------------------------------

    def test_only_expected_crontab_commands_are_invoked(self):
        # The recorder asserts on the exact argv of every subprocess.run call, so
        # any attempt to shell out to something other than `crontab -l` / `-` (or
        # to the real crontab) fails the test.
        seen: list = []

        recorder = CrontabRunRecorder(load_fixture("unrelated.crontab"))
        original_call = recorder.__call__

        def spy(cmd, *args, **kwargs):
            seen.append(cmd)
            return original_call(cmd, *args, **kwargs)

        with patch("agentcron.scheduler.os.name", "posix"), \
                patch("agentcron.scheduler.subprocess.run", spy):
            install_job(self.JOB, self.CONFIG_PATH)

        self.assertEqual(seen, [["crontab", "-l"], ["crontab", "-"]])
        self.assertEqual(len(recorder.write_payloads), 1)

    # -- Acceptance: preserve unrelated comments and cron entries ---------------

    def test_preserves_unrelated_comments_and_entries(self):
        existing = load_fixture("unrelated.crontab")
        recorder = CrontabRunRecorder(existing)
        self.install(recorder)
        payload = recorder.payload
        for line in existing.splitlines():
            if line.strip():
                self.assertIn(line, payload, f"unrelated line dropped: {line!r}")

    def test_appends_new_job_line_after_existing_content(self):
        recorder = CrontabRunRecorder(load_fixture("unrelated.crontab"))
        returned = self.install(recorder)
        expected = self.expected_line()
        self.assertEqual(returned, expected)
        self.assertEqual(recorder.payload_lines[-1], expected)

    # -- Acceptance: replace the marker for the same job exactly once -----------

    def test_replaces_existing_marker_for_same_job_exactly_once(self):
        recorder = CrontabRunRecorder(load_fixture("existing_marker.crontab"))
        self.install(recorder)
        marker = f"# agentcron:{self.JOB['id']}"
        marker_lines = [ln for ln in recorder.payload_lines if marker in ln]
        self.assertEqual(len(marker_lines), 1, "job marker must appear exactly once after merge")
        # The stale invocation is gone; the freshly rendered one replaces it.
        self.assertEqual(marker_lines[0], self.expected_line())
        self.assertNotIn("/old/python", recorder.payload)

    def test_replacing_is_idempotent_across_repeated_installs(self):
        # First install onto a crontab that already owns the marker...
        recorder1 = CrontabRunRecorder(load_fixture("existing_marker.crontab"))
        self.install(recorder1)
        merged_once = recorder1.payload
        # ...then reinstall using that output as the new existing crontab.
        recorder2 = CrontabRunRecorder(merged_once)
        self.install(recorder2)
        self.assertEqual(recorder2.payload, merged_once)

    # -- Acceptance: preserve entries for other AgentCron jobs ------------------

    def test_preserves_other_agentcron_job_entries(self):
        existing = load_fixture("other_jobs.crontab")
        recorder = CrontabRunRecorder(existing)
        self.install(recorder)
        payload = recorder.payload
        # Other AgentCron-owned markers survive untouched.
        self.assertIn("# agentcron:morning-brief", payload)
        self.assertIn("# agentcron:nightly-digest", payload)
        for line in existing.splitlines():
            if "agentcron:daily-review" in line:
                continue  # this one is the job under install; it gets replaced
            if line.strip():
                self.assertIn(line, payload, f"other job/entry dropped: {line!r}")
        # And exactly one line for the job we are installing.
        daily = [ln for ln in recorder.payload_lines if "# agentcron:daily-review" in ln]
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0], self.expected_line())

    # -- Acceptance: handle `crontab -l` returning no existing crontab ----------

    def test_handles_no_existing_crontab(self):
        # `crontab -l` exits non-zero with empty stdout when no crontab exists.
        recorder = CrontabRunRecorder("", list_returncode=1)
        returned = self.install(recorder)
        self.assertEqual(recorder.payload_lines, [self.expected_line()])
        self.assertEqual(returned, self.expected_line())

    def test_handles_empty_but_present_crontab(self):
        recorder = CrontabRunRecorder("", list_returncode=0)
        self.install(recorder)
        self.assertEqual(recorder.payload_lines, [self.expected_line()])

    # -- Acceptance: the generated invocation is shell-quoted -------------------

    def test_generated_invocation_is_shell_quoted(self):
        # A config path containing a space must be quoted so cron runs it as one
        # argument rather than splitting on whitespace.
        spaced = Path("/home/user/my configs/agentcron.json")
        recorder = CrontabRunRecorder("", list_returncode=1)
        returned = self.install(recorder, config_path=spaced)
        quoted = shlex.quote(str(spaced))
        self.assertIn(quoted, returned)
        self.assertIn(quoted, recorder.payload)
        # The raw, unquoted path must not leak into the crontab line.
        self.assertNotIn(" /home/user/my configs/agentcron.json ", returned)
        # Every component of the invocation round-trips through the shell lexer
        # back to the original argv.
        cron_fields, _, command = returned.partition(" # agentcron:")
        argv_text = cron_fields.split(" ", 5)[5]
        self.assertEqual(
            shlex.split(argv_text),
            [sys.executable, "-m", "agentcron", "--config", str(spaced), "run", "daily-review"],
        )

    # -- Dry run must not touch the crontab at all ------------------------------

    def test_dry_run_does_not_invoke_crontab(self):
        calls: list = []

        def guard(cmd, *args, **kwargs):
            calls.append(cmd)
            raise AssertionError("dry run must not shell out to crontab")

        with patch("agentcron.scheduler.os.name", "posix"), \
                patch("agentcron.scheduler.subprocess.run", guard):
            returned = install_job(self.JOB, self.CONFIG_PATH, dry_run=True)
        self.assertEqual(calls, [])
        self.assertEqual(returned, self.expected_line())

    # -- A failing `crontab -` surfaces as an error -----------------------------

    def test_write_failure_raises_runtime_error(self):
        def failing_run(cmd, *args, **kwargs):
            if cmd == ["crontab", "-l"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            if cmd == ["crontab", "-"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="crontab: cannot install")
            raise AssertionError(f"unexpected call: {cmd!r}")

        with patch("agentcron.scheduler.os.name", "posix"), \
                patch("agentcron.scheduler.subprocess.run", failing_run):
            with self.assertRaises(RuntimeError) as ctx:
                install_job(self.JOB, self.CONFIG_PATH)
        self.assertIn("crontab: cannot install", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
