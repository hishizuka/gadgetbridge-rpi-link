# gadgetbridge-rpi-link

English | [日本語](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README_ja.md) | [简体中文](https://github.com/hishizuka/gadgetbridge-rpi-link/blob/main/README_zh-CN.md)

Use an Android phone as a wireless companion for a Raspberry Pi: notifications,
phone GPS, and simple internet access over a single battery-friendly BLE
connection.

Canonical repository: <https://github.com/hishizuka/gadgetbridge-rpi-link>

## What Is This?

[Gadgetbridge](https://gadgetbridge.org/) is an open-source Android app that
connects smartwatches and fitness trackers to a phone without vendor cloud
accounts. Its BLE UART protocol for [Bangle.js](https://banglejs.com/) can
forward notifications, phone GPS positions, and small HTTP requests.

This package connects a Raspberry Pi or another small Linux device to
Gadgetbridge as a Bangle.js watch and exposes received messages as Python
events. The host application implements the UI, data storage, and other
application-specific behavior. See the
[Espruino Gadgetbridge documentation](https://www.espruino.com/Gadgetbridge)
for protocol details.

## What You Can Do

- **Show Android notifications on a Raspberry Pi display.** Gadgetbridge
  forwards notification additions, updates, and removals from Android. This
  library converts them into notification events that are easy to use from
  Python and render in a host UI. For CJK or other multibyte text, a small
  Gadgetbridge source change is currently required; see
  [Text Encoding](#text-encoding).

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-notification-to-raspberry-pi.svg" alt="Android notification forwarded to a Raspberry Pi display" width="560">

- **Use the Android phone as the Raspberry Pi's GPS receiver.** With
  Gadgetbridge phone GPS enabled, Raspberry Pi applications receive location
  updates from the phone without a separate GPS module.

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-gps-to-raspberry-pi.svg" alt="Phone GPS positions forwarded to a Raspberry Pi" width="560">

- **Use the phone as a time source when the Raspberry Pi has no RTC.** The
  library converts time information received from Gadgetbridge into a Python
  event that a host application can apply to the system clock. The time
  arrives only after the BLE connection and Gadgetbridge synchronization, not
  immediately at boot, so timestamps created before then may be incorrect.

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-time-to-raspberry-pi.svg" alt="Phone time forwarded to a Raspberry Pi after Gadgetbridge connects" width="560">

- **Read Google Maps turn-by-turn navigation.** Gadgetbridge converts Android
  navigation notifications and sends them to the Raspberry Pi. Through this
  library, Python applications can read turn directions, instructions, and
  remaining distances.

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/android-navigation-to-raspberry-pi.svg" alt="Google Maps navigation forwarded to a Raspberry Pi" width="560">

- **Make simple HTTP requests through the phone.** Fetch text or JSON
  resources, or send data to an external API with `method="POST"` and a
  request body, using the Android app as the network bridge. Binary data
  is not supported by the current Gadgetbridge implementation; see
  [HTTP Download Behavior](#http-download-behavior).

  <img src="https://raw.githubusercontent.com/hishizuka/gadgetbridge-rpi-link/main/docs/assets/raspberry-pi-http-via-phone.svg" alt="Raspberry Pi fetching text or JSON through the phone" width="560">

- **Trigger Android intents from the Raspberry Pi side.** This can start the
  phone's voice assistant or another Android action that the user
  intentionally allows.

Important limitations: HTTP is intended for text and small transfers and
normally needs a Bangle.js-flavor Gadgetbridge build; CJK and other multibyte
UART text needs a custom UTF-8 Gadgetbridge build. See
[Android App Setup Details](#android-app-setup-details).

**Why BLE?**

Everything above travels over one BLE connection. The Raspberry Pi does not
need Wi-Fi or Bluetooth tethering, which matters for battery-powered, all-day
setups such as bike computers or wearable displays.

| Link | Phone battery cost | Notes |
| --- | --- | --- |
| BLE (this library) | Lowest | Notifications, GPS, and light HTTP over one connection. Bandwidth is small, which is fine for text/JSON. |
| Bluetooth tethering | Low | A good alternative when the Raspberry Pi needs a real IP connection. Efficient as long as traffic stays light. |
| Wi-Fi tethering | High | Full bandwidth, but keeping the phone's hotspot radio running all day is expensive. |

## Quick Start

This package requires Python 3.13 or newer and Linux with BlueZ when it hosts
the BLE UART service.

1. Install the package from PyPI:

   ```sh
   pip install gadgetbridge-rpi-link
   ```

   If you use `uv`, allow pre-releases because the `bluez-peripheral`
   dependency is currently published as an alpha release:

   ```sh
   uv pip install --prerelease=allow gadgetbridge-rpi-link
   ```

2. Start the included BLE host for a manual smoke test:

   ```sh
   gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
   ```

3. Install [Gadgetbridge](https://gadgetbridge.org/) on Android. In its
   discovery screen, enable `Discover unsupported devices`, scan, long-press
   the Raspberry Pi, and choose `Add test device`. Select `Bangle.js` in the
   dialog and register it.
4. Enable the settings required for the features you want. See
   [Android App Setup Details](#android-app-setup-details).

The distribution name is `gadgetbridge-rpi-link`; the Python import name is
`gadgetbridge_rpi_link`. The package installs `bluez-peripheral` for BlueZ
hosting. Its other operations use only the Python standard library.

## Library Scope

Implemented in the package:

- Converting data received over BLE into messages that Python can use, and
  splitting outgoing data into sizes suitable for BLE.
- Events for notifications, find-device requests, phone time, location,
  navigation, HTTP responses, and other received data.
- Outgoing GPS power requests, Android intents, and HTTP requests.
- Matching HTTP requests with responses and saving downloaded text.
- A BlueZ BLE UART host for Linux.

The library does not render notifications, set system time, or publish GPS
locations. Host applications provide those adapters.

## Sending Data Example

Outgoing messages can be passed as dictionaries. The library converts them
to the format expected by Gadgetbridge and splits them into smaller byte
strings that can be sent over BLE:

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL, GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
for data in protocol.encode_tx({"t": "info", "msg": "OK"}):
    # Send `data` through the BLE UART TX characteristic.
    ...

for data in protocol.encode_tx({"t": "status", "bat": "23"}):
    ...

for data in protocol.encode_tx({"t": "http", "url": DEFAULT_HTTP_TEXT_URL}):
    ...
```

## Receiving Data Example

Pass bytes received over BLE UART to the library to reconstruct messages and
convert them into events for each type of content:

```python
from gadgetbridge_rpi_link import GadgetbridgeProtocol

protocol = GadgetbridgeProtocol()
events = protocol.feed_rx(
    b'\x10GB({"t":"notify","title":"Chat","body":"Hello"})\n'
)
print(events[0])
```

## System Time Example

For a Raspberry Pi without an RTC, the phone can provide a time source after
Gadgetbridge connects. The library provides the received time as an event; the
host application is responsible for applying it to the system clock.

From a source checkout, stop any other BLE host and run the example in dry-run
mode first:

```sh
PYTHONPATH=src python3 examples/set_system_time.py
```

After confirming that time arrives from the phone and configuring the required
system permission, pass `--apply` to execute `sudo -n date -u --set ...`:

```sh
PYTHONPATH=src python3 examples/set_system_time.py --apply
```

This is not an immediate boot-time replacement for an RTC: the clock remains
uncorrected until Android connects and Gadgetbridge sends the time. Hardware
validation of this example is still pending, so test it in dry-run mode first.

## Session HTTP Example

```python
from gadgetbridge_rpi_link import GadgetbridgeSession

async def sender(message: str) -> None:
    # Send `message` through a BLE UART transport.
    ...

session = GadgetbridgeSession(sender=sender)
response = await session.request_http("https://example.com/data", timeout=10)
```

For a stable smoke check, use the official Espruino Gadgetbridge sample URL:

```python
from gadgetbridge_rpi_link import DEFAULT_HTTP_TEXT_URL

response = await session.request_http(DEFAULT_HTTP_TEXT_URL, timeout=30)
print(response.get("resp"))
```

## Android Intent Example

Host applications can use `send_intent(...)` for Android actions supported by
Gadgetbridge. For example, this starts the phone's configured voice assistant:

```python
session.send_intent(
    "android.intent.action.VOICE_COMMAND",
    flags=["FLAG_ACTIVITY_NEW_TASK"],
)
```

## BlueZ Host Example

The package installed in [Quick Start](#quick-start) includes
`bluez-peripheral` 0.2.0a3 or newer from the
dbus-fast-backed alpha series. Version 0.2.0a5 is the recommended release at
the time of writing.

Run the example on a Linux host with BlueZ access:

```sh
gadgetbridge-rpi-bluez --product gadgetbridge-rpi-link
```

The command is a small manual probe similar in purpose to a DBus/GATT smoke
test script. It advertises the Gadgetbridge UART service until stopped and
accepts simple keyboard commands:

- `t`: prompt for one outgoing Gadgetbridge text line and send it as-is.
- `g`: request Gadgetbridge GPS ON.
- `G`: send the Android voice command intent.
- `h`: run the official text HTTP download test and save it to a local file.
- `q`: quit.

For the `t` command, enter the body of one outgoing Gadgetbridge message. Use a
plain URL, not a Markdown link. JSON-ish object syntax and strict JSON are both
accepted, for example:

```text
{t:"info", msg:"OK"}
{"t":"status","bat":"23"}
{t:"http", url:"https://pur3.co.uk/hello.txt"}
```

Use `--auto-gps` only when the host should automatically request that GPS be
turned on after receiving the phone's current GPS state.

Library code can use the BlueZ transport directly from its submodule:

```python
from gadgetbridge_rpi_link.bluez import BluezGadgetbridgeUartServer

server = BluezGadgetbridgeUartServer("gadgetbridge-rpi-link")
await server.start()
try:
    server.send({ "t": "info", "msg": "OK" })
finally:
    await server.stop()
```

## Android App Setup Details

The Android app side has a few important Bangle.js-specific constraints.

| Feature | Required Android / Gadgetbridge setup |
| --- | --- |
| Android notifications | Allow notification access for Gadgetbridge. Check its notification filters if only some apps should be forwarded. |
| Phone location | Grant Android location permission, then enable `Use phone GPS data` and choose a practical update interval. See [Phone Location](#phone-location). |
| Google Maps navigation | Allow its notifications. If turn directions or distances are missing, see [Navigation Notifications](#navigation-notifications). |
| Android intents | Enable `Allow Intents`. See [Android Intents](#android-intents). |
| HTTP text/JSON requests | Use a Bangle.js-flavor build, or follow the official [Internet Helper setup](https://gadgetbridge.org/basics/integrations/internet-helper/) with a regular build. See [HTTP Requests](#http-requests). |

### Getting A Gadgetbridge Build

Which Gadgetbridge build you need depends on the features you want:

- Notifications, phone GPS, navigation, and Android intents work with the
  regular Gadgetbridge releases. Follow the download links on the
  [official Gadgetbridge website](https://gadgetbridge.org/) to install one.
- For HTTP requests, the simplest route is a Bangle.js-flavor
  build with direct internet access. Get one in either of these ways:
  1. Install the `Bangle.js Gadgetbridge` app directly, following the
     [Espruino Gadgetbridge documentation](https://www.espruino.com/Gadgetbridge).
  2. Build the Gadgetbridge project from source, switching the Android Studio
     build variant from the default `mainlineDebug` to one that starts with
     `banglejs`, such as `banglejsDebug`.
- A regular build can instead use the official Internet Helper add-on by
  following the [Gadgetbridge setup guide](https://gadgetbridge.org/basics/integrations/internet-helper/).
- CJK or other multibyte notification text needs a custom build from modified
  source; see [Text Encoding](#text-encoding).

### Text Encoding

Gadgetbridge's Bangle.js BLE UART currently uses Latin-1 when sending and
receiving strings. To exchange multibyte text such as CJK characters, you need
a custom Gadgetbridge build that changes the character encoding in both
directions to UTF-8. With that custom build installed in Android developer
mode, UTF-8 multibyte messages can be received by this library. Building from
source is described in
[Getting A Gadgetbridge Build](#getting-a-gadgetbridge-build).

### Phone Location

In the registered Bangle.js device settings, enable `Use phone GPS data` and
adjust `GPS data update interval` as needed. The host can then receive location
updates from Android even when the Raspberry Pi has no physical GPS receiver.

### Navigation Notifications

Google Maps navigation is notification-based. Gadgetbridge reads turn-by-turn
instructions from Android notifications and sends them to the Raspberry Pi. On
recent Android versions, Google Maps live notification categories can hide the
instruction details from Gadgetbridge. If turn directions or distances are
missing, disable the Google Maps `Live Updates`,
`Live info`, or similarly named notification category in Android's Google Maps
notification settings.

### Android Intents

To send Android intents, enable `Allow Intents` in the registered device
settings. Gadgetbridge rejects intent requests from the Raspberry Pi while
this setting is off. Its description notes that background use may require
Android's display-over-other-apps permission.

### HTTP Requests

For HTTP requests, use a Bangle.js-flavor build or configure a regular
Gadgetbridge release by following the official
[Internet Helper setup](https://gadgetbridge.org/basics/integrations/internet-helper/).
After registering the Bangle.js device, enable `Allow Internet Access`
in its settings.

## HTTP Download Behavior

The included HTTP file-saving feature writes content received from
Gadgetbridge to a file. Current Android Gadgetbridge Bangle.js HTTP support is
text-oriented, so use it for text and small downloads.

The `binary=None|True|False` option only controls how already received data is
written to disk:

- `None` writes strings as binary only when the output path has a known
  binary suffix such as `.bin`, `.fit`, or `.zip`.
- `True` preserves legacy Gadgetbridge binary strings as Latin-1 bytes when
  possible, falling back to UTF-8 for Unicode text recovered from Base64.
- `False` writes string data as text using the requested encoding, even when
  the output path suffix would normally be treated as binary.

Data already received as bytes is written unchanged. The library does not
sniff response content; hosts should define the expected download path or pass
`binary=True|False` when that write contract is clearer.

Arbitrary binary HTTP downloads are not supported by the current Gadgetbridge
Android HTTP feature. Large binary responses returned through the Android text
path can arrive with replacement characters already inserted
by Gadgetbridge and may not be recoverable by the host. Supporting general
binary downloads requires changing Gadgetbridge to preserve bytes in transit,
for example by sending raw bytes or encoding them as Base64 text.

## Development Notes

The source tree does not require hard-coded BLE addresses, device hostnames, or
private local filesystem paths. Tests use synthetic data, `example.com`,
and the public Espruino text sample URL. Generated files such as `__pycache__`,
local handoff notes, and device-specific logs should not be included in
published packages.

## Related Libraries

The Linux BLE host is built on these open-source libraries:

- [bluez-peripheral](https://github.com/spacecheese/bluez_peripheral) provides
  the Python interface for building a BLE peripheral with the BlueZ GATT API.
- [dbus-fast](https://github.com/bluetooth-devices/dbus-fast) provides the
  asynchronous D-Bus implementation used by `bluez-peripheral` to communicate
  with BlueZ.

We thank their authors and contributors for making this project possible.

## License

MIT License. See `LICENSE` for details.
