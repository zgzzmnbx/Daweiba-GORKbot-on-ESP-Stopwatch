"""One BLE writer, latest-state wins. Offline robot never blocks PC speech."""
import asyncio
import contextlib
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from stopwatch_ble import BleExpressionClient, BleConsoleError, EXPRESSIONS as BLE_EXPRESSIONS, scan_targets
from stopwatch_sound import SoundClient
from stopwatch_audio import AudioClient, make_wav, read_wav

EXPRESSIONS = {"idle": "idle", "listening": "loop listening",
    "processing": "loop thinking", "speaking": "loop happy", "error": "confused"}
RECONNECT_INITIAL_DELAY = 5
RECONNECT_MAX_DELAY = 30
CONNECTION_POLL_SECONDS = 1


def short_bubble(text):
    # Full ASR/TTS text stays in the PC editor; device receives a labelled preview.
    clean = "".join(c for c in text if c.isprintable() and ord(c) <= 0xFFFF)
    return clean if len(clean) <= 24 else clean[:23] + "…"


class Robot:
    def __init__(self, client=None, scanner=None, sound=None):
        self.client = client or BleExpressionClient()
        self.scanner = scanner
        self.sound = sound or SoundClient()
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
        self.auto_task = None
        self.maintain_task = None
        self.operation_epoch = 0
        self.audio = None
        self.audio_task = None
        self.audio_job = ""
        self.audio_mode = ""
        self.audio_progress = {"stage": "idle", "bytes": 0, "total": 0, "elapsed": 0, "rate": 0}
        self.audio_result = None
        self.audio_error = ""

    def start(self):
        self.worker = asyncio.create_task(self.run())

    def start_auto_connect(self, preferred_address=""):
        """Start the background connection supervisor for this StopWatch."""
        if self.auto_task is None:
            self.auto_task = asyncio.create_task(
                self._auto_connect(preferred_address.strip(), self.operation_epoch))
            self._start_maintain(preferred_address.strip(), self.auto_task)

    def _start_maintain(self, preferred_address, initial=None):
        if self.maintain_task is None or self.maintain_task.done():
            self.maintain_task = asyncio.create_task(
                self._maintain_connection(preferred_address, self.operation_epoch, initial))

    async def _stop_auto_connect(self):
        tasks = (self.maintain_task, self.auto_task)
        for task in tasks:
            if task and not task.done():
                task.cancel()
        for task in tasks:
            if task and not task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _maintain_connection(self, preferred_address, epoch, initial):
        if initial:
            with contextlib.suppress(asyncio.CancelledError):
                await initial
        delay = RECONNECT_INITIAL_DELAY
        last_address = preferred_address
        pinned_address = bool(preferred_address)
        while epoch == self.operation_epoch:
            if self.client.connected:
                if self.target is not None:
                    last_address = self.target.address
                delay = RECONNECT_INITIAL_DELAY
                await asyncio.sleep(CONNECTION_POLL_SECONDS)
                continue
            await asyncio.sleep(delay)
            if epoch != self.operation_epoch:
                return
            try:
                async with self.lock:
                    if epoch != self.operation_epoch or self.client.connected:
                        continue
                    values = await asyncio.wait_for(
                        scan_targets(timeout=5, scanner=self.scanner), 8)
                    self.targets = {value.address: value for value in values}
                    candidates = [value for value in values
                                  if value.address.casefold() == last_address.casefold()]
                    if not candidates and not pinned_address and len(values) == 1:
                        candidates = values
                    if not candidates:
                        self.error = ("未发现已配置的 StopWatch，等待设备广播后重试"
                                      if last_address else "未发现唯一 StopWatch，等待设备广播后重试")
                        delay = min(delay * 2, RECONNECT_MAX_DELAY)
                        continue
                    last_address = candidates[0].address
                    self.reconnects += 1
                    await asyncio.wait_for(self._connect_locked(candidates[0]), 75)
                    delay = RECONNECT_INITIAL_DELAY
            except asyncio.CancelledError:
                raise
            except (asyncio.TimeoutError, BleConsoleError) as exc:
                self.error = str(exc) if isinstance(exc, BleConsoleError) else "蓝牙重连超时，稍后重试"
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
            except Exception:
                self.error = "蓝牙重连失败，稍后重试"
                delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _auto_connect(self, preferred_address, epoch):
        try:
            async with self.lock:
                if epoch != self.operation_epoch:
                    return
                values = await asyncio.wait_for(
                    scan_targets(timeout=5, scanner=self.scanner), 8)
                if epoch != self.operation_epoch:
                    return
                self.targets = {value.address: value for value in values}
                if preferred_address:
                    candidates = [value for value in values
                        if value.address.casefold() == preferred_address.casefold()]
                    if not candidates:
                        self.error = "未发现已配置的 StopWatch，请手动扫描连接"
                        return
                elif len(values) == 1:
                    candidates = values
                elif not values:
                    self.error = "未发现 StopWatch，请确认设备蓝牙已开启"
                    return
                else:
                    self.error = "发现多台 StopWatch，请手动选择设备"
                    return
                await asyncio.wait_for(self._connect_locked(candidates[0]), 75)
                if epoch != self.operation_epoch:
                    self.enabled = False
                    await self.sound.detach()
                    await self.client.disconnect()
                    self.target = None
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, BleConsoleError) as exc:
            if epoch == self.operation_epoch:
                self.error = str(exc) if isinstance(exc, BleConsoleError) else "蓝牙扫描或连接超时，请手动重试"
        except Exception:
            if epoch == self.operation_epoch:
                self.error = "蓝牙自动连接失败，请手动扫描连接"

    async def _connect_locked(self, target):
        self.enabled = False
        self.target = None
        try:
            await self.sound.detach()
            await self.client.disconnect()
            self.target = target
            await self.client.connect(target)
            raw_client = getattr(self.client, "client", None)
            if raw_client is not None:
                await self.sound.attach(raw_client)
        except BaseException:
            await self.sound.detach()
            await self.client.disconnect()
            self.enabled = False
            self.target = None
            raise
        self.enabled, self.reconnects = True, 0
        self.error = ""
        self.text = ""
        self.changed.set()

    def snapshot(self):
        return {"connected": self.client.connected, "enabled": self.enabled,
            "state": self.state, "error": self.error, "receipt": self.receipt,
            "reconnects": self.reconnects, "audio": self.audio_snapshot()}

    def audio_snapshot(self):
        return {"job_id": self.audio_job, "mode": self.audio_mode, **self.audio_progress,
            "error": self.audio_error, "result_ready": self.audio_result is not None,
            "running": bool(self.audio_task and not self.audio_task.done())}

    async def scan(self):
        self.operation_epoch += 1
        await self._stop_auto_connect()
        async with self.lock:
            values = await scan_targets(timeout=5, scanner=self.scanner)
            self.targets = {value.address: value for value in values}
        return [{"name": x.name, "address": x.address} for x in values]

    async def connect(self, address):
        self.operation_epoch += 1
        await self._stop_auto_connect()
        async with self.lock:
            if address not in self.targets:
                raise BleConsoleError("请先扫描并选择当次发现的设备")
            try:
                await self._connect_locked(self.targets[address])
            finally:
                self._start_maintain(address)

    async def disconnect(self):
        self.operation_epoch += 1
        self.enabled = False
        await self._stop_auto_connect()
        await self.cancel_audio()
        async with self.lock:
            self.enabled = False
            self.target = None
            self.reconnects = 0
            await self.sound.detach()
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
                if self.maintain_task and not self.maintain_task.done():
                    return
                if self.reconnects >= 2:
                    self.error = "设备离线；两次重连已结束，请手动连接"
                    return
                self.reconnects += 1
                await self.client.connect(self.target)
                raw_client = getattr(self.client, "client", None)
                if raw_client is not None:
                    await self.sound.attach(raw_client)
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
                    if (not self.enabled or self.client.connected or self.reconnects >= 2
                            or (self.maintain_task and not self.maintain_task.done())):
                        continue
                self.changed.clear()
                await self.flush()
            except BleConsoleError as exc:
                self.error, self.receipt = str(exc), ""
            except Exception:
                self.error, self.receipt = "蓝牙连接失败，可重新扫描连接", ""

    async def close(self):
        await self._stop_auto_connect()
        if self.worker:
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker
        await self.disconnect()

    def _audio_changed(self, value):
        self.audio_progress = value

    def _require_audio_idle(self):
        if self.audio_task and not self.audio_task.done():
            raise BleConsoleError("延迟音频任务正在进行，请先取消")
        if not self.enabled or not self.client.connected:
            raise BleConsoleError("StopWatch 未连接")

    async def _run_audio(self, mode, pcm=None, rate=None):
        async with self.lock:
            raw = getattr(self.client, "client", None)
            if raw is None or not getattr(raw, "is_connected", False):
                raise BleConsoleError("StopWatch 未连接")
            self.audio = AudioClient(raw)
            try:
                await self.audio.open()
                if mode in ("record", "echo"):
                    captured, captured_rate = await self.audio.record(self._audio_changed)
                    if mode == "record":
                        self.audio_result = make_wav(captured, captured_rate)
                    else:
                        await self.audio.play(captured, captured_rate, self._audio_changed)
                else:
                    await self.audio.play(pcm, rate, self._audio_changed)
            finally:
                await self.audio.close()
                self.audio = None

    def _start_audio(self, mode, pcm=None, rate=None):
        self._require_audio_idle()
        self.audio_job, self.audio_mode = str(uuid.uuid4()), mode
        self.audio_result, self.audio_error = None, ""
        self.audio_progress = {"stage": "starting", "bytes": 0, "total": len(pcm or b""), "elapsed": 0, "rate": 0}
        async def runner():
            try:
                await self._run_audio(mode, pcm, rate)
            except asyncio.CancelledError:
                self.audio_progress = {**self.audio_progress, "stage": "cancelled"}
                raise
            except Exception as exc:
                self.audio_error = str(exc).strip() or (
                    "Watch 音频通信超时；请检查蓝牙连接，旧版固件还需打开 Audio test"
                    if isinstance(exc, TimeoutError) else "Watch 音频任务意外失败")
                self.audio_progress = {**self.audio_progress, "stage": "error"}
        self.audio_task = asyncio.create_task(runner())
        return self.audio_snapshot()

    def start_audio_record(self, echo=False):
        return self._start_audio("echo" if echo else "record")

    def start_audio_play(self, wav):
        try:
            pcm, rate = read_wav(wav)
        except ValueError as exc:
            raise BleConsoleError(str(exc)) from exc
        return self._start_audio("play", pcm, rate)

    async def cancel_audio(self):
        task = self.audio_task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        return self.audio_snapshot()

    def take_audio_result(self, job_id):
        if job_id != self.audio_job or self.audio_result is None:
            raise BleConsoleError("录音结果不存在、尚未完成或已释放")
        result, self.audio_result = self.audio_result, None
        return result

    async def play_sound(self, sound_id):
        self._require_audio_idle()
        async with self.lock:
            return await self.sound.play(sound_id)

    async def stop_sound(self):
        async with self.lock:
            return await self.sound.stop()

    async def set_sound_volume(self, volume):
        self._require_audio_idle()
        async with self.lock:
            return await self.sound.set_volume(volume)

    async def play_expression(self, expression, mode="once"):
        """Send one validated manual expression over the existing BLE writer."""
        if expression not in BLE_EXPRESSIONS:
            raise BleConsoleError("未知 StopWatch 表情")
        if mode not in ("once", "loop"):
            raise BleConsoleError("播放方式只能是 once 或 loop")
        self._require_audio_idle()
        async with self.lock:
            command = expression if mode == "once" else f"loop {expression}"
            self.receipt = await self.client.send_command(command)
            self.state, self.text, self.error = expression, "", ""
            return {"receipt": self.receipt, "expression": expression, "mode": mode}

    async def set_bubble(self, text):
        self._require_audio_idle()
        async with self.lock:
            self.receipt = await self.client.send_text(text)
            self.text, self.error = text, ""
            return {"receipt": self.receipt, "text": text}

    async def clear_bubble(self):
        self._require_audio_idle()
        async with self.lock:
            self.receipt = await self.client.clear_text()
            self.text, self.error = "", ""
            return {"receipt": self.receipt}
