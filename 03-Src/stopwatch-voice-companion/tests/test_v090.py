import asyncio

import pytest

from companion.control import Controller
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice


class CharacterRobot(FakeRobot):
    async def play_expression(self, expression, mode):
        self.events.append(("expression", expression, mode))
        return {"receipt": "OK:EXPR", "expression": expression, "mode": mode}

    async def set_bubble(self, text):
        self.events.append(("bubble", text))
        return {"receipt": "OK:TEXT", "text": text}

    async def clear_bubble(self):
        self.events.append(("clear-bubble",))
        return {"receipt": "OK:CLEAR"}


def test_workspace_stays_available_when_voice_is_released():
    async def run():
        robot = CharacterRobot()
        control = Controller(FakeVoice(), robot)
        await control.acquire_workspace("tab")
        assert control.desktop_state()["workspace_active"]
        assert not control.desktop_state()["session_active"]
        result = await control.play_character("tab", "happy", "once", "desktop")
        assert result["desktop"]["accepted"] and not result["watch"]["requested"]
        await control.connect("tab")
        await control.release_voice("tab")
        assert control.desktop_state()["workspace_active"]
        await control.play_character("tab", "thinking", "loop", "watch")
        assert ("expression", "thinking", "loop") in robot.events
        await control.close()
    asyncio.run(run())


def test_character_boundary_rejects_watch_only_desktop_and_invalid_bubbles():
    async def run():
        control = Controller(FakeVoice(), CharacterRobot())
        await control.acquire_workspace("tab")
        with pytest.raises(VoiceError, match="仅支持 StopWatch"):
            await control.play_character("tab", "happy-work", "once", "both")
        with pytest.raises(VoiceError, match="1–300"):
            await control.set_character_bubble("tab", "", "desktop")
        with pytest.raises(VoiceError, match="目录"):
            await control.play_character("tab", "not-a-pose", "once", "desktop")
        await control.close()
    asyncio.run(run())


def test_desktop_bubble_is_replaced_and_can_be_cleared():
    async def run():
        control = Controller(FakeVoice(), CharacterRobot())
        await control.acquire_workspace("tab")
        await control.set_character_bubble("tab", "第一条", "desktop")
        first = control.desktop_state()["character"]
        await control.set_character_bubble("tab", "第二条", "desktop")
        second = control.desktop_state()["character"]
        assert second["bubble"] == "第二条" and second["revision"] > first["revision"]
        await control.clear_character_bubble("tab", "desktop")
        assert control.desktop_state()["character"]["bubble"] == ""
        await control.close()
    asyncio.run(run())
