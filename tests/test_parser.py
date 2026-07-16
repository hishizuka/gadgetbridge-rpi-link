import base64
import json
import unittest

from gadgetbridge_rpi_link import (
    F_BYTE_MARKER,
    L_BYTE_MARKER,
    FindDeviceEvent,
    GpsActiveQueryEvent,
    GpsFixEvent,
    HttpResponseEvent,
    NavigationEvent,
    NotificationAddEvent,
    NotificationRemoveEvent,
    NotificationUpdateEvent,
    ParseErrorEvent,
    SetTimeEvent,
    UnknownGBEvent,
)
from gadgetbridge_rpi_link.parser import GadgetbridgeParser
from gadgetbridge_rpi_link.navigation import build_navigation_event


def raw(inner: str) -> str:
    return f"{chr(F_BYTE_MARKER)}{inner}{chr(L_BYTE_MARKER)}"


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = GadgetbridgeParser()

    def parse_one(self, inner: str):
        events = self.parser.parse_text(raw(inner))
        self.assertEqual(len(events), 1)
        return events[0]

    def test_notify_message_with_unicode_payload(self):
        event = self.parse_one(
            'GB({"t":"notify","id":1758500272,"src":"ChatApp",'
            '"title":"Unicode title","subject":"",'
            '"body":"こんにちは\\nテストメッセージ",'
            '"sender":"","reply":true})'
        )

        self.assertIsInstance(event, NotificationAddEvent)
        self.assertEqual(event.title, "Unicode title")
        self.assertEqual(
            event.body,
            "こんにちは\nテストメッセージ",
        )
        self.assertTrue(event.reply)

    def test_notify_update_and_remove_messages(self):
        update = self.parse_one(
            'GB({t:"notify~",id:10,src:"Mail",title:"Subject",body:"Updated"})'
        )
        remove = self.parse_one('GB({t:"notify-",id:10})')

        self.assertIsInstance(update, NotificationUpdateEvent)
        self.assertEqual(update.id, 10)
        self.assertEqual(update.body, "Updated")
        self.assertIsInstance(remove, NotificationRemoveEvent)
        self.assertEqual(remove.id, 10)

    def test_find_and_gps_active_messages(self):
        find = self.parse_one('GB({t:"find",n:true})')
        gps_active = self.parse_one('GB({t:"is_gps_active"})')

        self.assertIsInstance(find, FindDeviceEvent)
        self.assertTrue(find.active)
        self.assertIsInstance(gps_active, GpsActiveQueryEvent)

    def test_gps_message_normalizes_speed_hdop_and_mode(self):
        event = self.parse_one(
            'GB({t:"gps",lat:35.681236,lon:139.767125,alt:12.5,'
            "speed:36,course:180,hdop:12,satellites:7,time:1000})"
        )

        self.assertIsInstance(event, GpsFixEvent)
        self.assertEqual(event.lat, 35.681236)
        self.assertEqual(event.lon, 139.767125)
        self.assertEqual(event.speed_mps, 10.0)
        self.assertEqual(event.hdop, 2.0)
        self.assertEqual(event.fix_mode, 3)
        self.assertEqual(event.satellites, 7)
        self.assertEqual(event.timestamp_utc.isoformat(), "1970-01-01T00:00:01+00:00")

    def test_set_time_updates_parser_offset(self):
        event = self.parse_one("setTime(3600);E.setTimeZone(1);")

        self.assertIsInstance(event, SetTimeEvent)
        self.assertEqual(event.timestamp_sec, 3600)
        self.assertEqual(event.timezone_offset_hours, 1.0)
        self.assertEqual(event.utc_time.isoformat(), "1970-01-01T01:00:00+00:00")

    def test_gps_timestamp_ignores_gadgetbridge_timezone_offset(self):
        self.parse_one("setTime(3600);E.setTimeZone(9);")
        event = self.parse_one('GB({t:"gps",time:1000})')

        self.assertIsInstance(event, GpsFixEvent)
        self.assertEqual(event.timestamp_utc.isoformat(), "1970-01-01T00:00:01+00:00")

    def test_http_response_decodes_atob_text(self):
        encoded_text = base64.b64encode(b'{"ok":true}').decode("ascii")
        text_event = self.parse_one(
            f'GB({{t:"http",id:"1",resp:atob("{encoded_text}")}})'
        )

        self.assertIsInstance(text_event, HttpResponseEvent)
        self.assertEqual(text_event.response, '{"ok":true}')

    def test_http_response_preserves_string_content_when_quoting_keys(self):
        response = 'body,{bad:1},atob("nope")'
        event = self.parse_one(
            f'GB({{"t":"http","id":"text","resp":{json.dumps(response)}}})'
        )

        self.assertIsInstance(event, HttpResponseEvent)
        self.assertEqual(event.request_id, "text")
        self.assertEqual(event.response, response)

    def test_navigation_message_derives_turn_and_distance(self):
        event = self.parse_one(
            'GB({t:"nav",instr:"Turn slightly left",'
            'distance:"100m",action:"left_slight"})'
        )

        self.assertIsInstance(event, NavigationEvent)
        self.assertEqual(event.turn_type, "Slight Left")
        self.assertEqual(event.distance_m, 100.0)
        self.assertFalse(event.should_clear)

    def test_navigation_invalid_distance_requests_clear(self):
        event = self.parse_one('GB({t:"nav",distance:"soon",action:"left"})')

        self.assertIsInstance(event, NavigationEvent)
        self.assertTrue(event.should_clear)

    def test_build_navigation_event_from_raw_payload(self):
        event = build_navigation_event(
            {"distance": "0.2km", "action": "right", "instr": "Turn right"},
            raw_text="raw",
        )

        self.assertIsInstance(event, NavigationEvent)
        self.assertEqual(event.turn_type, "Right")
        self.assertEqual(event.distance_m, 200.0)
        self.assertEqual(event.instruction, "Turn right")
        self.assertEqual(event.raw_text, "raw")

    def test_unknown_message_is_preserved(self):
        event = self.parse_one('GB({t:"weather",temp:20})')

        self.assertIsInstance(event, UnknownGBEvent)
        self.assertEqual(event.message_type, "weather")
        self.assertEqual(event.raw["temp"], 20)

    def test_documented_text_samples_parse_without_error(self):
        samples = [
            ('GB({"t":"info", "msg":"OK"})', "info", "msg", "OK"),
            ('GB({"t":"status", "bat":"23"})', "status", "bat", "23"),
            (
                'GB({"t":"http", url:"https://pur3.co.uk/hello.txt"})',
                "http",
                "url",
                "https://pur3.co.uk/hello.txt",
            ),
        ]

        for message, message_type, key, value in samples:
            with self.subTest(message=message):
                event = self.parse_one(message)
                self.assertIsInstance(event, UnknownGBEvent)
                self.assertEqual(event.message_type, message_type)
                self.assertEqual(event.raw[key], value)

    def test_parse_failure_becomes_event(self):
        event = self.parse_one("GB({t:")

        self.assertIsInstance(event, ParseErrorEvent)


if __name__ == "__main__":
    unittest.main()
