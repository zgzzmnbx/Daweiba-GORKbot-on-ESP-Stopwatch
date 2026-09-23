from pathlib import Path
from companion.service_manager import VoiceServiceManager
from test_v080 import Probe, Process


def test_default_managed_service_resolves_inside_current_project(monkeypatch):
    monkeypatch.setenv("VOICE_CONFIG", "Z:/old-project/config.toml")
    calls = []
    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return Process()
    manager = VoiceServiceManager({}, client=Probe([False, True]), popen=spawn, sleeper=lambda _: None)
    root = Path(__file__).resolve().parents[3]
    assert all(Path(p).is_relative_to(root) for p in manager.command)
    assert manager.ensure()["mode"] == "owned"
    command, kwargs = calls[0]
    assert Path(kwargs["env"]["VOICE_CONFIG"]).is_relative_to(root)
    assert Path(kwargs["cwd"]).is_relative_to(root)
    manager.close()


def test_explicit_empty_command_stays_reuse_only():
    manager = VoiceServiceManager({"voice_service_command": []}, client=Probe([False]))
    assert manager.ensure()["mode"] == "offline"
    assert not manager.snapshot()["configured"]
    manager.close()
