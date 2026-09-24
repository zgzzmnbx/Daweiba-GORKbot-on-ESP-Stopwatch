"""Session ownership and monotonic UI generations; no transcript retention."""
import asyncio
import contextlib
import time

from .voice import VoiceError


SAFE_ROUTING = {"asr": "local", "tts": "local", "allow_audio_upload": False, "allow_text_upload": False}
BLE_EXPRESSIONS = frozenset((
    "idle", "listening", "thinking", "happy", "happy-work", "excited", "curious", "confused",
    "angry", "surprised", "sad", "sleepy", "dizzy", "sleeping", "waking", "searching", "working",
    "bored", "suspicious", "proud", "shy", "laughing", "scared", "celebrate",
))


class Controller:
    def __init__(self, voice, robot, answer=None, answer_history_turns=4):
        self.voice, self.robot, self.answer = voice, robot, answer
        # `owner` protects the Gork workbench (desktop character and BLE).  A
        # voice session is an additional, independently releasable resource.
        # Keeping them separate means an offline ASR/TTS service cannot lock
        # the user out of local preview or an already connected StopWatch.
        self.owner = None
        self.voice_owner = None
        self.workspace_explicit = False
        self.workspace_deadline = 0.0
        self.workspace_lease_seconds = 30.0
        self.generation = 0
        self.turn = 0
        self.phase = "idle"
        self.text = ""
        self.routing = dict(SAFE_ROUTING)
        self.lock = asyncio.Lock()
        self.pending = {}
        self.cleanup = set()
        self.answer_upload = False
        self.answer_history = []
        self.answer_history_limit = max(0, min(10, int(answer_history_turns))) * 2
        self.answer_tasks = set()
        self.speech = None
        self.character = {"expression": "idle", "mode": "loop", "bubble": "", "manual": False, "revision": 0}
        self.character_bubble_deadline = 0.0

    def authorize(self, owner):
        if self.workspace_explicit and self.workspace_deadline <= time.monotonic():
            self.owner = None
            self.voice_owner = None
            self.workspace_explicit = False
        if not owner or owner != self.owner:
            raise VoiceError(401, "WORKSPACE_INVALID", "工作台控制权已失效，请重新取得控制权")

    def renew_workspace(self, owner):
        self.authorize(owner)
        if self.workspace_explicit:
            self.workspace_deadline = time.monotonic() + self.workspace_lease_seconds

    def require_voice(self, owner):
        self.authorize(owner)
        if owner != self.voice_owner or not self.voice.session:
            raise VoiceError(401, "VOICE_SESSION_INVALID", "语音会话未连接或已释放")

    def check(self, owner, generation):
        self.require_voice(owner)
        if generation != self.generation:
            raise VoiceError(409, "STALE_GENERATION", "旧操作已丢弃")

    def advance(self, owner, generation):
        self.require_voice(owner)
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
        for task in tuple(self.answer_tasks):
            task.cancel()

    async def cancel_one(self, request_id, turn, session):
        with contextlib.suppress(VoiceError):
            await self.voice.cancel(request_id, turn, session)

    async def connect(self, owner, replace=False):
        async with self.lock:
            if self.owner and self.owner != owner and self.workspace_explicit and not replace:
                raise VoiceError(409, "WORKSPACE_BUSY", "另一窗口正在控制，请明确接管")
            if self.voice_owner and self.voice_owner != owner and self.voice.session and not replace:
                raise VoiceError(409, "SESSION_BUSY", "另一个程序正在使用语音会话，请明确接管")
            await self.voice.connect(replace)
            self.owner, self.voice_owner, self.generation, self.turn = owner, owner, 0, 0
            self.workspace_explicit = False
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
            self.answer_upload = False
            self.speech = None
            self.answer_history.clear()
            # Robot generations span multiple browser sessions.
            self.robot.generation = 0
            self.robot.show("idle", 0)
            return {"generation": 0, "routing": self.routing}

    async def acquire_workspace(self, owner, replace=False):
        async with self.lock:
            if self.owner and self.owner != owner and not replace:
                raise VoiceError(409, "WORKSPACE_BUSY", "另一窗口正在控制，请明确接管")
            if self.owner and self.owner != owner:
                self.invalidate(self.generation + 1)
            self.owner = owner
            self.workspace_explicit = True
            self.workspace_deadline = time.monotonic() + self.workspace_lease_seconds
            return {"owner": True, "generation": self.generation,
                    "voice_connected": bool(self.voice_owner == owner and self.voice.session)}

    async def settings(self, owner, generation, routing, answer_upload=None, speech=None):
        async with self.lock:
            self.require_voice(owner)
            # Revocation/cancellation must not depend on catalogue availability.
            self.advance(owner, generation)
            self.routing = await self.voice.routing(routing)
            self.speech = None
            self.turn = 0
            if answer_upload is not None:
                self.answer_upload = bool(answer_upload)
            if speech is not None:
                caps = await self.voice.capabilities()
                cloud = caps.get("cloud", {})
                if routing["tts"] == "cloud":
                    voices = cloud.get("voices", [])
                    if speech["cloud_voice"] not in [item["id"] for item in voices]:
                        raise VoiceError(422, "VOICE_INVALID", "音色不在服务列表中，请刷新或更新语音服务")
                    if speech["speed"] != 1.0:
                        raise VoiceError(422, "CLOUD_SPEED", "当前云端接口仅支持自然语速 1.0×")
                elif speech["speaker_id"] not in [item["id"] for item in caps.get("tts", {}).get("speakers", [])]:
                    raise VoiceError(422, "VOICE_INVALID", "请选择服务提供的本地音色")
                speech = dict(speech, request_voice=bool(cloud.get("request_voice")))
            self.speech = speech
            # Changing modes ends the old turn even if its cancel was delayed.
            self.turn = await self.voice.turn()
            return {"routing": self.routing}

    def answer_capability(self):
        if self.answer is None:
            return {"enabled": False, "reason": "未配置回答服务；当前为跟读/朗读模式"}
        return self.answer.capability()

    async def ask(self, owner, generation, text):
        self.check(owner, generation)
        if not self.answer_upload:
            raise VoiceError(403, "ANSWER_UPLOAD_DENIED", "请单独允许向回答服务发送文字")
        capability = self.answer_capability()
        if not capability["enabled"]:
            raise VoiceError(503, "ANSWER_UNAVAILABLE", capability["reason"])
        task = asyncio.current_task()
        self.answer_tasks.add(task)
        self.phase = "generating"
        self.robot.show("processing", generation)
        try:
            result = await self.answer.complete(text, list(self.answer_history))
            self.check(owner, generation)
            self.answer_history.extend(({"role": "user", "content": text}, {"role": "assistant", "content": result}))
            if self.answer_history_limit:
                self.answer_history = self.answer_history[-self.answer_history_limit:]
            else:
                self.answer_history.clear()
            self.text, self.phase = result, "ready"
            self.robot.show("idle", generation, result)
            return result
        except asyncio.CancelledError as exc:
            raise VoiceError(409, "STALE_GENERATION", "旧回答已取消") from exc
        finally:
            self.answer_tasks.discard(task)

    def clear_answer_history(self, owner):
        self.require_voice(owner)
        self.answer_history.clear()
        return {"cleared": True}

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

    async def desktop_stop(self):
        async with self.lock:
            if self.owner:
                self.invalidate(self.generation + 1)
            with contextlib.suppress(Exception):
                await self.robot.cancel_audio()
            with contextlib.suppress(Exception):
                await self.robot.stop_sound()
            return {"generation": self.generation, "status": "stopped"}

    def desktop_state(self):
        if self.character_bubble_deadline and time.monotonic() >= self.character_bubble_deadline:
            self.character["bubble"] = ""
            self.character_bubble_deadline = 0.0
            self.character["revision"] += 1
        return {"phase": self.phase, "robot": self.robot.snapshot(),
                "workspace_active": bool(self.owner), "session_active": bool(self.voice_owner and self.voice.session),
                "character": dict(self.character)}

    async def play_character(self, owner, expression, mode, target):
        self.authorize(owner)
        if expression not in BLE_EXPRESSIONS:
            raise VoiceError(422, "EXPRESSION_INVALID", "请选择目录中的角色表情")
        if mode not in ("once", "loop") or target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_REQUEST_INVALID", "角色目标或播放方式无效")
        if expression == "happy-work" and target in ("desktop", "both"):
            raise VoiceError(422, "WATCH_ONLY_EXPRESSION", "happy-work 仅支持 StopWatch")
        result = {"desktop": {"requested": target in ("desktop", "both"), "accepted": False},
                  "watch": {"requested": target in ("watch", "both"), "accepted": False}}
        if target in ("desktop", "both"):
            self.character.update(expression=expression, mode=mode, manual=True, revision=self.character["revision"] + 1)
            result["desktop"]["accepted"] = True
        if target in ("watch", "both"):
            try:
                result["watch"].update(await self.robot.play_expression(expression, mode))
                result["watch"]["accepted"] = True
            except Exception as exc:
                result["watch"]["error"] = str(exc)
        return result

    async def restore_character_auto(self, owner):
        self.authorize(owner)
        self.character.update(expression="idle", mode="loop", manual=False, revision=self.character["revision"] + 1)
        return {"desktop": {"requested": True, "accepted": True}}

    async def set_character_bubble(self, owner, text, target):
        self.authorize(owner)
        if not text or len(text) > 300 or any(not c.isprintable() and c not in "\n\r" for c in text):
            raise VoiceError(422, "BUBBLE_INVALID", "气泡需为 1–300 个可显示字符")
        if target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_TARGET_INVALID", "请选择桌面、StopWatch 或两端")
        result = {"desktop": {"requested": target in ("desktop", "both"), "accepted": False},
                  "watch": {"requested": target in ("watch", "both"), "accepted": False}}
        if target in ("desktop", "both"):
            self.character.update(bubble=text, revision=self.character["revision"] + 1)
            self.character_bubble_deadline = time.monotonic() + 8
            result["desktop"]["accepted"] = True
        if target in ("watch", "both"):
            try:
                result["watch"].update(await self.robot.set_bubble(text))
                result["watch"]["accepted"] = True
            except Exception as exc:
                result["watch"]["error"] = str(exc)
        return result

    async def clear_character_bubble(self, owner, target):
        self.authorize(owner)
        if target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_TARGET_INVALID", "请选择桌面、StopWatch 或两端")
        result = {"desktop": {"requested": target in ("desktop", "both"), "accepted": False},
                  "watch": {"requested": target in ("watch", "both"), "accepted": False}}
        if target in ("desktop", "both"):
            self.character.update(bubble="", revision=self.character["revision"] + 1)
            self.character_bubble_deadline = 0.0
            result["desktop"]["accepted"] = True
        if target in ("watch", "both"):
            try:
                result["watch"].update(await self.robot.clear_bubble())
                result["watch"]["accepted"] = True
            except Exception as exc:
                result["watch"]["error"] = str(exc)
        return result

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
                result = await self.voice.synthesize(value, turn, request_id, self.speech)
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
        self.require_voice(owner)
        try:
            await self.voice.alive()
        except VoiceError:
            if owner == self.owner:
                self.invalidate(self.generation + 1)
                self.voice_owner = None
            raise
        self.authorize(owner)
        self.renew_workspace(owner)
        return {"generation": self.generation, "phase": self.phase, "robot": self.robot.snapshot()}

    async def release(self, owner):
        async with self.lock:
            self.require_voice(owner)
            self.advance(owner, self.generation + 1)
            try:
                await self.voice.release()
            finally:
                self.voice_owner = None
                self.answer_upload = False
                self.answer_history.clear()

    async def release_workspace(self, owner):
        async with self.lock:
            self.authorize(owner)
            self.invalidate(self.generation + 1)
            if self.voice_owner == owner and self.voice.session:
                with contextlib.suppress(VoiceError):
                    await self.voice.release()
            self.owner = None
            self.voice_owner = None
            self.workspace_explicit = False
            self.workspace_deadline = 0.0
            self.answer_upload = False
            self.answer_history.clear()

    async def release_voice(self, owner):
        async with self.lock:
            self.require_voice(owner)
            self.invalidate(self.generation + 1)
            try:
                await self.voice.release()
            finally:
                self.voice_owner = None
                self.answer_upload = False
                self.answer_history.clear()

    async def close(self):
        for task in tuple(self.answer_tasks):
            task.cancel()
        if self.answer_tasks:
            await asyncio.gather(*self.answer_tasks, return_exceptions=True)
        await self.voice.close()
        if self.cleanup:
            await asyncio.gather(*self.cleanup, return_exceptions=True)
        await self.robot.close()
        if self.answer is not None:
            await self.answer.close()
