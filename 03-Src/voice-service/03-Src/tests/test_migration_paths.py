from pathlib import Path

from voice_service.config import ROOT, SERVICE_ROOT, Settings, load_settings


def test_relocated_default_config_resolves_models_in_stopwatch_runtime(monkeypatch):
    monkeypatch.delenv("VOICE_CONFIG", raising=False)
    assert SERVICE_ROOT == Path(__file__).resolve().parents[2]
    assert ROOT == SERVICE_ROOT.parents[1]
    assert Settings().asr_dir == str(ROOT / "Codex-Temp/voice-runtime/models/sensevoice")
    assert Settings().tts_dir == str(ROOT / "Codex-Temp/voice-runtime/models/kokoro")
    settings = load_settings()
    assert settings.asr_dir == Settings().asr_dir
    assert settings.tts_dir == Settings().tts_dir
