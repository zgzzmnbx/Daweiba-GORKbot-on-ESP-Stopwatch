"""Production Controller/VoiceClient/Robot/AudioClient pipeline with controlled
HTTP and transport peers. These tests cannot certify a physical microphone."""
import asyncio
import json
import uuid
import struct
from types import SimpleNamespace
import httpx
import pytest
from companion.control import Controller
from companion.robot import Robot
from companion.voice import VoiceClient,VoiceError
from companion.answer import AnswerClient
from stopwatch_audio import Packet,Op,make_wav
from test_stopwatch_audio import FakeBle

class ProductBle(FakeBle):
    def __init__(self):super().__init__();self.capture=b'\1\0'*3200;self.product_arms=0;self.hellos=0;self.voice_callback=None
    async def start_notify(self,uuid,callback):
        if uuid.startswith('48f1d'):self.voice_callback=callback
        else:await super().start_notify(uuid,callback)
    async def write_gatt_char(self,uuid,raw,response):
        if uuid.startswith('48f1d'):return
        packet=Packet.decode(raw)
        if packet.op==Op.HELLO:
            self.hellos+=1
            self.send(Packet(Op.CAPS,packet.transfer,self.epoch,480000,struct.pack('<HHB',244,10,2)));return
        if packet.op==Op.PRODUCT_ARM:
            self.product_arms+=1
            self.send(Packet(Op.ACK,packet.transfer,self.epoch,0,bytes([packet.op])))
            self.send(Packet(Op.RECORDING,packet.transfer,self.epoch))
            self.send(Packet(Op.RECORDED,packet.transfer,self.epoch,len(self.capture),b'\0'));return
        return await super().write_gatt_char(uuid,raw,response)

class Device:
    def __init__(self):self.client=ProductBle();self.connected=True;self.events=[]
    async def clear_text(self):self.events.append('clear');return 'OK:CLEAR'
    async def send_command(self,command):self.events.append(command);return 'OK:APPLIED'
    async def send_text(self,text):self.events.append(text);return 'OK:TEXT'
    async def disconnect(self):self.connected=False;self.client.is_connected=False

@pytest.mark.parametrize('ending',['complete','failure','cancel'])
def test_named_record_and_answer_snapshots_span_watch_pipeline_then_restore(tmp_path,ending):
    from companion.motion import ASSETS,MotionLibrary,watch_token
    async def run():
        config=json.loads((ASSETS/'initial-config.gork.json').read_text(encoding='utf-8'))
        library=MotionLibrary(tmp_path/'expressions.json')
        question=library.save_expression('我的疑惑','question',config,1)['entry']
        writing=library.save_expression('我的书写','writing',config,2)['entry']
        tts_started=asyncio.Event();tts_gate=asyncio.Event();c=None
        async def service(request):
            if request.url.path=='/v1/sessions':return httpx.Response(200,json={'session_id':'fixture','protocol_version':1})
            if request.url.path=='/v1/settings':return httpx.Response(200,json={'routing':{'asr':'local','tts':'local','allow_audio_upload':False,'allow_text_upload':False}})
            if request.url.path.endswith('/turns'):return httpx.Response(200,json={'turn_id':1})
            if request.url.path=='/v1/asr/transcribe':
                assert 'loop '+watch_token(question) in d.events
                assert c.desktop_state()['character']['custom_motion']==question
                return httpx.Response(200,json={'result':{'text':'你好'}})
            if request.url.path=='/v1/tts/synthesize':
                assert c.desktop_state()['character']['custom_motion']==writing
                assert c.interaction_motion()==writing
                await r.flush()
                tts_started.set();await tts_gate.wait()
                if ending=='failure':return httpx.Response(503,json={'error':{'code':'FIXTURE','message':'failed'}})
                return httpx.Response(200,content=make_wav(b'\1\0'*24000,24000),headers={'Content-Type':'audio/wav'})
            return httpx.Response(200,json={})
        async def answer(request):
            assert c.desktop_state()['character']['custom_motion']==writing
            await r.flush()
            return httpx.Response(200,json={'choices':[{'message':{'content':'你好，我在。'}}]})
        v=VoiceClient('http://127.0.0.1:18865');await v.http.aclose();v.http=httpx.AsyncClient(transport=httpx.MockTransport(service),base_url='http://127.0.0.1:18865')
        a=AnswerClient('http://127.0.0.1:18866','test-model',transport=httpx.MockTransport(answer))
        d=Device();r=Robot(client=d);r.enabled=True;r.target=SimpleNamespace(address='fixture');c=Controller(v,r,a);c.motion_library=library
        who=str(uuid.uuid4());await c.connect(who);c.answer_upload=True;c.watch_dialogue.owner=who
        await c.begin(who,1)
        await c.state(who,1,'listening')
        assert c.desktop_state()['character']['custom_motion']==question
        assert r.expression=='loop '+watch_token(question)
        await c.state(who,1,'idle')
        assert c.interaction_motion() is None
        task=asyncio.create_task(c.watch_dialogue.one())
        try:
            await asyncio.wait_for(tts_started.wait(),2)
            assert c.interaction_motion()==writing
            if ending=='cancel':
                task.cancel()
                with pytest.raises(asyncio.CancelledError):await task
            else:
                tts_gate.set()
                if ending=='failure':
                    with pytest.raises(VoiceError):await task
                else:
                    await task
                    assert d.events.index('loop '+watch_token(question))<d.events.index('loop '+watch_token(writing))
                    assert d.events.count('loop '+watch_token(writing))==1,'answer/TTS/PLAY must preserve one writing loop'
                    assert d.client.played
                    timings=c.watch_dialogue.timings
                    assert all(key in timings for key in ('encode','send','device_play','stop_to_play'))
                    assert timings['stop_to_play']>=timings['download']
            assert c.interaction_motion() is None
            assert r.expression is None
            assert library.read()['entries']==[question,writing]
        finally:
            tts_gate.set()
            if not task.done():task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            await c.watch_dialogue.disable();await v.close();await a.close()
    asyncio.run(run())

def test_watch_complete_production_pipeline_and_duration_limit():
    async def run(long=False):
        requests=[]
        async def service(request):
            requests.append(request.url.path)
            if request.url.path=='/v1/sessions':return httpx.Response(200,json={'session_id':'test-session','protocol_version':1})
            if request.url.path=='/v1/settings':return httpx.Response(200,json={'routing':{'asr':'local','tts':'local','allow_audio_upload':False,'allow_text_upload':False}})
            if request.url.path.endswith('/turns'):return httpx.Response(200,json={'turn_id':1})
            if request.url.path=='/v1/asr/transcribe':return httpx.Response(200,json={'result':{'text':'你好'}})
            if request.url.path=='/v1/tts/synthesize':return httpx.Response(200,content=make_wav(b'\1\0'*(24000*(11 if long else 1)),24000) if not long else _long_wav(),headers={'Content-Type':'audio/wav'})
            return httpx.Response(200,json={})
        async def answer(request):
            data=json.loads(request.content);assert '20个字' in data['messages'][0]['content']
            return httpx.Response(200,json={'choices':[{'message':{'content':'你好，我在这里。'}}]})
        v=VoiceClient('http://127.0.0.1:18865');await v.http.aclose();v.http=httpx.AsyncClient(transport=httpx.MockTransport(service),base_url='http://127.0.0.1:18865')
        a=AnswerClient('http://127.0.0.1:18866','test-model',transport=httpx.MockTransport(answer))
        d=Device();r=Robot(client=d);r.enabled=True;c=Controller(v,r,a)
        who=str(uuid.uuid4());await c.connect(who);c.answer_upload=True;c.watch_dialogue.owner=who
        try:
            await c.watch_dialogue.one()
            assert c.watch_dialogue.recognized=='你好'
            assert c.watch_dialogue.answer=='你好，我在这里。'
            first=c.watch_dialogue.snapshot()
            assert first['turns'][0]['recognized']=='你好' and first['turns'][0]['answer']=='你好，我在这里。'
            assert first['turns'][0]['id'] and first['history_revision']>0
            assert '/v1/asr/transcribe' in requests and '/v1/tts/synthesize' in requests
            assert d.client.product_arms==1
            if long:
                assert c.watch_dialogue.stage=='speech_not_played' and not d.client.played
            else:
                assert c.watch_dialogue.stage=='completed' and d.client.played
                assert d.events.index('你好，我在这里。')>d.events.index('clear')
                await c.watch_dialogue.one()
                repeated=c.watch_dialogue.snapshot()['turns']
                assert len(repeated)==2 and repeated[0]['id']!=repeated[1]['id']
                assert repeated[0]['recognized']==repeated[1]['recognized']=='你好'
                c.watch_dialogue.pending_short=True;c.watch_dialogue.gesture.set()
                cleared=c.clear_answer_history(who)
                assert not c.watch_dialogue.snapshot()['turns'] and not c.answer_history
                assert not c.watch_dialogue.pending_short and not c.watch_dialogue.gesture.is_set()
                assert cleared['history_revision']>first['history_revision']
        finally:
            await c.watch_dialogue.disable();await v.close();await a.close()
    asyncio.run(run());asyncio.run(run(True))

def _long_wav():
    import io,wave
    target=io.BytesIO()
    with wave.open(target,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*(24000*11))
    return target.getvalue()

def test_watch_revoked_permission_does_not_capture():
    async def run():
        d=Device();r=Robot(client=d);v=SimpleNamespace(session='test')
        c=Controller(v,r);who=str(uuid.uuid4());c.owner=c.voice_owner=who;c.watch_dialogue.owner=who
        c.routing=dict(asr='cloud',tts='local',allow_audio_upload=False,allow_text_upload=False)
        with pytest.raises(VoiceError) as error:await c.watch_dialogue.one()
        assert error.value.code=='AUDIO_UPLOAD_DENIED' and d.client.product_arms==0
    asyncio.run(run())

def test_prewarm_never_arms_microphone_and_same_link_record_reuses_hello():
    async def run():
        d=Device();r=Robot(client=d);r.enabled=True
        assert await r.prepare_audio()
        prepared=r.prepared_audio
        assert prepared is not None and d.client.hellos==1 and d.client.product_arms==0
        assert not r.audio_snapshot()['running'] and r.network.router.active is None
        assert await r.prepare_audio() and r.prepared_audio is prepared and d.client.hellos==1
        r.dialogue_pinned=True;r.network.router.begin(True,r.network.wifi)
        r._start_audio('productrecord');await asyncio.wait_for(r.audio_task,2)
        assert not r.audio_error and r.audio_result
        assert d.client.hellos==1 and d.client.product_arms==1
        assert r.recording_started is not None and r.prepared_audio is None and r.audio is None
        assert prepared.closed
        r.dialogue_pinned=False;r.network.router.end()
    asyncio.run(run())

@pytest.mark.parametrize('change',['link','failed'])
def test_prewarm_rejects_old_transport_or_failed_epoch(change):
    async def run():
        d=Device();r=Robot(client=d);r.enabled=True
        await r.prepare_audio();old=r.prepared_audio
        if change=='link':d.client=ProductBle()
        else:old.abort(ConnectionError('old epoch disconnected'))
        await r.prepare_audio()
        assert old.closed and r.prepared_audio is not old
        assert d.client.product_arms==0
        assert d.client.hellos==(1 if change=='link' else 2)
        await r.close_prepared_audio()
        assert r.prepared_audio is None and d.client.callback is None
    asyncio.run(run())

def test_disable_closes_prepared_session_without_recording():
    async def run():
        d=Device();r=Robot(client=d);r.enabled=True
        await r.prepare_audio();prepared=r.prepared_audio
        c=Controller(SimpleNamespace(session='test'),r)
        await c.watch_dialogue.disable()
        assert prepared.closed and prepared.heartbeat.done()
        assert r.prepared_audio is None and d.client.callback is None
        assert not d.client.product_arms and not r.network.router.active
    asyncio.run(run())

def test_click_during_prewarm_cannot_unpin_conversation_route():
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        class SlowHello(ProductBle):
            async def write_gatt_char(self,uuid,raw,response):
                if not uuid.startswith('48f1d') and Packet.decode(raw).op==Op.HELLO:
                    entered.set();await release.wait()
                await super().write_gatt_char(uuid,raw,response)
        d=Device();d.client=SlowHello();r=Robot(client=d);r.enabled=True
        task=asyncio.create_task(r.prepare_audio())
        try:
            await asyncio.wait_for(entered.wait(),.2)
            r.dialogue_pinned=True;r.network.router.begin(True,r.network.wifi)
            release.set();await task
            assert r.network.router.active=='ble' and not d.client.product_arms
        finally:
            release.set();await task;await r.close_prepared_audio()
            r.dialogue_pinned=False;r.network.router.end()
    asyncio.run(run())

def test_manual_disconnect_releases_idle_prewarm_immediately():
    async def run():
        d=Device();r=Robot(client=d);r.enabled=True
        await r.prepare_audio();prepared=r.prepared_audio
        await r.disconnect()
        assert prepared.closed and prepared.heartbeat.done()
        assert r.prepared_audio is None and not d.connected and d.client.callback is None
        assert d.client.product_arms==0
    asyncio.run(run())

def test_robot_close_cancels_live_recording_before_waiting_for_prewarm_lock():
    async def run():
        entered=asyncio.Event()
        class LiveCapture(ProductBle):
            async def write_gatt_char(self,uuid,raw,response):
                p=Packet.decode(raw)
                if p.op==Op.PRODUCT_ARM:
                    self.product_arms+=1
                    self.send(Packet(Op.ACK,p.transfer,self.epoch,0,bytes([p.op])))
                    self.send(Packet(Op.RECORDING,p.transfer,self.epoch));entered.set();return
                await super().write_gatt_char(uuid,raw,response)
        d=Device();d.client=LiveCapture();r=Robot(client=d);r.enabled=True
        r.dialogue_pinned=True;r.network.router.begin(True,r.network.wifi);r._start_audio('productrecord')
        await asyncio.wait_for(entered.wait(),.2)
        await asyncio.wait_for(r.close(),.5)
        assert r.audio_task.cancelled() and r.audio is None and not d.connected
        assert r.prepared_audio is None and not r.audio_snapshot()['running']
    asyncio.run(run())

def test_next_physical_click_has_no_one_second_rearm_wait():
    async def run():
        d=Device();r=Robot(client=d);r.enabled=True;c=Controller(SimpleNamespace(session='test'),r)
        w=c.watch_dialogue;w.owner=str(uuid.uuid4());w.permitted=lambda:None
        first=asyncio.Event();second=asyncio.Event();calls=0
        async def turn():
            nonlocal calls
            calls+=1;(first if calls==1 else second).set()
        w.one=turn;w.task=asyncio.create_task(w.run())
        try:
            w.device_event(1);await asyncio.wait_for(first.wait(),.2)
            # This second physical click arrives at the first turn's boundary.
            await asyncio.sleep(0);w.device_event(1)
            await asyncio.wait_for(second.wait(),.2)
            assert calls==2
        finally:await w.disable()
    asyncio.run(run())

def test_rejected_enable_and_permission_revocation_preserve_explanation_without_capture():
    async def run():
        d=Device();r=Robot(client=d);c=Controller(SimpleNamespace(session='test'),r)
        who=str(uuid.uuid4());c.owner=c.voice_owner=who
        c.routing=dict(asr='local',tts='local',allow_audio_upload=False,allow_text_upload=False)
        c.answer_upload=True
        with pytest.raises(VoiceError) as failure:
            await c.watch_dialogue.enable(who,True)
        assert failure.value.code=='ANSWER_UNAVAILABLE'
        result=c.watch_dialogue.snapshot()
        assert not result['enabled'] and result['stage']=='disabled'
        assert '未配置回答服务' in result['error']
        assert d.client.product_arms==0 and c.watch_dialogue.task is None
        assert not r.audio_snapshot()['running']
        c.watch_dialogue.owner=who;c.answer_upload=False
        await c.watch_dialogue.lease()
        assert not c.watch_dialogue.snapshot()['enabled']
        assert '允许向回答服务发送文字' in c.watch_dialogue.snapshot()['error']
        await c.watch_dialogue.disable()
        assert c.watch_dialogue.snapshot()['error']=='' and d.client.product_arms==0
    asyncio.run(run())

@pytest.mark.parametrize('blocked',['asr','answer','tts'])
def test_physical_event_only_and_cancel_each_service(blocked):
    async def run():
        arrived=asyncio.Event();never=asyncio.Event();calls=[]
        async def service(request):
            path=request.url.path;calls.append(path)
            if path=='/v1/sessions':return httpx.Response(200,json={'session_id':'test-session','protocol_version':1})
            if path=='/v1/settings':return httpx.Response(200,json={'routing':{'asr':'local','tts':'local','allow_audio_upload':False,'allow_text_upload':False}})
            if path.endswith('/turns'):return httpx.Response(200,json={'turn_id':1})
            if path=='/v1/asr/transcribe':
                if blocked=='asr':arrived.set();await never.wait()
                return httpx.Response(200,json={'result':{'text':'你好'}})
            if path=='/v1/tts/synthesize':
                if blocked=='tts':arrived.set();await never.wait()
                return httpx.Response(200,content=make_wav(b'\1\0'*24000,24000))
            return httpx.Response(200,json={})
        async def answer(request):
            if blocked=='answer':arrived.set();await never.wait()
            return httpx.Response(200,json={'choices':[{'message':{'content':'我在。'}}]})
        v=VoiceClient('http://127.0.0.1:18865');await v.http.aclose()
        v.http=httpx.AsyncClient(transport=httpx.MockTransport(service),base_url='http://127.0.0.1:18865')
        a=AnswerClient('http://127.0.0.1:18866','test-model',transport=httpx.MockTransport(answer))
        d=Device();r=Robot(client=d);r.enabled=True;c=Controller(v,r,a);who=str(uuid.uuid4())
        await c.connect(who);c.answer_upload=True
        try:
            await c.watch_dialogue.enable(who,True);await asyncio.sleep(.05)
            assert d.client.product_arms==0 and not r.audio_snapshot()['running']
            previous=asyncio.create_task(asyncio.sleep(60));r.audio_task=previous
            c.watch_dialogue.device_event(1)
            await asyncio.wait_for(arrived.wait(),3)
            assert previous.cancelled() # explicit begin preempts old playback
            c.watch_dialogue.device_event(2);await asyncio.sleep(.15)
            assert not d.client.played
            assert r.audio is None and not r.audio_snapshot()['running']
            assert not r.network.router.active
            count=d.client.product_arms;await asyncio.sleep(1.1)
            assert d.client.product_arms==count # no old recording or automatic rearm
        finally:
            await c.watch_dialogue.disable();await v.close();await a.close()
    asyncio.run(run())
