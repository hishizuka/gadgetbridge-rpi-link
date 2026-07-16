import asyncio
import base64
import json
import tempfile
import unittest
from pathlib import Path

from gadgetbridge_rpi_link import (
    DEFAULT_HTTP_TEXT_URL,
    F_BYTE_MARKER,
    L_BYTE_MARKER,
    GadgetbridgeSession,
)
from gadgetbridge_rpi_link.http import (
    encode_http_download_payload,
    should_write_download_as_binary,
)
from gadgetbridge_rpi_link.outgoing import (
    build_gps_power_message,
    build_intent_message,
)


def rx(inner: str) -> bytes:
    return f"{chr(F_BYTE_MARKER)}{inner}{chr(L_BYTE_MARKER)}".encode("utf-8")


class OutgoingTest(unittest.TestCase):
    def test_gps_power_messages_match_existing_payload_shape(self):
        self.assertEqual(build_gps_power_message(True), '{t:"gps_power", status:true}')
        self.assertEqual(
            build_gps_power_message(False), '{t:"gps_power", status:false}'
        )

    def test_voice_command_intent_can_be_built_with_generic_intent_builder(self):
        self.assertEqual(
            build_intent_message(
                "android.intent.action.VOICE_COMMAND",
                flags=["FLAG_ACTIVITY_NEW_TASK"],
            ),
            (
                '{"t":"intent","target":"activity",'
                '"action":"android.intent.action.VOICE_COMMAND",'
                '"flags":["FLAG_ACTIVITY_NEW_TASK"]}'
            ),
        )

    def test_http_download_payload_can_force_text_or_binary(self):
        self.assertEqual(
            encode_http_download_payload("caf\xe9", binary=True),
            b"caf\xe9",
        )
        self.assertEqual(
            encode_http_download_payload("caf\xe9", binary=False),
            "caf\xe9".encode("utf-8"),
        )
        self.assertEqual(
            encode_http_download_payload("こんにちは", binary=True),
            "こんにちは".encode("utf-8"),
        )
        self.assertEqual(
            encode_http_download_payload("caf\xe9", binary=False, path="data.bin"),
            "caf\xe9".encode("utf-8"),
        )

    def test_http_download_payload_infers_binary_from_suffix(self):
        payload = "\x00\x01ABC"

        self.assertTrue(should_write_download_as_binary(path="data.bin"))
        self.assertTrue(should_write_download_as_binary(path="data.txt", binary=True))
        self.assertFalse(should_write_download_as_binary(path="data.bin", binary=False))
        self.assertEqual(
            encode_http_download_payload(payload, path="data.bin"),
            b"\x00\x01ABC",
        )
        self.assertEqual(
            encode_http_download_payload(payload, path="data.txt"),
            payload.encode("utf-8"),
        )


class SessionHttpTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sent_messages = []
        self.session = GadgetbridgeSession(sender=self.sent_messages.append)

    async def _wait_for_sent_messages(self, count=1):
        deadline = asyncio.get_running_loop().time() + 1.0
        while asyncio.get_running_loop().time() < deadline:
            if len(self.sent_messages) >= count:
                return
            await asyncio.sleep(0.001)
        self.fail("Timed out waiting for sent messages")

    async def test_request_http_sends_headers_and_body(self):
        task = asyncio.create_task(
            self.session.request_http(
                "https://example.com/data",
                method="POST",
                headers={"Content-Type": "application/json"},
                body={"hello": "world"},
                timeout=1,
            )
        )
        await self._wait_for_sent_messages()
        sent = json.loads(self.sent_messages[0])

        self.assertEqual(sent["t"], "http")
        self.assertEqual(sent["method"], "POST")
        self.assertEqual(sent["body"], '{"hello":"world"}')

        self.session.feed_rx(rx(f'GB({{"t":"http","id":"{sent["id"]}","resp":"ok"}})'))
        response = await task
        self.assertEqual(response["resp"], "ok")
        self.assertEqual(set(response), {"t", "id", "resp"})

    async def test_request_http_matches_parallel_responses_by_id(self):
        task_one = asyncio.create_task(
            self.session.request_http("https://example.com/one", timeout=1)
        )
        task_two = asyncio.create_task(
            self.session.request_http("https://example.com/two", timeout=1)
        )
        await self._wait_for_sent_messages(count=2)
        sent_one, sent_two = [json.loads(message) for message in self.sent_messages]

        self.session.feed_rx(
            rx(f'GB({{"t":"http","id":"{sent_two["id"]}","resp":"second"}})')
        )
        self.session.feed_rx(
            rx(f'GB({{"t":"http","id":"{sent_one["id"]}","resp":"first"}})')
        )

        self.assertEqual((await task_one)["resp"], "first")
        self.assertEqual((await task_two)["resp"], "second")

    async def test_request_http_json_decodes_atob_response(self):
        task = asyncio.create_task(
            self.session.request_http_json("https://example.com/data", timeout=1)
        )
        await self._wait_for_sent_messages()
        sent = json.loads(self.sent_messages[0])
        encoded = base64.b64encode(b'{"ok":true}').decode("ascii")

        self.session.feed_rx(
            rx(f'GB({{t:"http",id:"{sent["id"]}",resp:atob("{encoded}")}})')
        )

        self.assertEqual(await task, {"ok": True})

    async def test_request_http_cleans_pending_when_send_fails(self):
        def failing_sender(_message):
            raise RuntimeError("send failed")

        session = GadgetbridgeSession(sender=failing_sender)

        with self.assertRaisesRegex(RuntimeError, "send failed"):
            await session.request_http("https://example.com/data", timeout=1)

        self.assertEqual(session._http_pending, {})

    async def test_sent_messages_are_disabled_by_default(self):
        session = GadgetbridgeSession()

        session.send_message("one")

        self.assertEqual(session.sent_messages, [])

    async def test_sent_messages_keeps_only_configured_recent_messages(self):
        session = GadgetbridgeSession(sent_message_limit=2)

        session.send_message("one")
        session.send_message("two")
        session.send_message("three")

        self.assertEqual(session.sent_messages, ["two", "three"])

    async def test_sent_messages_can_be_unbounded(self):
        session = GadgetbridgeSession(sent_message_limit=None)

        session.send_message("one")
        session.send_message("two")
        session.send_message("three")

        self.assertEqual(session.sent_messages, ["one", "two", "three"])

    async def test_sent_message_limit_rejects_negative_values(self):
        with self.assertRaises(ValueError):
            GadgetbridgeSession(sent_message_limit=-1)

    async def test_download_http_file_writes_text_response(self):
        async def fake_request_http(*_args, **_kwargs):
            return {"resp": "Hello World!\n"}

        self.session.request_http = fake_request_http

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "hello.txt"
            status = await self.session.download_http_file(
                "https://example.com/hello.txt",
                save_path,
                binary=False,
            )
            self.assertEqual(status, 200)
            self.assertEqual(save_path.read_text(encoding="utf-8"), "Hello World!\n")

    async def test_download_http_text_sample_uses_official_sample_url(self):
        calls = []

        async def fake_download_http_file(url, save_path, **kwargs):
            calls.append((url, kwargs))
            Path(save_path).write_text("Hello World!\n", encoding="utf-8")
            return 200

        self.session.download_http_file = fake_download_http_file

        with tempfile.TemporaryDirectory() as temp_dir:
            result = await self.session.download_http_text_sample(
                output_dir=temp_dir,
                product="Unit",
            )
            self.assertEqual(
                Path(result).read_text(encoding="utf-8"),
                "Hello World!\n",
            )

        self.assertEqual(calls[0][0], DEFAULT_HTTP_TEXT_URL)
        self.assertEqual(calls[0][1]["headers"], {"User-Agent": "Unit"})
        self.assertEqual(calls[0][1]["timeout"], 30)

    async def test_download_http_files_returns_minus_one_for_failed_download(self):
        async def fake_download_http_file(url, save_path, **_kwargs):
            if url.endswith("bad"):
                raise RuntimeError("boom")
            return 200

        self.session.download_http_file = fake_download_http_file

        results = await self.session.download_http_files(
            ["https://example.com/good", "https://example.com/bad"],
            ["good.txt", "bad.txt"],
        )

        self.assertEqual(results, [200, -1])

    async def test_download_http_files_rejects_length_mismatch(self):
        with self.assertRaises(ValueError):
            await self.session.download_http_files(
                ["https://example.com/one", "https://example.com/two"],
                ["one.txt"],
            )


if __name__ == "__main__":
    unittest.main()
