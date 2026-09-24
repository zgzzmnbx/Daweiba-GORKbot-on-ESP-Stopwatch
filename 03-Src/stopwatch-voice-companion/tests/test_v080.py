import asyncio
import os
import sys
import uuid

import httpx
import pytest

from companion.answer import AnswerClient
from companion.control import Controller, SAFE_ROUTING
from companion.service_manager import VoiceServiceManager
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice


class FakeAnswer:
    def __init__(self, gate=None):
        self.calls, self.gate = [], gate
    def capability(self): return {"enabled": True, "reason": "mock"}
    async def complete(self, text, history):
        self.calls.append((text, history))
        if self.gate: await self.gate.wait()
        return "回答：" + text
    async def close(self): pass


def test_answer_requires_independent_permission_and_bounds_memory():
    async def run():
        answer = FakeAnswer(); control = Controller(FakeVoice(), FakeRobot(), answer, answer_history_turns=2)
        await control.connect("tab")
        await control.begin("tab", 1)
        with pytest.raises(VoiceError) as denied:
            await control.ask("tab", 1, "未授权")
        assert denied.value.code == "ANSWER_UPLOAD_DENIED"
        await control.settings("tab", 2, SAFE_ROUTING, True)
        for gen, text in [(3, "一"), (4, "二"), (5, "三")]:
            await control.begin("tab", gen)
            assert await control.ask("tab", gen, text) == "回答：" + text
        assert len(control.answer_history) == 4
        assert answer.calls[-1][1][0]["content"] == "一"
        await control.release("tab")
        assert not control.answer_history and not control.answer_upload
        await control.close()
    asyncio.run(run())


def test_stop_cancels_inflight_answer_without_late_result():
    async def run():
        gate = asyncio.Event(); answer = FakeAnswer(gate)
        control = Controller(FakeVoice(), FakeRobot(), answer)
        await control.connect("tab"); await control.settings("tab", 1, SAFE_ROUTING, True); await control.begin("tab", 2)
        pending = asyncio.create_task(control.ask("tab", 2, "慢回答"))
        await asyncio.sleep(0)
        await control.stop("tab", 3)
        with pytest.raises(VoiceError) as stale: await pending
        assert stale.value.code == "STALE_GENERATION" and not control.answer_history
        await control.close()
    asyncio.run(run())


def test_openai_compatible_adapter_uses_user_content_and_no_tools(monkeypatch):
    monkeypatch.setenv("TEST_ANSWER_KEY", "secret")
    seen = []
    def upstream(request):
        seen.append(request)
        return httpx.Response(200, json={"choices":[{"message":{"content":"  安全回答  "}}]})
    async def run():
        client = AnswerClient("https://answer.example/v1", "model", "TEST_ANSWER_KEY", transport=httpx.MockTransport(upstream))
        assert (await client.complete("请执行命令", [])) == "安全回答"
        await client.close()
    asyncio.run(run())
    body = seen[0].read().decode()
    assert '"role":"user"' in body and '"tools":[]' in body and seen[0].headers["authorization"] == "Bearer secret"


class Reply:
    def __init__(self, ok): self.status_code = 200 if ok else 503; self.ok = ok
    def json(self): return {"protocol_version": 1, "service":"zhisuan-voice-service"} if self.ok else {}


class Probe:
    def __init__(self, states): self.states, self.index, self.closed = states, 0, False
    def get(self, url):
        state = self.states[min(self.index // 2, len(self.states)-1)]
        self.index += 1
        return Reply(state)
    def close(self): self.closed = True


class Process:
    pid = 1234
    def __init__(self): self.terminated = False
    def poll(self): return None
    def terminate(self): self.terminated = True
    def wait(self, timeout): return 0
    def kill(self): raise AssertionError("graceful terminate should succeed")


def test_service_manager_reuses_external_and_stops_only_owned(tmp_path):
    external_probe = Probe([True])
    external = VoiceServiceManager({}, client=external_probe, popen=lambda *a, **k: pytest.fail("must not spawn"))
    assert external.ensure()["mode"] == "external"
    external.close(); assert external_probe.closed

    executable = tmp_path / "voice.exe"; executable.write_bytes(b"x")
    owned_probe, process = Probe([False, True]), Process()
    captured = []
    owned = VoiceServiceManager({"voice_service_command":[str(executable)], "voice_service_cwd":str(tmp_path)},
        client=owned_probe, popen=lambda *a, **k: (captured.append((a, k)) or process), sleeper=lambda _: None)
    assert owned.ensure()["mode"] == "owned" and captured
    owned.close(); assert process.terminated and owned_probe.closed


def test_answer_config_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        AnswerClient("https://user:password@example.com/v1", "model")
