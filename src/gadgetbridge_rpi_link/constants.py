"""Constants used by the Gadgetbridge UART protocol."""

F_BYTE_MARKER = 0x10
L_BYTE_MARKER = 0x0A

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# BangleJS/Gadgetbridge raises its return UART chunk size after it receives a
# host chunk larger than 20 bytes. Keep the default near the high-MTU payload
# size so large HTTP responses are not forced back to 20-byte writes.
DEFAULT_TX_CHUNK_SIZE = 128
HDOP_UEAE_FACTOR = 6.0

NMEA_MODE_NO_FIX = 1
NMEA_MODE_2D = 2
NMEA_MODE_3D = 3
HDOP_CUTOFF_MODERATE = 3.0
HDOP_CUTOFF_FAIR = 5.0

GADGETBRIDGE_ACTION_TURN_TYPE = {
    "continue": "Straight",
    "left": "Left",
    "left_slight": "Slight Left",
    "left_sharp": "Sharp Left",
    "right": "Right",
    "right_slight": "Slight Right",
    "right_sharp": "Sharp Right",
    "keep_left": "Slight Left",
    "keep_right": "Slight Right",
    "uturn_left": "Uturn Left",
    "uturn_right": "Uturn Right",
    "roundabout_right": "Right",
    "roundabout_left": "Left",
    "roundabout_uturn": "Uturn Right",
    "finish": "Finish",
}

GADGETBRIDGE_HIDDEN_ACTIONS = {
    "",
    "offroute",
    "roundabout_straight",
}

GADGETBRIDGE_DISTANCE_FACTORS = {
    "m": 1.0,
    "km": 1000.0,
    "ft": 0.3048,
    "yd": 0.9144,
    "mi": 1609.344,
}
