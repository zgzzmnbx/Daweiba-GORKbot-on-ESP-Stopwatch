import asyncio
import uuid

import httpx
import pytest

from companion.app import create_app
from companion.control import Controller
from companion.task_monitor import _fixed_wav
from companion import sentinel_voice_library as library
from test_companion import FakeRobot, FakeVoice, wav_bytes


def test_cached_cherry_phrase_is_reused_and_invalid_audio_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(library, 'cache_dir', lambda: tmp_path)
    phrase = library.PHRASES[0][2]
    with pytest.raises(FileNotFoundError):
        _fixed_wav(phrase)
    raw = wav_bytes(24000)
    path = library.save(phrase, raw)
    assert _fixed_wav(phrase) == path
    assert _fixed_wav(phrase).read_bytes() == raw
    assert library.catalogue()['ready'] == 1
    with pytest.raises(ValueError):
        library.save(phrase, b'invalid wav')
    assert _fixed_wav(phrase).read_bytes() == raw
    with pytest.raises(ValueError):
        library.path_for('arbitrary text')


def test_voice_library_generation_requires_cloud_grant_and_caches_one_phrase(tmp_path, monkeypatch):
    monkeypatch.setattr(library, 'cache_dir', lambda: tmp_path)

    class Cost:
        async def monitor_feed(self):
            return {'task': None, 'recent': [], 'events': []}
        async def close(self):
            pass

    class Voice(FakeVoice):
        def __init__(self):
            super().__init__()
            self.requests = []
        async def synthesize(self, *args, **kwargs):
            self.requests.append((args, kwargs))
            return wav_bytes(24000)

    async def run():
        owner = str(uuid.uuid4())
        voice = Voice()
        control = Controller(voice, FakeRobot())
        app = create_app({'sentinel_state_path': tmp_path / 'prefs.json'}, controller=control, cost_client=Cost())
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url='http://127.0.0.1:8766', headers={'X-Companion-Client': owner}) as client:
                control.owner = control.voice_owner = owner
                control.voice.session = 'private-session'
                control.turn = 1
                response = await client.post('/api/character/voice-library/generate',
                                             json={'item_id': 'conversion_start'})
                assert response.status_code == 403
                control.routing = {'tts': 'cloud', 'allow_text_upload': True}
                response = await client.post('/api/character/voice-library/generate',
                                             json={'item_id': 'conversion_start'})
                assert response.status_code == 200
                assert response.json()['library']['ready'] == 1
                assert len(voice.requests) == 1
                assert voice.requests[0][0][0] == '开始转换'
                assert voice.requests[0][0][3]['cloud_voice'] == 'Cherry'
                response = await client.post('/api/character/voice-library/generate',
                                             json={'item_id': 'conversion_start'})
                assert response.json()['generated'] == [] and len(voice.requests) == 1
                preview = await client.get('/api/character/voice-library/conversion_start/preview')
                assert preview.status_code == 200 and preview.content == wav_bytes(24000)
    asyncio.run(run())
