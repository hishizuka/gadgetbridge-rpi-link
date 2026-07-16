import subprocess
import unittest
from datetime import datetime, timezone

from examples.set_system_time import (
    SetTimeHandler,
    apply_system_time,
    build_parser,
    build_set_time_command,
)
from gadgetbridge_rpi_link import SetTimeEvent, UnknownRawEvent


class SetSystemTimeExampleTest(unittest.TestCase):
    def setUp(self):
        self.event = SetTimeEvent(
            timestamp_sec=3600,
            timezone_offset_hours=9.0,
            utc_time=datetime(1970, 1, 1, 1, tzinfo=timezone.utc),
        )

    def test_build_set_time_command_uses_utc_without_a_shell(self):
        self.assertEqual(
            build_set_time_command(self.event),
            [
                "sudo",
                "-n",
                "date",
                "-u",
                "--set",
                "1970-01-01T01:00:00+00:00",
            ],
        )

    def test_apply_system_time_checks_the_command_result(self):
        calls = []

        def runner(command, *, check):
            calls.append((command, check))

        apply_system_time(self.event, runner=runner)

        self.assertEqual(calls, [(build_set_time_command(self.event), True)])

    def test_handler_is_dry_run_by_default(self):
        applied = []
        handler = SetTimeHandler(apply=False, setter=applied.append)

        handler(self.event)

        self.assertEqual(applied, [])

    def test_handler_applies_only_set_time_events(self):
        applied = []
        handler = SetTimeHandler(apply=True, setter=applied.append)

        handler(UnknownRawEvent(raw_text="unknown"))
        handler(self.event)

        self.assertEqual(applied, [self.event])

    def test_handler_logs_command_failures(self):
        def failing_setter(_event):
            raise subprocess.CalledProcessError(1, ["date"])

        handler = SetTimeHandler(apply=True, setter=failing_setter)

        with self.assertLogs("gadgetbridge-set-system-time", level="ERROR"):
            handler(self.event)

    def test_cli_requires_explicit_apply_flag(self):
        self.assertFalse(build_parser().parse_args([]).apply)
        self.assertTrue(build_parser().parse_args(["--apply"]).apply)


if __name__ == "__main__":
    unittest.main()
