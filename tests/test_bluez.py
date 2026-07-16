import contextlib
import io
import unittest
from unittest.mock import patch

from gadgetbridge_rpi_link import FrameEncoder
from gadgetbridge_rpi_link.bluez import (
    BluezGadgetbridgeUartServer,
    BluezUnavailableError,
    HAS_BLUEZ,
    is_bluez_supported,
    require_bluez,
)
from gadgetbridge_rpi_link.cli import bluez_host
from gadgetbridge_rpi_link.cli.bluez_host import build_parser


class FakeService:
    def __init__(self):
        self.chunks = []

    def notify(self, message):
        self.notified = message

    def notify_chunk(self, chunk):
        self.chunks.append(chunk)


class BluezCapabilityTest(unittest.IsolatedAsyncioTestCase):
    def test_is_bluez_supported_matches_import_flag(self):
        self.assertEqual(is_bluez_supported(), HAS_BLUEZ)

    def test_bluez_cli_parser_is_available_even_when_dependency_is_missing(self):
        help_text = build_parser().format_help()

        self.assertIn("Gadgetbridge BlueZ UART host probe", help_text)
        self.assertIn("--auto-gps", help_text)

    def test_bluez_cli_reports_missing_dependency_without_traceback(self):
        async def failing_main():
            raise BluezUnavailableError(
                "install 'bluez-peripheral>=0.2.0a3,<0.3'"
            )

        stderr = io.StringIO()
        with patch.object(bluez_host, "main", failing_main):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    bluez_host.cli()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            stderr.getvalue(),
            "error: install 'bluez-peripheral>=0.2.0a3,<0.3'\n",
        )

    def test_require_bluez_raises_typed_error_when_unavailable(self):
        if HAS_BLUEZ:
            self.skipTest("BlueZ dependencies are installed")

        with self.assertRaises(BluezUnavailableError):
            require_bluez()
        with self.assertRaises(BluezUnavailableError):
            BluezGadgetbridgeUartServer("test")

    async def test_send_async_chunks_with_legacy_payload_suffix(self):
        server = object.__new__(BluezGadgetbridgeUartServer)
        server.encoder = FrameEncoder(chunk_size=3)
        server.service = FakeService()
        server._tx_lock = None

        await server.send_async("abcdef")

        self.assertEqual(server.service.chunks, [b"abc", b"def", b"\\n\n"])

    def test_server_accepts_legacy_tx_chunk_size_override(self):
        if not HAS_BLUEZ:
            self.skipTest("BlueZ dependencies are not installed")

        server = BluezGadgetbridgeUartServer("test", tx_chunk_size=20)

        self.assertEqual(server.encoder.chunk_size, 20)


if __name__ == "__main__":
    unittest.main()
