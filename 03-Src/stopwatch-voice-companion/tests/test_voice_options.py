import asyncio
import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from companion.app import create_app
from companion.control import Controller, SAFE_ROUTING
from companion.service_manager import VoiceServiceManager
from companion.voice import VoiceClient, VoiceError
from test_companion import FakeRobot, FakeVoice, wav_bytes
from test_v080 import Probe, Process

CAPS = {"protocol_version": 1, "tts": {"speakers": [{"id": 3}, {"id": 58}]},
        "cloud": {"request_voice": True, "voices": [{"id": "Cherry"}, {"id": "Ethan"}]}}


class OptionsVoice(FakeVoice):
    async def capabilities(self): return CAPS
    async def synthesize(self, *args):
        self.last_synthesis = args
        return wav_bytes(24000)


def test_speech_selection_propagates_and_invalid_selection_cannot_leak_old_turn():
    async def run():
        voice = OptionsVoice()
        control = Controller(voice, FakeRobot())
        await control.connect("tab")
        options = {"speaker_id": 58, "cloud_voice": "Ethan", "speed": 1.15}
        await control.settings("tab", 1, SAFE_ROUTING, False, options)
        await control.perform("tab", 1, "tts", "hello")
        assert voice.last_synthesis[3] == dict(options, request_voice=True)
        cloud = dict(SAFE_ROUTING, tts="cloud", allow_text_upload=True)
        with pytest.raises(VoiceError, match="自然语速"):
            await control.settings("tab", 2, cloud, False, options)
        assert control.turn == 0
        options["speed"] = 1.0
        await control.settings("tab", 3, cloud, False, options)
        # Even invalid speech settings must not prevent revoking uploads.
        with pytest.raises(VoiceError):
            await control.settings("tab", 4, SAFE_ROUTING, False, dict(options, speaker_id=99))
        assert not control.routing["allow_text_upload"] and control.turn == 0
        await control.close()
    asyncio.run(run())


def test_http_voice_options_and_legacy_compatibility():
    seen = []
    def upstream(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=wav_bytes(24000), headers={"content-type": "audio/wav"})
    async def run():
        voice = VoiceClient("http://127.0.0.1:8765", transport=httpx.MockTransport(upstream))
        await voice.synthesize("hi", 1, "a", {"speaker_id":58, "speed":1.15})
        await voice.synthesize("hi", 2, "b", {"cloud_voice":"Ethan", "request_voice":True})
        await voice.close()
    asyncio.run(run())
    assert seen[0]["speaker_id"] == 58 and seen[0]["speed"] == 1.15
    assert "cloud_voice" not in seen[0] and seen[1]["cloud_voice"] == "Ethan"


def test_settings_http_validation():
    control = Controller(OptionsVoice(), FakeRobot())
    with TestClient(create_app(controller=control), base_url="http://127.0.0.1:8766") as client:
        headers = {"X-Companion-Client":str(uuid.uuid4())}
        assert client.post("/api/session", json={}, headers=headers).status_code == 200
        body = {"generation":1, "routing":SAFE_ROUTING,
                "speech":{"speaker_id":58,"cloud_voice":"Ethan","speed":1.15}}
        assert client.patch("/api/settings", json=body, headers=headers).status_code == 200
        body["speech"]["speed"] = 99
        assert client.patch("/api/settings", json=body, headers=headers).status_code == 422
        assert client.post("/api/voice-service/start", headers=headers).status_code == 503
        assert client.post("/api/voice-service/start").status_code == 401


def test_manager_retry_keeps_client_open_and_owned_identity(tmp_path):
    executable = tmp_path / "voice.exe"
    executable.write_bytes(b"x")
    class FailedProcess(Process):
        def poll(self): return 1
    probe = Probe([False, False, True])
    processes, calls = [FailedProcess(), Process()], []
    def spawn(*args, **kwargs):
        calls.append(1)
        return processes.pop(0)
    manager = VoiceServiceManager({"voice_service_command":[str(executable)]},
                                  client=probe, popen=spawn, sleeper=lambda _:None)
    assert manager.ensure()["mode"] == "offline" and not probe.closed
    assert manager.ensure()["mode"] == "owned"
    assert manager.ensure()["mode"] == "owned" and len(calls) == 2
    manager.close()
    assert probe.closed


def test_manager_bad_config_is_reported_without_crashing():
    manager = VoiceServiceManager({"voice_service_command":["missing.exe"]}, client=Probe([False]))
    assert manager.ensure()["mode"] == "offline"
    assert manager.snapshot()["error"]
    manager.close()
