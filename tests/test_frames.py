import unittest

from gadgetbridge_rpi_link import (
    F_BYTE_MARKER,
    L_BYTE_MARKER,
    FrameDecoder,
    FrameEncoder,
)
from gadgetbridge_rpi_link.constants import DEFAULT_TX_CHUNK_SIZE


class FrameTest(unittest.TestCase):
    def test_decoder_reassembles_partial_frame(self):
        decoder = FrameDecoder()

        self.assertEqual(decoder.feed(bytes([F_BYTE_MARKER]) + b"GB({"), [])
        frames = decoder.feed(b'"t":"gps"})' + bytes([L_BYTE_MARKER]))

        self.assertEqual(frames, ['\x10GB({"t":"gps"})\n'])

    def test_decoder_keeps_newlines_inside_gb_frame(self):
        decoder = FrameDecoder()
        frame = (
            bytes([F_BYTE_MARKER])
            + b'GB({"t":"http","resp":"first line\nbody})\nmore"})'
            + bytes([L_BYTE_MARKER])
        )
        split = frame.index(b"body") + 2

        self.assertEqual(decoder.feed(frame[:split]), [])
        chunks = decoder.feed(frame[split:])

        self.assertEqual(len(chunks), 1)
        self.assertIn("first line\nbody})\nmore", chunks[0])

    def test_decoder_uses_write_chunk_boundary_for_completion(self):
        decoder = FrameDecoder()
        frame = (
            bytes([F_BYTE_MARKER])
            + b'GB({"t":"http","resp":"first\nsecond"})'
            + bytes([L_BYTE_MARKER])
        )
        split = frame.index(b"\nsecond") + 3

        self.assertEqual(decoder.feed(frame[:split]), [])
        self.assertTrue(decoder.has_pending_frame)
        self.assertEqual(decoder.feed(frame[split:]), [frame.decode("utf-8")])

    def test_decoder_discards_previous_incomplete_frame_on_new_start_marker(self):
        decoder = FrameDecoder()

        decoder.feed(bytes([F_BYTE_MARKER]) + b"GB({broken")
        frames = decoder.feed(
            bytes([F_BYTE_MARKER]) + b"GB({})" + bytes([L_BYTE_MARKER])
        )

        self.assertEqual(decoder.discarded_frames, 1)
        self.assertEqual(frames, ["\x10GB({})\n"])

    def test_decoder_suspends_http_frame_while_startup_frame_interleaves(self):
        decoder = FrameDecoder()
        http_start = bytes([F_BYTE_MARKER]) + b'GB({"t":"http","id":"1","resp":"abc'
        set_time = (
            bytes([F_BYTE_MARKER])
            + b"setTime(1782181599);E.setTimeZone(9.0);"
            + bytes([L_BYTE_MARKER])
        )
        http_tail = b'def"})' + bytes([L_BYTE_MARKER])

        self.assertEqual(decoder.feed(http_start), [])
        self.assertEqual(decoder.feed(set_time), [set_time.decode("utf-8")])

        frames = decoder.feed(http_tail)

        self.assertEqual(decoder.discarded_frames, 0)
        self.assertEqual(frames, [(http_start + http_tail).decode("utf-8")])

    def test_decoder_suspends_http_frame_while_multiple_frames_interleave(self):
        decoder = FrameDecoder()
        http_start = bytes([F_BYTE_MARKER]) + b'GB({"t":"http","id":"1","resp":"abc'
        set_time = (
            bytes([F_BYTE_MARKER])
            + b"setTime(1782181599);E.setTimeZone(9.0);"
            + bytes([L_BYTE_MARKER])
        )
        gps_active = (
            bytes([F_BYTE_MARKER])
            + b'GB({"t":"is_gps_active"})'
            + bytes([L_BYTE_MARKER])
        )
        http_tail = b'def"})' + bytes([L_BYTE_MARKER])

        self.assertEqual(decoder.feed(http_start), [])
        self.assertEqual(decoder.feed(set_time), [set_time.decode("utf-8")])
        self.assertEqual(decoder.feed(gps_active), [gps_active.decode("utf-8")])

        frames = decoder.feed(http_tail)

        self.assertEqual(decoder.discarded_frames, 0)
        self.assertEqual(frames, [(http_start + http_tail).decode("utf-8")])

    def test_encoder_preserves_legacy_line_suffix_and_chunks(self):
        encoder = FrameEncoder(chunk_size=20)

        self.assertEqual(
            encoder.encode("A" * 25),
            [
                b"A" * 20,
                b"AAAAA\\n\n",
            ],
        )

    def test_encoder_default_uses_high_mtu_chunk_size(self):
        encoder = FrameEncoder()

        self.assertEqual(DEFAULT_TX_CHUNK_SIZE, 128)
        self.assertEqual(encoder.encode("A" * 129), [b"A" * 128, b"A\\n\n"])


if __name__ == "__main__":
    unittest.main()
