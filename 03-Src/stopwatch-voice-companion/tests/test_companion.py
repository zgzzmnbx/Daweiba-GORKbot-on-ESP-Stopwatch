import asyncio
import io
import uuid
import wave
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from companion.app import create_app
from companion.control import Controller, SAFE_ROUTING
from companion.robot import Robot, short_bubble
from companion.voice import VoiceClient, VoiceError, check_wav


def wav_bytes(rate=16000, channels=1, frames=3200):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((channels, 2, rate, frames, 'NONE', 'NONE'))
        wav.writeframes(b'\x00\x00' * frames * channels)
    return output.getvalue()


def test_audio_timeout_keeps_failure_reason_and_zero_transfer(monkeypatch):
    async def run():
        robot = Robot(client=SimpleNamespace(connected=True))
        robot.enabled = True
        async def timeout(*_args):
            raise TimeoutError()
        monkeypatch.setattr(robot, '_run_audio', timeout)
        job = robot.start_audio_play(wav_bytes())
        await robot.audio_task
        result = robot.audio_snapshot()
        assert result['job_id'] == job['job_id']
        assert result['stage'] == 'error' and result['bytes'] == 0
        assert 'Audio test' in result['error']
        assert not result['running']
    asyncio.run(run())


class FakeRobot:
    def __init__(self):
        self.events, self.generation = [], 0
    def start(self): pass
    def show(self, *args): self.events.append(args)
    def snapshot(self): return {'connected': False, 'enabled': False, 'receipt': '', 'error': ''}
    async def close(self): pass
    async def play_sound(self, sound_id): self.events.append(('sound', sound_id)); return {'event':'completed','sound_id':sound_id}
    async def stop_sound(self): self.events.append(('sound-stop',)); return {'event':'stopped'}
    async def set_sound_volume(self, volume): self.events.append(('sound-volume', volume)); return {'event':'completed','volume':volume}
    def audio_snapshot(self): return {'job_id':'00000000-0000-0000-0000-000000000001','stage':'received','running':False,'result_ready':True}
    def start_audio_record(self, echo=False): self.events.append(('audio-record',echo)); return self.audio_snapshot()
    def start_audio_play(self, data): self.events.append(('audio-play',len(data))); return self.audio_snapshot()
    async def cancel_audio(self): self.events.append(('audio-cancel',)); return self.audio_snapshot()
    def take_audio_result(self, job_id): self.events.append(('audio-result',job_id)); return wav_bytes()


class FakeVoice:
    def __init__(self):
        self.session = None
        self.turn_id, self.replaces = 0, []
        self.cancelled, self.routes = [], []
        self.gate = None
        self.started = asyncio.Event()
        self.invalid = False
    async def connect(self, replace=False):
        self.replaces.append(replace); self.session = str(uuid.uuid4())
    async def routing(self, value):
        self.routes.append(value); return value
    async def turn(self): self.turn_id += 1; return self.turn_id
    async def cancel(self, *args): self.cancelled.append(args)
    request_id = staticmethod(VoiceClient.request_id)
    async def transcribe(self, *args):
        self.started.set()
        if self.gate: await self.gate.wait()
        return '这是完整的测试转写文本，不应该被设备气泡长度截断。' * 2
    async def synthesize(self, *args):
        self.started.set()
        if self.gate: await self.gate.wait()
        return wav_bytes(24000)
    async def alive(self):
        if self.invalid:
            self.session = None
            raise VoiceError(401, 'SESSION_INVALID', '接管')
        return {'turn_id': self.turn_id}
    async def release(self): self.session = None
    async def close(self): await self.release()
    async def health(self): return {'ready': True}
    async def capabilities(self): return {'protocol_version': 1}


def test_wav_validation_and_no_relabel():
    assert check_wav(wav_bytes(), microphone=True)
    assert check_wav(wav_bytes(24000))
    for invalid in [b'webm', wav_bytes(48000), wav_bytes(channels=2), wav_bytes()[:-4], wav_bytes(frames=30)]:
        with pytest.raises(VoiceError): check_wav(invalid, microphone=True)


def test_http_client_full_wav_multipart_and_token():
    seen = []
    def upstream(request):
        seen.append(request)
        path = request.url.path
        if path == '/v1/sessions': return httpx.Response(200, json={'session_id': 'private-token', 'protocol_version':1})
        assert request.headers['X-Voice-Session'] == 'private-token'
        if path == '/v1/asr/transcribe':
            assert b'RIFF' in request.content and b'name="turn_id"' in request.content
            return httpx.Response(200, json={'result': {'text': '你好'}})
        if path == '/v1/tts/synthesize': return httpx.Response(200, content=wav_bytes(24000), headers={'content-type':'audio/wav'})
        return httpx.Response(200, json={})
    async def run():
        client = VoiceClient('http://127.0.0.1:8765', transport=httpx.MockTransport(upstream))
        await client.connect()
        assert await client.transcribe(wav_bytes(), 1, 'test-asr') == '你好'
        assert await client.synthesize('你好', 1, 'test-tts') == wav_bytes(24000)
        await client.close()
    asyncio.run(run())
    assert b'false' in seen[0].content


@pytest.mark.parametrize('status,code', [(409, 'SESSION_BUSY'), (401, 'SESSION_INVALID'), (403, 'UPLOAD_DENIED')])
def test_http_errors_are_not_success_or_retried(status, code):
    calls = []
    def upstream(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'code': code, 'message': code}})
    async def run():
        client = VoiceClient('http://127.0.0.1:8765', transport=httpx.MockTransport(upstream))
        client.session = 'old'
        with pytest.raises(VoiceError) as caught: await client.alive()
        assert caught.value.code == code
        if status == 401: assert client.session is None
        await client.http.aclose()
    asyncio.run(run()); assert len(calls) == 1


def test_http_timeout_offline_and_invalid_tts():
    async def run():
        for result in [httpx.ReadTimeout('timeout'), httpx.ConnectError('offline'), httpx.Response(200, json={'url':'not-an-audio-file'})]:
            def upstream(request):
                if isinstance(result, Exception): raise result
                return result
            client = VoiceClient('http://127.0.0.1:8765', transport=httpx.MockTransport(upstream))
            with pytest.raises(VoiceError): await client.synthesize('你好', 1, 'req')
            await client.http.aclose()
    asyncio.run(run())


def test_20_stops_discard_late_asr_and_tts_with_cancel():
    async def run():
        voice, robot = FakeVoice(), FakeRobot()
        control = Controller(voice, robot)
        await control.connect('tab')
        assert voice.routes[-1] == SAFE_ROUTING and voice.replaces == [False]
        for index in range(20):
            gen = index * 2 + 1
            await control.begin('tab', gen)
            voice.gate, voice.started = asyncio.Event(), asyncio.Event()
            pending = asyncio.create_task(control.perform('tab', gen, 'asr' if index % 2 else 'tts', 'mock'))
            await voice.started.wait()
            await control.stop('tab', gen + 1)
            last = len(robot.events)
            voice.gate.set()
            with pytest.raises(VoiceError) as caught: await pending
            assert caught.value.code == 'STALE_GENERATION'
            assert len(robot.events) == last and control.phase == 'idle'
            await asyncio.sleep(0)
        assert len(voice.cancelled) == 20
        await control.close()
    asyncio.run(run())


def test_new_turn_does_not_wait_for_old_request_and_takeover_invalidates():
    async def run():
        voice, robot = FakeVoice(), FakeRobot()
        control = Controller(voice, robot)
        await control.connect('old')
        with pytest.raises(VoiceError): await control.connect('new')
        await control.begin('old', 1)
        voice.gate = asyncio.Event(); gate = voice.gate
        old = asyncio.create_task(control.perform('old', 1, 'asr', b''))
        await voice.started.wait()
        await control.begin('old', 2)
        voice.gate = None
        result = await control.perform('old', 2, 'asr', b'')
        assert len(result) > 24
        await control.connect('new', True)
        gate.set()
        with pytest.raises(VoiceError): await old
        with pytest.raises(VoiceError): await control.state('old', 1, 'speaking')
        voice.invalid = True
        with pytest.raises(VoiceError): await control.heartbeat('new')
        voice.invalid = False
        await control.connect('reopened')
        await control.close()
    asyncio.run(run())


def test_explicit_settings_and_current_robot_mapping():
    async def run():
        voice, robot = FakeVoice(), FakeRobot(); control = Controller(voice, robot)
        await control.connect('tab'); await control.begin('tab', 1)
        await control.state('tab', 1, 'listening')
        text = await control.perform('tab', 1, 'asr', b'')
        await control.state('tab', 1, 'speaking')
        assert robot.events[-1] == ('speaking', 1, text)
        await control.settings('tab', 2, {**SAFE_ROUTING, 'tts':'cloud','allow_text_upload':True})
        with pytest.raises(VoiceError): await control.state('tab', 1, 'speaking')
        await control.close()
    asyncio.run(run())


def test_asr_and_edited_tts_share_turn_but_have_distinct_generations():
    async def run():
        voice, robot = FakeVoice(), FakeRobot(); control = Controller(voice, robot)
        await control.connect('tab'); await control.begin('tab', 1)
        await control.perform('tab', 1, 'asr', b'')
        await control.begin('tab', 2, reuse_turn=True)
        assert control.turn == 1
        await control.perform('tab', 2, 'tts', '人工编辑文字')
        with pytest.raises(VoiceError): await control.state('tab', 1, 'listening')
        await control.begin('tab', 3)
        assert control.turn == 2
        await control.close()
    asyncio.run(run())


def test_api_local_boundary_permissions_and_safe_default():
    control = Controller(FakeVoice(), FakeRobot())
    app = create_app(controller=control)
    headers = {'X-Companion-Client': str(uuid.uuid4())}
    with TestClient(app, base_url='http://127.0.0.1:8766') as client:
        assert client.get('/').status_code == 200
        preview = client.get('/api/sounds/2/preview')
        assert preview.status_code == 200 and preview.content[:4] == b'RIFF'
        assert client.get('/api/sounds/9/preview').status_code == 404
        assert client.get('/api/health', headers={'host':'evil.example'}).status_code == 403
        assert client.post('/api/session', json={}, headers={'Origin':'https://evil.example'}).status_code == 403
        assert client.post('/api/session', json={}).status_code == 401
        result = client.post('/api/session', json={}, headers=headers)
        assert result.status_code == 200 and 'session_id' not in result.text
        assert result.json()['routing'] == SAFE_ROUTING
        assert client.patch('/api/settings', headers=headers, json={'generation':1, 'routing':{**SAFE_ROUTING,'tts':'cloud'}}).status_code == 403
        assert client.post('/api/begin', headers=headers, json={'generation':1}).status_code == 200
        assert client.post('/api/device/sound', headers=headers, json={'sound_id':2}).json()['sound_id'] == 2
        assert client.put('/api/device/sound/volume', headers=headers, json={'volume':35}).json()['volume'] == 35
        assert client.delete('/api/device/sound', headers=headers).json()['event'] == 'stopped'
        assert client.post('/api/device/sound', headers=headers, json={'sound_id':7}).status_code == 422
        job = client.post('/api/device/audio/record', headers=headers, json={'echo':False}).json()
        assert job['stage'] == 'received'
        assert client.post('/api/device/audio/play', headers={**headers,'Content-Type':'audio/wav'}, content=wav_bytes()).status_code == 200
        assert client.get('/api/device/audio', headers=headers).status_code == 200
        assert client.get('/api/device/audio/result/'+job['job_id'], headers=headers).content[:4] == b'RIFF'
        assert client.delete('/api/device/audio', headers=headers).status_code == 200
        assert client.post('/api/tts', headers=headers, json={'generation':1,'text':'你好'}).headers['content-type'] == 'audio/wav'
        assert client.post('/api/stop', headers=headers, json={'generation':2}).status_code == 200
        assert client.post('/api/tts', headers=headers, json={'generation':1,'text':'旧结果'}).status_code == 409
        assert client.post('/api/tts', headers=headers, json={'generation':2,'text':'x'*301}).status_code == 422
        assert client.delete('/api/session', headers=headers).status_code == 200


def test_config_rejects_remote_or_credential_urls():
    for url in ['https://remote.example', 'http://127.0.0.1@remote.example', 'http://user:password@localhost:8765', 'http://localhost:8765/key']:
        with pytest.raises(ValueError): create_app({'voice_url':url})


def test_bubble_bmp_preview_does_not_mutate_full_text():
    value = '中'*40+'😀\n'
    result = short_bubble(value)
    assert result == '中'*23+'…' and len(result.encode('utf8')) == 72
    assert len(value) == 42


class FakeBle:
    def __init__(self): self.connected=False; self.writes=[]; self.connects=0; self.fail=False
    async def connect(self, target):
        self.connects += 1
        if self.fail: raise RuntimeError('offline')
        self.connected=True
    async def disconnect(self): self.connected=False
    async def send_command(self, value): self.writes.append(value); return 'OK:'+value.upper()
    async def clear_text(self): self.writes.append('clear'); return 'OK:CLEAR'
    async def send_text(self, value): self.writes.append(value); return 'OK:TEXT:1'


def test_robot_latest_state_only_and_reconnection_no_old_text():
    async def run():
        ble = FakeBle(); robot = Robot(ble); robot.target=object(); robot.enabled=True
        robot.show('listening', 1); robot.show('idle', 2); robot.show('speaking', 1)
        await robot.flush(); assert ble.writes == ['idle','clear']
        robot.show('speaking', 3, '你好'); await robot.flush()
        assert ble.writes[-3:] == ['loop happy','clear','你好']
        ble.connected=False; await robot.flush()
        assert ble.writes[-2:] == ['loop happy','clear']
        ble.connected=False; await robot.flush()
        assert ble.connects == 2 and '两次' in robot.error
        await robot.close()
    asyncio.run(run())
