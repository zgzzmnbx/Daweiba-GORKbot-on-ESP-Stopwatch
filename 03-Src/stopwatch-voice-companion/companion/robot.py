"""One BLE writer, latest-state wins. Offline robot never blocks PC speech."""
import asyncio
import contextlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from stopwatch_ble import BleExpressionClient, BleConsoleError, scan_targets

EXPRESSIONS = {"idle": "idle", "listening": "loop listening",
    "processing": "loop thinking", "speaking": "loop happy", "error": "confused"}


def short_bubble(text):
    # Full ASR/TTS text stays in the PC editor; device receives a labelled preview.
    clean = "".join(c for c in text if c.isprintable() and ord(c) <= 0xFFFF)
    return clean if len(clean) <= 24 else clean[:23] + "…"


class Robot:
    def __init__(self, client=None, scanner=None):
        self.client = client or BleExpressionClient()
        self.scanner = scanner
        self.targets = {}
        self.target = None
        self.enabled = False
        self.generation = 0
        self.revision = 0
        self.state, self.text = "idle", ""
        self.receipt, self.error = "", ""
        self.reconnects = 0
        self.changed = asyncio.Event()
        self.lock = asyncio.Lock()
        self.worker = None

    def start(self):
        self.worker = asyncio.create_task(self.run())

    def snapshot(self):
        return {"connected": self.client.connected, "enabled": self.enabled,
            "state": self.state, "error": self.error, "receipt": self.receipt,
            "reconnects": self.reconnects}

    async def scan(self):
        values = await scan_targets(timeout=5, scanner=self.scanner)
        self.targets = {value.address: value for value in values}
        return [{"name": x.name, "address": x.address} for x in values]

    async def connect(self, address):
        if address not in self.targets:
            raise BleConsoleError("请先扫描并选择当次发现的设备")
        async with self.lock:
            await self.client.disconnect()
            self.target = self.targets[address]
            await self.client.connect(self.target)
            self.enabled, self.reconnects = True, 0
            self.error = ""
            # Reconnection never replays a transcript from an earlier turn.
            self.text = ""
            self.changed.set()

    async def disconnect(self):
        self.enabled = False
        async with self.lock:
            await self.client.disconnect()
        self.receipt = ""

    def show(self, state, generation, text=""):
        if generation < self.generation:
            return
        self.generation = generation
        self.state, self.text = state, short_bubble(text)
        self.revision += 1
        self.changed.set()

    async def flush(self):
        async with self.lock:
            if not self.enabled or self.target is None:
                return
            reconnected = False
            if not self.client.connected:
                if self.reconnects >= 2:
                    self.error = "设备离线；两次重连已结束，请手动连接"
                    return
                self.reconnects += 1
                await self.client.connect(self.target)
                reconnected = True
            revision = self.revision
            state, text = self.state, "" if reconnected else self.text
            self.receipt = await self.client.send_command(EXPRESSIONS[state])
            if revision != self.revision:
                return
            await self.client.clear_text()
            if text and revision == self.revision:
                self.receipt = await self.client.send_text(text)
            self.error = ""

    async def run(self):
        while True:
            try:
                try:
                    await asyncio.wait_for(self.changed.wait(), 1)
                except asyncio.TimeoutError:
                    if not self.enabled or self.client.connected or self.reconnects >= 2:
                        continue
                self.changed.clear()
                await self.flush()
            except BleConsoleError as exc:
                self.error, self.receipt = str(exc), ""
            except Exception:
                self.error, self.receipt = "蓝牙连接失败，可重新扫描连接", ""

    async def close(self):
        if self.worker:
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker
        await self.disconnect()
