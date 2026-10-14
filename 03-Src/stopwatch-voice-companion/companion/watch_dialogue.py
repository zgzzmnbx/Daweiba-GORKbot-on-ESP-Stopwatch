"""Explicit browser-owned device delegation using the existing voice engine,
permissions, generation, request cancellation and Watch playback pipeline."""
import asyncio
import contextlib
import time
import uuid
from .voice import VoiceError

class WatchDialogue:
    def __init__(self,control):
        self.control=control;self.owner=None;self.task=None;self.turn_task=None
        self.stage='disabled';self.error='';self.recognized='';self.answer='';self.timings={};self.link=None
        self.lease_task=None
        self.pending_short=False
        self.turns=[];self.current_turn=None;self.history_id=str(uuid.uuid4());self.history_revision=0
        self.gesture=asyncio.Event()
        self.gesture_started=None
        self.motion=None;self.motion_revision=0;self.motion_task=None
        self.voice={}
        control.robot.network.voice_event=self.device_event
    def device_event(self,code):
        if not self.owner:return
        if code in (1,2):
            self.control.invalidate(self.control.generation+1)
            if code==1:
                self.gesture_started=time.monotonic()
                self.control.manual_until=time.monotonic()+15
                self.gesture.set()
            else:self.gesture.clear()
    def snapshot(self):
        return dict(enabled=bool(self.owner),stage=self.stage,error=self.error,recognized=self.recognized,answer=self.answer,timings=self.timings,generation=self.control.generation,
            history_id=self.history_id,history_revision=self.history_revision,
            turns=[{**turn,'timings':dict(turn['timings'])} for turn in self.turns])
    def publish(self):
        if self.current_turn is not None:
            self.current_turn.update(recognized=self.recognized,answer=self.answer,stage=self.stage,timings=dict(self.timings),voice=dict(self.voice))
            self.history_revision+=1
    def clear_history(self):
        self.turns.clear();self.current_turn=None
        self.pending_short=False;self.gesture.clear()
        self.recognized=self.answer='';self.timings={};self.history_revision+=1
        return dict(history_id=self.history_id,history_revision=self.history_revision)
    def permitted(self):
        c=self.control;c.require_voice(self.owner)
        if c.routing['asr']=='cloud' and not c.routing['allow_audio_upload']:raise VoiceError(403,'AUDIO_UPLOAD_DENIED','请在电脑设置音频上传许可')
        if c.routing['tts']=='cloud' and not c.routing['allow_text_upload']:raise VoiceError(403,'TEXT_UPLOAD_DENIED','请在电脑设置朗读文字上传许可')
        if not c.answer_upload:raise VoiceError(403,'ANSWER_UPLOAD_DENIED','请单独允许向回答服务发送文字')
        if not c.answer_capability()['enabled']:raise VoiceError(503,'ANSWER_UNAVAILABLE',c.answer_capability()['reason'])
    async def enable(self,owner,enabled):
        self.control.authorize(owner)
        if enabled:self.control.require_voice(owner)
        await self.disable()
        if enabled:
            self.owner=owner
            try:self.permitted()
            except VoiceError as exc:
                self.error=str(exc);self.owner=None;raise
            except BaseException:self.owner=None;raise
            self.error='';self.stage='ready'
            self.task=asyncio.create_task(self.run())
            self.lease_task=asyncio.create_task(self.lease())
        return self.snapshot()
    async def disable(self):
        self.owner=None
        self.motion=None
        self.gesture.clear()
        if self.lease_task:
            self.lease_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.lease_task
            self.lease_task=None
        with contextlib.suppress(Exception):await self.control.robot.network.delegate(False)
        for task in (self.turn_task,self.task):
            if task and task is not asyncio.current_task() and not task.done():task.cancel()
        for task in (self.turn_task,self.task):
            if task and task is not asyncio.current_task():
                with contextlib.suppress(asyncio.CancelledError,VoiceError):await task
        self.task=self.turn_task=None;self.stage='disabled';self.error=''
        await self.control.robot.cancel_audio()
        await self.control.robot.close_prepared_audio()
        self.control.robot.dialogue_pinned=False;self.control.robot.network.router.end()
    def invalidate(self):
        # Stops/releases/settings use the same generation boundary as browser
        # speech. A new delegated begin must not cancel itself.
        if self.turn_task and self.turn_task is not asyncio.current_task():
            self.motion=None;self.turn_task.cancel()
    async def lease(self):
        try:
            while self.owner:
                self.permitted()
                try:await self.control.robot.network.delegate(True)
                except Exception:self.invalidate()
                if not self.turn_task or self.turn_task.done():
                    with contextlib.suppress(Exception):await self.control.robot.prepare_audio()
                await asyncio.sleep(2)
        except VoiceError as exc:
            self.error=str(exc)
            self.owner=None;self.gesture.set()
            self.invalidate()
            with contextlib.suppress(Exception):await self.control.robot.network.delegate(False)
        except asyncio.CancelledError:
            self.invalidate()
    async def checked(self, awaitable):
        result=await awaitable
        self.permitted()
        robot=self.control.robot
        route=robot.network.router.active
        if route=='wifi' and not robot.network.wifi.connected:raise ConnectionError('Wi-Fi 中断，本轮结束')
        if route=='ble' and not robot.client.connected:raise ConnectionError('BLE 中断，本轮结束')
        return result
    async def one(self):
        task=asyncio.current_task();self.motion_task=task
        try:
            return await self._one()
        finally:
            if self.motion_task is task:
                self.motion=None;self.motion_task=None
                self.control.answer_read_motion=None;self.control.answer_read_generation=None
                self.control.answer_read_continuing=False
                robot=self.control.robot
                robot.show('idle',self.control.generation,robot.text)

    async def _one(self):
        c=self.control;r=c.robot;self.permitted()
        # A physical begin preempts a sentinel/diagnostic playback through its
        # existing cancel path before choosing this new conversation's route.
        r.dialogue_pinned=False
        await r.cancel_audio()
        r.network.router.end()
        r.dialogue_pinned=True;r.network.router.begin(r.client.connected,r.network.wifi)
        await r.network.delegate(True)
        self.error='';self.timings={};self.voice={}
        shorten=self.pending_short;self.pending_short=False
        if not shorten:
            self.recognized=self.answer=''
            self.current_turn=dict(id=str(uuid.uuid4()),recognized='',answer='',stage='armed',timings={})
            self.turns.append(self.current_turn);self.turns=self.turns[-20:];self.history_revision+=1
            self.stage='armed'
            self.motion=await c.named_motion('我的疑惑','question');self.motion_revision+=1
            self.permitted()
            from .motion import watch_token
            r._start_audio('productrecord',speech_expression='loop '+watch_token(self.motion) if self.motion else None)
            while not r.audio_task.done():
                self.permitted()
                progress=r.audio_progress.get('stage')
                if progress=='recording':
                    self.stage='recording';c.phase='listening'
                    c.manual_until=time.monotonic()+15
                await asyncio.sleep(.1)
            await r.audio_task
            if r.audio_error:raise ConnectionError(r.audio_error)
            if self.gesture_started is not None and r.recording_started is not None:
                self.timings['prepare']=max(0,r.recording_started-self.gesture_started)
            if r.audio_progress.get('stage')=='received':self.timings['download']=r.audio_progress.get('elapsed',0)
            wav=r.take_audio_result(r.audio_job)
        self.permitted()
        generation=c.generation+1
        await c.begin(self.owner,generation)
        if not shorten:
            started=time.monotonic();self.stage='recognizing'
            self.recognized=await self.checked(c.perform(self.owner,generation,'asr',wav,watch_speech=True))
            self.timings['asr']=time.monotonic()-started
            self.publish()
        if not self.recognized.strip():raise VoiceError(422,'EMPTY_ASR','未识别到有效语音，请重说')
        self.stage='thinking';started=time.monotonic()
        text=self.recognized if not shorten else '请用不超过20个汉字简短回答这个问题：'+self.recognized
        self.answer=await self.checked(c.ask(self.owner,generation,text,defer_watch_text=True,short=True))
        self.timings['answer']=time.monotonic()-started
        self.publish()
        self.stage='synthesizing';started=time.monotonic()
        audio=await self.checked(c.perform(self.owner,generation,'tts',self.answer,watch_speech=True))
        self.voice=dict(c.last_speech_output or {})
        self.timings['tts']=time.monotonic()-started
        self.publish()
        try:
            from stopwatch_audio import read_wav
            read_wav(audio)
        except ValueError:
            self.stage='speech_not_played';self.error='回答较长，请看电脑；音频超过10秒或格式不兼容，未播放'
            self.publish()
            await r.device_client().send_text('回答较长，请看电脑')
            return
        from .motion import watch_token
        self.stage='transferring';started=time.monotonic();r.start_audio_play(audio,speech=True,speech_text=self.answer,
            speech_expression='loop '+watch_token(self.motion) if self.motion else None)
        await self.checked(r.audio_task)
        if r.audio_error:raise ConnectionError(r.audio_error)
        self.timings['playback']=time.monotonic()-started
        for key in ('encode','send','device_play'):
            if key in r.audio_progress:self.timings[key]=r.audio_progress[key]
        first=r.audio_progress.get('first_play_at')
        if not shorten and first is not None and r.capture_stopped is not None:
            self.timings['stop_to_play']=max(0,first-r.capture_stopped)
        self.stage='completed';c.phase='ready'
        self.publish()
    async def shorten(self,owner):
        self.control.require_voice(owner)
        if owner!=self.owner or not self.recognized:raise VoiceError(409,'NO_WATCH_ANSWER','请先启用 Watch 对话并完成一轮识别')
        self.permitted();self.pending_short=True;self.control.invalidate(self.control.generation+1);self.gesture.set()
        return self.snapshot()
    async def run(self):
        try:
            while self.owner:
                self.stage='ready'
                await self.gesture.wait()
                self.gesture.clear()
                if not self.owner:break
                self.permitted()
                self.turn_task=asyncio.create_task(self.one())
                try:await self.turn_task
                except asyncio.CancelledError:
                    if not self.owner:raise
                    self.stage='cancelled'
                except Exception as exc:
                    self.stage='interrupted';self.error=str(exc)
                finally:
                    self.publish()
                    await self.control.robot.cancel_audio()
                    self.control.robot.dialogue_pinned=False;self.control.robot.network.router.end()
                    self.control.phase='ready'
                try:self.permitted()
                except VoiceError:self.owner=None;break
                # Rearm only a new physical gesture. Nothing from the preceding
                # recording/AI answer is replayed or restored after disconnect.
                # The event is cleared before each turn; no fixed rearm delay is needed.
                await asyncio.sleep(0)
        except VoiceError as exc:self.error=str(exc)
        except asyncio.CancelledError:pass
        finally:
            self.owner=None
            await self.control.robot.cancel_audio()
            await self.control.robot.close_prepared_audio()
            self.control.robot.dialogue_pinned=False;self.control.robot.network.router.end()
