"""BlueZ GATT server transport for Gadgetbridge UART."""

from __future__ import annotations

import asyncio
import inspect
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

from .constants import (
    DEFAULT_TX_CHUNK_SIZE,
    RX_CHARACTERISTIC_UUID,
    SERVICE_UUID,
    TX_CHARACTERISTIC_UUID,
)
from .events import GadgetbridgeEvent
from .frames import FrameEncoder
from .protocol import GadgetbridgeProtocol

try:
    from bluez_peripheral.advert import Advertisement
    from bluez_peripheral.agent import NoIoAgent
    from bluez_peripheral.gatt.characteristic import (
        CharacteristicFlags as CharFlags,
        characteristic,
    )
    from bluez_peripheral.gatt.service import Service
    try:
        from bluez_peripheral.util import Adapter
    except ImportError:
        from bluez_peripheral.adapter import Adapter
    from bluez_peripheral.util import get_message_bus
    from dbus_fast.constants import PropertyAccess
    from dbus_fast.service import ServiceInterface, dbus_property, method

    HAS_BLUEZ = True
except ImportError:
    Advertisement = None
    Adapter = None
    CharFlags = None
    NoIoAgent = None
    Service = object
    ServiceInterface = object
    characteristic = None
    dbus_property = None
    get_message_bus = None
    method = None
    HAS_BLUEZ = False

EventHandler = Callable[[GadgetbridgeEvent], Any | Awaitable[Any]]
RxChunkHandler = Callable[[bytes], Any | Awaitable[Any]]


class BluezUnavailableError(ImportError):
    """Raised when the bluez-peripheral dependency is unavailable."""


def is_bluez_supported() -> bool:
    """Return whether the BlueZ transport dependencies are importable."""

    return HAS_BLUEZ


def require_bluez() -> None:
    """Raise a typed error when BlueZ transport support is unavailable."""

    if not HAS_BLUEZ:
        raise BluezUnavailableError(
            "bluez-peripheral is required for BlueZ support; "
            "install 'bluez-peripheral>=0.2.0a3,<0.3'"
        )


if HAS_BLUEZ:

    _GADGETBRIDGE_NAME_PREFIXES = (
        "Bangle.js",
        "Pixl.js",
        "Puck.js",
        "MDBT42Q",
        "Espruino",
    )


    def _gadgetbridge_advertised_name(product: str) -> str:
        if product.startswith(_GADGETBRIDGE_NAME_PREFIXES):
            return product
        return f"Bangle.js {product}"


    def _scan_response_local_name_hex(name: str) -> str:
        data = name.encode("utf-8")[:29]
        return f"{len(data) + 1:02x}09{data.hex()}"


    class _BtmgmtUartAdvertisement:
        """Fallback advertiser for systems where bluetoothd D-Bus advertising fails."""

        def __init__(
            self,
            service_uuid: str,
            local_name: str,
            instance_id: int = 1,
        ) -> None:
            self.service_uuid = service_uuid
            self.local_name = local_name
            self.instance_id = instance_id
            self.active = False

        async def register(self) -> None:
            btmgmt = shutil.which("btmgmt") or "/usr/bin/btmgmt"
            instance = str(self.instance_id)
            await self._run_btmgmt(
                btmgmt,
                "rm-adv",
                instance,
                allow_failure=True,
                timeout=2.0,
            )
            await self._run_btmgmt(
                btmgmt,
                "add-adv",
                "-u",
                self.service_uuid,
                "-c",
                "-g",
                "-s",
                _scan_response_local_name_hex(self.local_name),
                instance,
                timeout=5.0,
            )
            self.active = True

        async def unregister(self) -> None:
            if not self.active:
                return
            btmgmt = shutil.which("btmgmt") or "/usr/bin/btmgmt"
            await self._run_btmgmt(
                btmgmt,
                "rm-adv",
                str(self.instance_id),
                allow_failure=True,
                timeout=2.0,
            )
            self.active = False

        async def _run_btmgmt(
            self,
            btmgmt: str,
            *args: str,
            allow_failure: bool = False,
            timeout: float = 5.0,
        ) -> None:
            timeout_cmd = shutil.which("timeout") or "/usr/bin/timeout"
            process = await asyncio.create_subprocess_exec(
                "sudo",
                "-n",
                timeout_cmd,
                "-k",
                "1s",
                f"{timeout:g}s",
                btmgmt,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout + 2.0,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                if allow_failure:
                    return
                raise RuntimeError(f"btmgmt timed out after {timeout:.1f}s") from None
            if process.returncode == 0 or allow_failure:
                return
            output = (stderr or stdout).decode("utf-8", errors="replace").strip()
            raise RuntimeError(output or f"btmgmt exited with {process.returncode}")

    class _MinimalUartAdvertisement(ServiceInterface):  # type: ignore[misc, valid-type]
        """Small LEAdvertisement1 object that avoids optional BlueZ parameters."""

        _DEFAULT_PATH = "/org/cardputer_zero/gadgetbridge/advertisement"

        def __init__(
            self,
            service_uuids: list[str],
            local_name: str | None = None,
        ) -> None:
            super().__init__("org.bluez.LEAdvertisement1")
            self.service_uuids = service_uuids
            self.local_name = local_name
            self.bus = None
            self.adapter = None
            self.path: str | None = None

        @method("Release")
        def release(self):
            self.unexport()

        @dbus_property(PropertyAccess.READ, "Type")
        def get_type(self) -> "s":  # type: ignore[valid-type]
            return "peripheral"

        @dbus_property(PropertyAccess.READ, "ServiceUUIDs")
        def get_service_uuids(self) -> "as":  # type: ignore[valid-type]
            return self.service_uuids

        async def register(
            self,
            bus: Any,
            *,
            path: str | None = None,
            adapter: Any = None,
        ) -> None:
            self.bus = bus
            self.path = path or self._DEFAULT_PATH
            bus.export(self.path, self)
            try:
                if adapter is None:
                    adapter = await Adapter.get_first(bus)
                manager = adapter.get_advertising_manager()
                await manager.call_register_advertisement(self.path, {})
            except Exception:
                self.unexport()
                raise
            self.adapter = adapter

        async def unregister(self) -> None:
            if self.path is None or self.adapter is None:
                return
            manager = self.adapter.get_advertising_manager()
            await manager.call_unregister_advertisement(self.path)
            self.unexport()
            self.adapter = None

        def unexport(self) -> None:
            if self.bus is None or self.path is None:
                return
            self.bus.unexport(self.path)
            self.path = None

    class _NamedMinimalUartAdvertisement(_MinimalUartAdvertisement):
        @dbus_property(PropertyAccess.READ, "LocalName")
        def get_local_name(self) -> "s":  # type: ignore[valid-type]
            return self.local_name or ""

    class _GadgetbridgeUartService(Service):  # type: ignore[misc, valid-type]
        def __init__(
            self,
            product: str,
            protocol: GadgetbridgeProtocol,
            on_event: EventHandler | None,
            on_rx_chunk: RxChunkHandler | None,
            encoder: FrameEncoder,
        ) -> None:
            self.product = product
            self.protocol = protocol
            self.on_event = on_event
            self.on_rx_chunk = on_rx_chunk
            self.encoder = encoder
            super().__init__(SERVICE_UUID, True)

        @characteristic(TX_CHARACTERISTIC_UUID, CharFlags.NOTIFY | CharFlags.READ)
        def tx_characteristic(self, _options: dict[str, Any]) -> bytes:
            return self.product.encode("utf-8")

        @characteristic(RX_CHARACTERISTIC_UUID, CharFlags.WRITE).setter
        def rx_characteristic(self, value: bytes, _options: dict[str, Any]) -> None:
            chunk = bytes(value)
            if self.on_rx_chunk is not None:
                result = self.on_rx_chunk(chunk)
                if inspect.isawaitable(result):
                    asyncio.create_task(result)
            for event in self.protocol.feed_rx(chunk):
                self._dispatch_event(event)

        def notify(self, message: str | dict[str, Any]) -> None:
            for chunk in self.encoder.encode(message):
                self.notify_chunk(chunk)

        def notify_chunk(self, chunk: bytes) -> None:
            self.tx_characteristic.changed(chunk)

        def _dispatch_event(self, event: GadgetbridgeEvent) -> None:
            if self.on_event is None:
                return
            result = self.on_event(event)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

else:

    class _GadgetbridgeUartService:  # type: ignore[no-redef]
        pass


class BluezGadgetbridgeUartServer:
    """Host the Gadgetbridge UART GATT service through BlueZ."""

    def __init__(
        self,
        product: str,
        on_event: EventHandler | None = None,
        on_rx_chunk: RxChunkHandler | None = None,
        protocol: GadgetbridgeProtocol | None = None,
        tx_chunk_size: int = DEFAULT_TX_CHUNK_SIZE,
        advertise: bool = True,
    ) -> None:
        require_bluez()
        self.product = product
        self.advertised_name = _gadgetbridge_advertised_name(product)
        self.advertise = advertise
        self.on_event = on_event
        self.on_rx_chunk = on_rx_chunk
        self.protocol = protocol or GadgetbridgeProtocol()
        self.encoder = FrameEncoder(chunk_size=tx_chunk_size)
        self._tx_lock: asyncio.Lock | None = None
        self.bus = None
        self.advert = None
        self.agent = None
        self.service = _GadgetbridgeUartService(
            product=self.product,
            protocol=self.protocol,
            on_event=self.on_event,
            on_rx_chunk=self.on_rx_chunk,
            encoder=self.encoder,
        )

    async def start(self) -> None:
        self.bus = await get_message_bus()
        await self.service.register(self.bus)
        self.agent = NoIoAgent()
        try:
            await self.agent.register(
                self.bus,
                path="/org/cardputer_zero/gadgetbridge/agent",
                default=False,
            )
        except TypeError:
            await self.agent.register(self.bus)
        if not self.advertise:
            return
        adapter = await Adapter.get_first(self.bus)
        try:
            self.advert = Advertisement(
                self.advertised_name,
                [SERVICE_UUID],
                appearance=0,
                timeout=0,
            )
        except TypeError:
            self.advert = Advertisement(self.advertised_name, [SERVICE_UUID], 0, 0)
        try:
            await self.advert.register(self.bus, adapter=adapter)
        except TypeError:
            try:
                await self.advert.register(self.bus, adapter)
            except Exception:
                self._unexport_advertisement()
                self.advert = await self._register_minimal_advertisement(adapter)
        except Exception:
            self._unexport_advertisement()
            self.advert = await self._register_minimal_advertisement(adapter)

    async def stop(self) -> None:
        if self.advert is not None:
            unregister = getattr(self.advert, "unregister", None)
            if unregister is not None:
                try:
                    result = unregister()
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    pass
            self.advert = None
        if self.bus is not None:
            self.bus.disconnect()
            self.bus = None

    def _unexport_advertisement(self) -> None:
        if self.advert is None:
            return
        unexport = getattr(self.advert, "unexport", None)
        if unexport is None:
            return
        try:
            unexport()
        except Exception:
            pass

    async def _register_minimal_advertisement(self, adapter: Any) -> Any:
        attempts: list[_MinimalUartAdvertisement] = [
            _NamedMinimalUartAdvertisement([SERVICE_UUID], self.advertised_name),
            _MinimalUartAdvertisement([SERVICE_UUID]),
        ]
        last_error: Exception | None = None
        for advert in attempts:
            try:
                await advert.register(self.bus, adapter=adapter)
            except Exception as exc:
                last_error = exc
            else:
                return advert
        btmgmt_advert = _BtmgmtUartAdvertisement(
            SERVICE_UUID,
            self.advertised_name,
        )
        try:
            await btmgmt_advert.register()
        except Exception as exc:
            last_error = exc
        else:
            return btmgmt_advert
        if last_error is not None:
            raise last_error
        raise RuntimeError("failed to create BlueZ advertisement")

    def _send_chunks_sync(self, message: str | dict[str, Any]) -> None:
        self.service.notify(message)

    async def send_async(self, message: str | dict[str, Any]) -> None:
        if self._tx_lock is None:
            self._tx_lock = asyncio.Lock()

        chunks = list(self.encoder.encode(message))
        async with self._tx_lock:
            for chunk in chunks:
                self.service.notify_chunk(chunk)
                await asyncio.sleep(0)

    def send(self, message: str | dict[str, Any]) -> asyncio.Task[None] | None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._send_chunks_sync(message)
            return None
        return loop.create_task(self.send_async(message))


__all__ = [
    "BluezGadgetbridgeUartServer",
    "BluezUnavailableError",
    "HAS_BLUEZ",
    "is_bluez_supported",
    "require_bluez",
]
