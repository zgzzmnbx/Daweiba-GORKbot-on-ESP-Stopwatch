"""Session ownership and monotonic UI generations; no transcript retention."""
import asyncio
import contextlib

from .voice import VoiceError


SAFE_ROUTING = {"asr": "local", "tts": "local", "allow_audio_upload": False, "allow_text_upload": False}


class Controller:
    def __init__(self, voice, robot):
        self.voice, self.robot = voice, robot
        self.owner = None
        self.generation = 0
        self.turn = 0
        self.phase = "idle"
        self.text = ""
        self.routing = dict(SAFE_ROUTING)
        self.lock = asyncio.Lock()
        self.pending = {}
        self.cleanup = set()

    def authorize(self, owner):
        if not owner or owner != self.owner or not self.voice.session:
            raise VoiceError(401, "SESSION_INVALID", "会话已失效，请重新连接并确认设置")

    def check(self, owner, generation):
        self.authorize(owner)
        if generation != self.generation:
            raise VoiceError(409, "STALE_GENERATION", "旧操作已丢弃")

    def advance(self, owner, generation):
        self.authorize(owner)
        if generation <= self.generation:
            raise VoiceError(409, "STALE_GENERATION", "旧操作已丢弃")
        self.invalidate(generation)

    def invalidate(self, generation):
        self.generation = generation
        self.phase = "idle"
        self.text = ""
        self.robot.show("idle", generation)
        for request_id, (turn, session, _) in list(self.pending.items()):
            task = asyncio.create_task(self.cancel_one(request_id, turn, session))
            self.cleanup.add(task)
            task.add_done_callback(self.cleanup.discard)

    async def cancel_one(self, request_id, turn, session):
        with contextlib.suppress(VoiceError):
            await self.voice.cancel(request_id, turn, session)

    async def connect(self, owner, replace=False):
        async with self.lock:
            if self.owner and self.voice.session and not replace:
                raise VoiceError(409, "SESSION_BUSY", "另一个工作台已占用，请明确接管")
            await self.voice.connect(replace)
            self.owner, self.generation, self.turn = owner, 0, 0
            self.pending.clear()
            # Even a service configured with permissive defaults starts safe here.
            try:
                await self.voice.routing(dict(SAFE_ROUTING))
            except VoiceError:
                await self.voice.release()
                self.owner = None
                raise
            self.routing = dict(SAFE_ROUTING)
            self.phase = "idle"
            self.text = ""
            # Robot generations span multiple browser sessions.
            self.robot.generation = 0
            self.robot.show("idle", 0)
            return {"generation": 0, "routing": self.routing}

    async def settings(self, owner, generation, routing):
        async with self.lock:
            self.advance(owner, generation)
            self.routing = await self.voice.routing(routing)
            # Changing modes ends the old turn even if its cancel was delayed.
            self.turn = await self.voice.turn()
            return {"routing": self.routing}

    async def begin(self, owner, generation, reuse_turn=False):
        async with self.lock:
            self.advance(owner, generation)
            if not reuse_turn or not self.turn:
                self.turn = await self.voice.turn()
            return {"generation": generation}

    async def stop(self, owner, generation):
        async with self.lock:
            self.advance(owner, generation)
            return {"generation": generation, "status": "stopped"}

    async def state(self, owner, generation, phase):
        self.check(owner, generation)
        self.phase = phase
        self.robot.show(phase, generation, self.text if phase == "speaking" else "")

    async def perform(self, owner, generation, kind, value):
        self.check(owner, generation)
        if not self.turn:
            raise VoiceError(409, "NO_TURN", "请先开始新一轮")
        if any(item[2] == generation for item in self.pending.values()):
            raise VoiceError(409, "REQUEST_BUSY", "上一请求尚未结束，请停止后重试")
        request_id = self.voice.request_id(kind)
        turn, session = self.turn, self.voice.session
        self.pending[request_id] = (turn, session, generation)
        self.phase = "processing"
        self.robot.show("processing", generation)
        try:
            if kind == "asr":
                result = await self.voice.transcribe(value, turn, request_id)
            else:
                result = await self.voice.synthesize(value, turn, request_id)
            self.check(owner, generation)
            self.phase = "ready"
            self.text = result if kind == "asr" else value
            self.robot.show("idle", generation, self.text)
            return result
        except VoiceError:
            if owner == self.owner and generation == self.generation:
                self.phase = "error"
                self.robot.show("error", generation)
            raise
        finally:
            self.pending.pop(request_id, None)

    async def heartbeat(self, owner):
        self.authorize(owner)
        try:
            await self.voice.alive()
        except VoiceError:
            if owner == self.owner:
                self.invalidate(self.generation + 1)
            raise
        self.authorize(owner)
        return {"generation": self.generation, "phase": self.phase, "robot": self.robot.snapshot()}

    async def release(self, owner):
        async with self.lock:
            self.authorize(owner)
            self.advance(owner, self.generation + 1)
            try:
                await self.voice.release()
            finally:
                self.owner = None

    async def close(self):
        await self.voice.close()
        if self.cleanup:
            await asyncio.gather(*self.cleanup, return_exceptions=True)
        await self.robot.close()
