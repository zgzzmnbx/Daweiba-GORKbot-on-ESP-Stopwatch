"""Session ownership and monotonic UI generations; no transcript retention."""
import asyncio
import contextlib
import time
from pathlib import Path
import sys
import wave

from .voice import VoiceError
from .notification_coordinator import NotificationCoordinator
from .watch_dialogue import WatchDialogue
from .motion import watch_token
from . import speech_cache


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
        self.watch_speech_generation = None
        self.routing = dict(SAFE_ROUTING)
        self.lock = asyncio.Lock()
        self.pending = {}
        self.cleanup = set()
        self.answer_upload = False
        self.answer_history = []
        self.answer_history_limit = max(0, min(10, int(answer_history_turns))) * 2
        self.answer_tasks = set()
        self.motion_library=None
        self.answer_motion=None
        self.answer_motion_generation=None
        self.answer_motion_revision=0
        self.record_motion=None
        self.record_motion_generation=None
        self.record_motion_revision=0
        self.answer_read_motion=None;self.answer_read_generation=None
        self.answer_read_continuing=False
        self.interaction_identity=None;self.interaction_revision=0
        self.speech = None
        self.last_speech_output=None
        self.fixed_speech_hits=0
        self.fixed_speech_misses=0
        self.fixed_speech_warmup={'state':'idle','generated':0}
        self.fixed_speech_lock=asyncio.Lock()
        self.character = {"expression": "idle", "mode": "loop", "bubble": "", "manual": False, "revision": 0}
        self.character_bubble_deadline = 0.0
        self.manual_until = 0.0
        self.task_monitor = None
        self.external_notifications = None
        self.output_target = "pc"
        self.codex_monitor = None
        self.codex_spool = Path(__file__).resolve().parents[3] / 'Codex-Temp' / 'codex-sentinel-hook-queue'
        self.notifications = NotificationCoordinator(self)
        self.watch_dialogue=WatchDialogue(self) if hasattr(robot,'network') else None

    async def play_auto_tone(self, guard):
        if sys.platform != 'win32' or not guard():
            return 'unavailable' if guard() else 'suppressed'
        import winsound
        path = Path(__file__).resolve().parents[3] / '01-assets' / 'audio' / 'source' / '02-confirm.wav'
        if not path.is_file():
            return 'failed'
        try:
            with wave.open(str(path), 'rb') as sound:
                duration = min(2.0, sound.getnframes() / sound.getframerate())
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            await asyncio.sleep(duration)
            return 'started_by_os' if guard() else 'suppressed'
        except asyncio.CancelledError:
            winsound.PlaySound(None, 0)
            raise
        except Exception:
            return 'failed'

    def stop_auto_tone(self):
        if sys.platform == 'win32':
            import winsound
            with contextlib.suppress(Exception):
                winsound.PlaySound(None, 0)

    async def synthesize_auto_speech(self, text, guard):
        """Use the current voice session and selected tone, without taking over.

        NotificationCoordinator serializes reminders. Register this request in
        the normal cancellation map so a manual turn/revocation can invalidate
        it; never change the user's phase, generation, text, or output choice.
        """
        async with self.lock:
            if not guard() or not self.auto_available() or self.pending or self.answer_tasks:
                raise VoiceError(409, 'AUTO_SUPPRESSED', '人工语音操作优先')
            if not self.owner or self.voice_owner != self.owner or not self.voice.session:
                raise VoiceError(409, 'VOICE_SESSION_REQUIRED', '语音播报需要当前语音会话')
            if self.routing['tts'] == 'cloud' and not self.routing['allow_text_upload']:
                raise VoiceError(403, 'UPLOAD_NOT_ALLOWED', '云端播报未获文字上传许可')
            generation, session, owner = self.generation, self.voice.session, self.owner
            speech = dict(self.speech or {})
            turn = self.turn or await self.voice.turn()
            if not guard():
                raise VoiceError(409, 'AUTO_SUPPRESSED', '提醒已失效')
            request_id = self.voice.request_id('auto_tts')
            self.pending[request_id] = (turn, session, generation)
        try:
            result = await self.voice.synthesize(text, turn, request_id, speech)
            if (not guard() or owner != self.owner or session != self.voice.session
                    or generation != self.generation
                    or self.routing['tts'] == 'cloud' and not self.routing['allow_text_upload']):
                raise VoiceError(409, 'AUTO_SUPPRESSED', '提醒已失效，本次未播放')
            observed=getattr(self.voice,'last_voice',None)
            self.last_speech_output={**(observed if observed and observed.get('request_id')==request_id else
                                       {'mode':self.routing['tts'],'requested':speech.get('cloud_voice','')}),
                                     'cache_hit':False}
            return result
        except asyncio.CancelledError:
            await self.cancel_one(request_id, turn, session)
            raise
        finally:
            self.pending.pop(request_id, None)

    async def fixed_speech_profile(self):
        """Read public synthesis identity, never credentials or user transcripts."""
        cloud=(await self.voice.capabilities()).get('cloud', {})
        speech=self.speech or {}
        voice=(speech.get('cloud_voice') if speech.get('request_voice') else None) or cloud.get('default_voice')
        if self.routing.get('tts') != 'cloud' or not cloud.get('tts_model') or not voice:
            raise VoiceError(409,'CACHE_PROFILE_UNAVAILABLE','请先应用云端音色设置')
        return {'route':'cloud', 'model':cloud['tts_model'], 'region':cloud.get('region',''),
                'voice':voice, 'speed':speech.get('speed',1.0), 'sample_rate':24000,
                'voice_protocol':(await self.voice.health()).get('version','')}

    async def fixed_speech(self, text, guard, *, cached_only=False, force=False):
        """Reuse exact rendered text, including amounts/counts, with the current voice."""
        if not speech_cache.cacheable_text(text):
            # Unresolved templates cannot stand in for an actual rendered value.
            return await self.synthesize_auto_speech(text,guard)
        owner,session,generation,speech=self.owner,self.voice.session,self.generation,dict(self.speech or {})
        def valid():
            return (guard() and self.owner==owner and self.voice_owner==owner and self.voice.session==session
                    and self.generation==generation and dict(self.speech or {})==speech and self.auto_available()
                    and self.routing.get('tts')=='cloud' and self.routing.get('allow_text_upload') is True)
        if not valid() or not owner or not session or self.pending or self.answer_tasks:
            raise VoiceError(409,'AUTO_SUPPRESSED','当前语音会话或许可不可用')
        try:
            profile=await self.fixed_speech_profile()
        except VoiceError as error:
            if cached_only or error.code!='CACHE_PROFILE_UNAVAILABLE':
                raise
            return await self.synthesize_auto_speech(text,valid)
        audio=None if force else await asyncio.to_thread(speech_cache.read,text,profile)
        if not valid():
            raise VoiceError(409,'AUTO_SUPPRESSED','语音设置已变化，提醒已取消')
        if audio is not None:
            self.fixed_speech_hits+=1
            self.last_speech_output={'mode':'cloud','requested':profile['voice'],'rendered':profile['voice'],
                                     'provider':profile['model'],'cache_hit':True}
            return audio
        if cached_only:
            raise VoiceError(404,'CACHE_MISSING','当前音色的这段播报尚未生成')
        self.fixed_speech_misses+=1
        audio=await self.synthesize_auto_speech(text,valid)
        if not valid() or await self.fixed_speech_profile() != profile or not valid():
            raise VoiceError(409,'AUTO_SUPPRESSED','已取消，未保存迟到语音')
        try:
            # Short synchronous atomic writes prevent generation changes between validation and persistence.
            speech_cache.save(text,profile,audio)
        except (OSError, ValueError):
            pass  # Cache failure or Watch length limits must not break a valid live PC synthesis.
        self.last_speech_output={'mode':'cloud','requested':profile['voice'],'rendered':profile['voice'],
                                 'provider':profile['model'],'cache_hit':False}
        return audio

    async def warm_fixed_speech(self, entries, *, force=False):
        """Low priority synthesis only; never display, play or send to a device."""
        owner,session,generation=self.owner,self.voice.session,self.generation
        profile=await self.fixed_speech_profile()
        def valid():
            return (bool(owner) and self.owner==owner and self.voice_owner==owner
                    and self.voice.session==session and self.generation==generation
                    and self.routing.get('tts')=='cloud' and self.routing.get('allow_text_upload') is True)
        generated=[]
        async with self.fixed_speech_lock:
            self.fixed_speech_warmup={'state':'generating','generated':0}
            try:
                for item_id,_,text in entries:
                    if not valid() or await self.fixed_speech_profile()!=profile:
                        raise VoiceError(409,'VOICE_LIBRARY_CHANGED','音色或许可已变化，已停止生成')
                    if not force and await asyncio.to_thread(speech_cache.read,text,profile) is not None:
                        continue
                    async def synthesize():
                        await self.fixed_speech(text,valid,force=force)
                    done=await self.notifications.dispatch(source='voice-library',priority=0,valid=valid,action=synthesize,ttl=120)
                    if not done:
                        raise VoiceError(409,'VOICE_LIBRARY_CHANGED','生成已取消或等待超时')
                    generated.append(item_id)
                    self.fixed_speech_warmup['generated']=len(generated)
                self.fixed_speech_warmup['state']='ready'
                return generated
            except BaseException:
                self.fixed_speech_warmup['state']='stopped'
                raise

    def auto_block_reason(self):
        audio = self.robot.audio_snapshot() if hasattr(self.robot, 'audio_snapshot') else {}
        if self.phase in {'listening', 'processing', 'generating', 'speaking'}:
            return '语音操作进行中'
        if audio.get('running'):
            return 'Watch 音频进行中'
        if time.monotonic() < self.manual_until:
            return '人工角色操作优先'
        return ''

    def auto_available(self):
        # A manual pose remains the idle preference, but it must not disable
        # an explicitly enabled sentinel forever. The recent action has a
        # bounded priority window; after it, automatic task cues may resume.
        return not self.auto_block_reason()

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
        if self.external_notifications:
            self.external_notifications.manual_started()
        if self.watch_dialogue:self.watch_dialogue.invalidate()
        self.generation = generation
        self.phase = "idle"
        self.record_motion=None;self.record_motion_generation=None
        self.answer_read_motion=None;self.answer_read_generation=None
        self.answer_read_continuing=False
        self.text = ""
        self.watch_speech_generation = None
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
            if not replace and self.owner == owner and self.voice_owner == owner and self.voice.session:
                try:
                    await self.voice.alive()
                    self.renew_workspace(owner)
                    return {"generation": self.generation, "routing": self.routing, "resumed": True}
                except VoiceError as exc:
                    if exc.status != 401:
                        raise
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
            self.watch_speech_generation = None
            self.answer_upload = False
            self.speech = None
            self.answer_history.clear()
            self.last_speech_output=None
            # Robot generations span multiple browser sessions.
            self.robot.generation = 0
            self.robot.show("idle", 0)
            return {"generation": 0, "routing": self.routing}

    async def acquire_workspace(self, owner, replace=False):
        async with self.lock:
            if self.workspace_explicit and self.workspace_deadline <= time.monotonic():
                self.owner = None
                self.voice_owner = None
                self.workspace_explicit = False
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
            previous_speech=self.speech
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
            elif previous_speech is not None:
                # Permission-only updates contain no voice draft. Revocation
                # still happens first and never depends on catalogue health.
                speech=dict(previous_speech)
                if routing['tts']=='cloud':speech['speed']=1.0
            self.speech = speech
            # Changing modes ends the old turn even if its cancel was delayed.
            self.turn = await self.voice.turn()
            return {"routing": self.routing}

    def answer_capability(self):
        if self.answer is None:
            return {"enabled": False, "reason": "未配置回答服务；当前为跟读/朗读模式"}
        return self.answer.capability()

    async def named_motion(self,name,scene):
        if self.motion_library is not None:
            with contextlib.suppress(OSError,ValueError):
                library=await asyncio.to_thread(self.motion_library.read)
                return next((entry for entry in library['entries'] if entry['name']==name and entry['scene']==scene),None)
        return None

    def interaction_motion(self):
        motion=None
        if self.answer_motion and self.phase=='generating' and self.answer_motion_generation==self.generation:
            motion=self.answer_motion
        elif self.watch_dialogue and self.watch_dialogue.owner and self.watch_dialogue.motion:
            motion=self.watch_dialogue.motion
        elif self.phase=='listening' and self.record_motion_generation==self.generation:
            motion=self.record_motion
        elif (self.phase in ('processing','speaking') or self.phase=='ready' and self.answer_read_continuing) and self.answer_read_generation==self.generation:
            motion=self.answer_read_motion
        identity=(self.generation,watch_token(motion)) if motion else None
        if identity!=self.interaction_identity:
            self.interaction_identity=identity;self.interaction_revision+=1
        return motion

    async def ask(self, owner, generation, text, defer_watch_text=False, *, short=False, speech_pending=False):
        self.check(owner, generation)
        if not self.answer_upload:
            raise VoiceError(403, "ANSWER_UPLOAD_DENIED", "请单独允许向回答服务发送文字")
        capability = self.answer_capability()
        if not capability["enabled"]:
            raise VoiceError(503, "ANSWER_UNAVAILABLE", capability["reason"])
        task = asyncio.current_task()
        self.answer_tasks.add(task)
        self.phase = "generating"
        try:
            entry=await self.named_motion('我的书写','writing')
            self.check(owner,generation)
            self.answer_motion,self.answer_motion_generation=entry,generation
            self.answer_motion_revision+=1
            delegated=defer_watch_text and self.watch_dialogue and self.watch_dialogue.motion_task is task
            if delegated:
                self.watch_dialogue.motion=entry;self.watch_dialogue.motion_revision+=1
            if entry:self.robot.show('processing',generation,expression='loop '+watch_token(entry))
            else:self.robot.show('processing',generation)
            result = await self.answer.complete(text, list(self.answer_history),short=True) if short else await self.answer.complete(text, list(self.answer_history))
            self.check(owner, generation)
            self.answer_history.extend(({"role": "user", "content": text}, {"role": "assistant", "content": result}))
            if self.answer_history_limit:
                self.answer_history = self.answer_history[-self.answer_history_limit:]
            else:
                self.answer_history.clear()
            self.text, self.phase = result, "ready"
            self.answer_read_motion=entry;self.answer_read_generation=generation
            self.answer_read_continuing=bool(entry and (delegated or speech_pending))
            self.character.update(bubble=result,revision=self.character['revision']+1)
            self.character_bubble_deadline=time.monotonic()+min(45,max(8,len(result)*.12))
            keep_motion=self.answer_read_continuing
            self.robot.show("idle", generation, "" if defer_watch_text else result,
                **({'expression':'loop '+watch_token(entry)} if keep_motion else {}))
            return result
        except asyncio.CancelledError as exc:
            raise VoiceError(409, "STALE_GENERATION", "旧回答已取消") from exc
        finally:
            if self.answer_motion_generation==generation:
                self.answer_motion=None;self.answer_motion_generation=None
                if self.phase=='generating':self.robot.show('idle',generation)
            self.answer_tasks.discard(task)

    def clear_answer_history(self, owner):
        self.require_voice(owner)
        if self.watch_dialogue:
            self.invalidate(self.generation+1)
            watch_history=self.watch_dialogue.clear_history()
        else:watch_history={}
        self.answer_history.clear()
        return {"cleared": True,"generation":self.generation,**watch_history}

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
        if self.external_notifications:
            await self.external_notifications.stop()
        if self.task_monitor:
            await self.task_monitor.stop()
        if self.codex_monitor:
            await self.codex_monitor.stop()
        self.notifications.clear()
        self.stop_auto_tone()
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
        character = dict(self.character)
        monitor = self.task_monitor
        if monitor and monitor.enabled and self.auto_available():
            presentation = monitor.presentation
            if presentation and time.monotonic() < presentation['until']:
                character.update(expression=presentation['expression'], bubble=presentation['bubble'],
                                 revision=character['revision'] + monitor.epoch + len(monitor.history) + 1,
                                 auto=True)
            elif not monitor.connection_error and monitor.current and monitor.current['activity']['status'] == 'running':
                character.update(expression='working', bubble='',
                                 revision=character['revision'] + monitor.epoch + len(monitor.history) + 1,
                                 auto=True)
        codex = self.codex_monitor
        if (codex and codex.enabled and codex.target in ('desktop', 'both')
                and codex.state()['current'] and codex.state()['current']['status'] == 'running'
                and self.auto_available() and not self.notifications.current()
                and not (monitor and monitor.enabled and monitor.current
                         and monitor.current['activity']['status'] == 'running')):
            character.update(expression='working', bubble='',
                             revision=character['revision'] + codex.epoch + len(codex.history) + 30000,
                             auto=True)
        presentation = self.notifications.current()
        if presentation and self.auto_available():
            character.update(bubble=presentation['bubble'],
                             revision=character['revision'] + presentation['revision'] + 10000,
                             dismissOnClick=presentation['dismiss_on_click'])
            if presentation['expression']:
                character.update(expression=presentation['expression'], auto=True,
                                 mode=presentation.get('mode', 'once'),
                                 custom_motion=presentation.get('custom_motion'))
        external = self.external_notifications.current() if self.external_notifications and self.external_notifications.visual_available() else None
        if external and (not presentation or external['priority'] >= presentation['priority']):
            character.update(expression=external['expression'], bubble=external['bubble'], mode=external['mode'],
                             custom_motion=external['custom_motion'], revision=external['revision'], auto=True)
        motion=self.interaction_motion()
        if motion:
            character.update(expression=motion['id'],mode='loop',custom_motion=motion,auto=True,
                revision=200000+self.interaction_revision)
        return {"phase": self.phase, "robot": self.robot.snapshot(),
                "workspace_active": bool(self.owner), "session_active": bool(self.voice_owner and self.voice.session),
                "character": character,
                "codex": self.codex_monitor.desktop_summary() if self.codex_monitor else {'enabled': False}}

    async def play_character(self, owner, expression, mode, target, custom_entry=None):
        self.authorize(owner)
        self.manual_until = time.monotonic() + 15
        if expression not in BLE_EXPRESSIONS and not (custom_entry and custom_entry['id'] == expression):
            raise VoiceError(422, "EXPRESSION_INVALID", "请选择目录中的角色表情")
        if mode not in ("once", "loop") or target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_REQUEST_INVALID", "角色目标或播放方式无效")
        if expression == "happy-work" and target in ("desktop", "both"):
            raise VoiceError(422, "WATCH_ONLY_EXPRESSION", "happy-work 仅支持 StopWatch")
        if self.external_notifications:
            await self.external_notifications.yield_to_manual()
        result = {"desktop": {"requested": target in ("desktop", "both"), "accepted": False},
                  "watch": {"requested": target in ("watch", "both"), "accepted": False}}
        if target in ("desktop", "both"):
            self.character.update(expression=expression, mode=mode, manual=True, custom_motion=custom_entry, revision=self.character["revision"] + 1)
            result["desktop"]["accepted"] = True
        if target in ("watch", "both"):
            try:
                result["watch"].update(await self.robot.play_expression(watch_token(custom_entry) if custom_entry else expression, mode))
                result["watch"]["accepted"] = True
            except Exception as exc:
                result["watch"]["error"] = ('Watch 未能播放该自定义表情；请确认连接，并烧录包含当前参数的固件。' if custom_entry else str(exc))
        return result

    async def restore_character_auto(self, owner):
        self.authorize(owner)
        self.manual_until = 0.0
        self.character.update(expression="idle", mode="loop", manual=False, custom_motion=None, revision=self.character["revision"] + 1)
        return {"desktop": {"requested": True, "accepted": True}}

    async def set_character_bubble(self, owner, text, target):
        self.authorize(owner)
        self.manual_until = time.monotonic() + 15
        if not text or len(text) > 300 or any(not c.isprintable() and c not in "\n\r" for c in text):
            raise VoiceError(422, "BUBBLE_INVALID", "气泡需为 1–300 个可显示字符")
        if target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_TARGET_INVALID", "请选择桌面、StopWatch 或两端")
        if self.external_notifications:
            await self.external_notifications.yield_to_manual()
        result = {"desktop": {"requested": target in ("desktop", "both"), "accepted": False},
                  "watch": {"requested": target in ("watch", "both"), "accepted": False}}
        if target in ("desktop", "both"):
            self.character.update(bubble=text, revision=self.character["revision"] + 1)
            self.character_bubble_deadline = time.monotonic() + min(45, max(8, len(text) * 0.12))
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
        self.manual_until = time.monotonic() + 15
        if target not in ("desktop", "watch", "both"):
            raise VoiceError(422, "CHARACTER_TARGET_INVALID", "请选择桌面、StopWatch 或两端")
        if self.external_notifications:
            await self.external_notifications.yield_to_manual()
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
        entry=await self.named_motion('我的疑惑','question') if phase=='listening' else None
        if phase=='speaking' and self.answer_read_generation==generation:entry=self.answer_read_motion
        self.check(owner,generation)
        self.record_motion=entry;self.record_motion_generation=generation if entry else None
        self.record_motion_revision+=1
        retained_text=getattr(self.robot,'text','') if phase=='idle' and self.answer_read_continuing else ''
        if phase=='idle':
            self.answer_read_motion=None;self.answer_read_generation=None;self.answer_read_continuing=False
        self.phase = phase
        self.robot.show(phase, generation, self.text if phase == "speaking" else retained_text,
            **({'expression':'loop '+watch_token(entry)} if entry else {}))

    async def perform(self, owner, generation, kind, value, watch_speech=False):
        self.check(owner, generation)
        if kind == "tts":
            self.watch_speech_generation = None
        if not self.turn:
            raise VoiceError(409, "NO_TURN", "请先开始新一轮")
        if any(item[2] == generation for item in self.pending.values()):
            raise VoiceError(409, "REQUEST_BUSY", "上一请求尚未结束，请停止后重试")
        request_id = self.voice.request_id(kind)
        turn, session = self.turn, self.voice.session
        self.pending[request_id] = (turn, session, generation)
        self.phase = "processing"
        delegated=watch_speech and self.watch_dialogue and self.watch_dialogue.motion_task is asyncio.current_task()
        motion=self.watch_dialogue.motion if delegated else None
        if not motion and kind=='tts' and self.answer_read_generation==generation and value==self.text:motion=self.answer_read_motion
        self.robot.show("processing", generation,**({'expression':'loop '+watch_token(motion)} if motion else {}))
        try:
            if kind == "asr":
                result = await self.voice.transcribe(value, turn, request_id)
            else:
                result = await self.voice.synthesize(value, turn, request_id, self.speech)
            self.check(owner, generation)
            if kind=='tts':
                observed=getattr(self.voice,'last_voice',None)
                if observed and observed.get('request_id')==request_id:self.last_speech_output=dict(observed)
            self.phase = "ready"
            self.text = result if kind == "asr" else value
            self.watch_speech_generation = generation if kind == "tts" and watch_speech else None
            self.robot.show("idle", generation, "" if watch_speech else self.text,
                **({'expression':'loop '+watch_token(motion)} if motion else {}))
            return result
        except VoiceError:
            if owner == self.owner and generation == self.generation:
                self.phase = "error"
                self.robot.show("error", generation)
            raise
        finally:
            self.pending.pop(request_id, None)

    def take_watch_speech_text(self, owner, generation):
        self.check(owner, generation)
        if self.watch_speech_generation != generation or not self.text:
            raise VoiceError(409, "WATCH_SPEECH_MISSING", "请先合成当前这轮 Watch 朗读语音")
        self.watch_speech_generation = None
        return self.text

    async def heartbeat(self, owner):
        self.require_voice(owner)
        session = self.voice.session
        try:
            await self.voice.alive()
        except VoiceError as exc:
            if exc.status == 401 and owner == self.owner and self.voice.session in (None, session):
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
        if self.watch_dialogue:await self.watch_dialogue.disable()
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
