"""v0.8.0 built-in sound protocol helpers; no connection is opened on import."""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import struct

VERSION = 1
SERVICE_UUID = "48f1c001-8a75-4db6-9c18-590f7e9b0a01"
COMMAND_UUID = "48f1c002-8a75-4db6-9c18-590f7e9b0a01"
EVENT_UUID = "48f1c003-8a75-4db6-9c18-590f7e9b0a01"
FRAME = struct.Struct("<BBHIB")

CAPABILITIES, CATALOG, PLAY, STOP, SET_VOLUME, GET_STATUS = range(1, 7)
ACCEPTED, STARTED, COMPLETED, STOPPED, STATUS, FAILED = (0x80, 0x81, 0x82, 0x83, 0x84, 0xFF)
EVENT_NAMES = {
    ACCEPTED: "accepted", STARTED: "started", COMPLETED: "completed",
    STOPPED: "stopped", STATUS: "status", FAILED: "failed",
}


@dataclass(frozen=True)
class SoundFrame:
    operation: int
    request_id: int
    value: int = 0
    argument: int = 0

    def encode(self) -> bytes:
        if not 0 < self.request_id <= 0xFFFF:
            raise ValueError("request_id must be 1..65535")
        if not 0 <= self.value <= 0xFFFFFFFF or not 0 <= self.argument <= 0xFF:
            raise ValueError("frame value out of range")
        return FRAME.pack(VERSION, self.operation, self.request_id, self.value, self.argument)

    @classmethod
    def decode(cls, data: bytes):
        if len(data) != FRAME.size:
            raise ValueError("sound frame must be exactly 9 bytes")
        version, operation, request_id, value, argument = FRAME.unpack(data)
        if version != VERSION or request_id == 0:
            raise ValueError("unsupported version or zero request_id")
        return cls(operation, request_id, value, argument)


def play(request_id: int, sound_id: int) -> bytes:
    if sound_id not in range(1, 7):
        raise ValueError("unknown sound_id")
    return SoundFrame(PLAY, request_id, argument=sound_id).encode()


def set_volume(request_id: int, volume: int) -> bytes:
    if volume not in range(0, 101):
        raise ValueError("volume must be 0..100")
    return SoundFrame(SET_VOLUME, request_id, value=volume).encode()


class SoundClient:
    """Built-in sound control over an already-owned BleakClient."""

    def __init__(self, timeout: float = 3.0):
        self.client = None
        self.command = COMMAND_UUID
        self.events = EVENT_UUID
        self.timeout = timeout
        self.queue = None
        self.next_id = 1
        self.lock = asyncio.Lock()

    async def attach(self, client):
        self.client = client
        self.queue = asyncio.Queue()
        await client.start_notify(self.events, self._notify)

    async def detach(self):
        if self.client and getattr(self.client, "is_connected", False):
            try:
                await self.client.stop_notify(self.events)
            except Exception:
                pass
        self.client = None
        self.queue = None

    def _notify(self, _sender, data):
        try:
            frame = SoundFrame.decode(bytes(data))
        except ValueError:
            return
        if self.queue:
            self.queue.put_nowait(frame)

    def _id(self):
        value = self.next_id
        self.next_id = 1 if value == 0xFFFF else value + 1
        return value

    async def request(self, operation, value=0, argument=0):
        if not self.client or not getattr(self.client, "is_connected", False):
            raise RuntimeError("BLE sound service is not connected")
        async with self.lock:
            request_id = self._id()
            while not self.queue.empty():
                self.queue.get_nowait()
            await self.client.write_gatt_char(
                self.command, SoundFrame(operation, request_id, value, argument).encode(), response=True
            )
            accepted = started = False
            while True:
                event = await asyncio.wait_for(self.queue.get(), self.timeout)
                if event.request_id != request_id:
                    continue
                if event.operation == FAILED:
                    raise RuntimeError(f"device rejected sound request: {event.value}")
                if event.operation == ACCEPTED:
                    accepted = True
                    continue
                if event.operation == STARTED:
                    started = True
                    continue
                terminal = {
                    PLAY: (COMPLETED, STOPPED), STOP: (STOPPED,),
                    SET_VOLUME: (COMPLETED,), CAPABILITIES: (STATUS,),
                    CATALOG: (STATUS,), GET_STATUS: (STATUS,),
                }.get(operation, (COMPLETED, STOPPED, STATUS))
                if event.operation in terminal:
                    return {"request_id": request_id, "event": event.operation,
                            "event_name": EVENT_NAMES[event.operation],
                            "value": event.value, "sound_id": event.argument,
                            "accepted": accepted, "started": started}

    async def play(self, sound_id):
        if sound_id not in range(1, 7):
            raise ValueError("unknown sound_id")
        return await self.request(PLAY, argument=sound_id)

    async def stop(self):
        return await self.request(STOP)

    async def set_volume(self, volume):
        if volume not in range(0, 101):
            raise ValueError("volume must be 0..100")
        return await self.request(SET_VOLUME, value=volume)
