import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

import pytest

import asyncio
from stopwatch_sound import ACCEPTED, STARTED, COMPLETED, PLAY, SET_VOLUME, SoundClient, SoundFrame, play, set_volume

ROOT = Path(__file__).resolve().parents[1]


def test_frames_fit_20_byte_mtu_and_round_trip():
    encoded = play(7, 3)
    assert len(encoded) == 9 and len(encoded) <= 20
    assert SoundFrame.decode(encoded) == SoundFrame(PLAY, 7, 0, 3)
    assert SoundFrame.decode(set_volume(8, 35)) == SoundFrame(SET_VOLUME, 8, 35, 0)


@pytest.mark.parametrize("value", [-1, 101])
def test_volume_is_bounded(value):
    with pytest.raises(ValueError):
        set_volume(1, value)


def test_generator_is_deterministic_and_within_budget():
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)
        subprocess.run([sys.executable, str(ROOT / "tools/generate_builtin_sounds.py"), "--root", str(target)], check=True)
        manifest = json.loads((target / "01-assets/audio/manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["sounds"]) == 6 and manifest["total_pcm_bytes"] <= 128_000
        assert manifest["version"] == 2 and manifest["peak_amplitude"] == 30_000
        assert len({item["id"] for item in manifest["sounds"]}) == 6
        for item in manifest["sounds"]:
            with wave.open(str(target / "01-assets/audio/source" / f'{item["id"]:02d}-{item["name"]}.wav')) as audio:
                assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16_000)
                assert audio.readframes(800) == b"\0" * 1600
                pcm = audio.readframes(audio.getnframes() - 800)
                samples = memoryview(pcm).cast("h")
                assert max(map(abs, samples)) == 30_000
                assert all(-32_768 <= value <= 32_767 for value in samples)


def test_speaker_and_vibration_share_only_m5unified_io_expander():
    firmware = ROOT / "03-Src/stopwatch-grok-avatar"
    main = (firmware / "src/main.cpp").read_text(encoding="utf-8")
    output = (firmware / "src/speaker_output.cpp").read_text(encoding="utf-8")
    platformio = (firmware / "platformio.ini").read_text(encoding="utf-8")
    assert "#include <M5IOE1.h>" not in main
    assert "M5IOE1 ioe" not in main
    assert "M5.Power.setVibration" in main
    assert "M5IOE1 = https://github.com/m5stack/M5IOE1.git#" in platformio
    assert "M5.getIOExpander(0)" in output
    assert "M5IOE1_Class::gpio3" in output
    assert "M5IOE1_Class::gpio10" in output
    assert "kCodecAddress = 0x18" in output
    assert "GPIO_NUM_14" in output
    assert "gpio_set_direction" in output and "GPIO_MODE_INPUT_OUTPUT" in output
    assert "gpio_set_level" in output
    assert "gpio_get_level" in output
    assert "kOfficialEs8311PlaybackRegisters" in output
    assert "{0x09, 0x0C}" in output  # 16-bit Philips I2S
    assert "{0x08, 0xFF}" in output  # 44.1 kHz LRCK divider
    assert "{0x44, 0x58}" in output  # official internal DAC reference
    assert "mute & 0x60" in output


def test_builtin_loudness_boost_is_scoped_to_short_sounds():
    firmware = ROOT / "03-Src/stopwatch-grok-avatar/src"
    sound = (firmware / "sound_control.cpp").read_text(encoding="utf-8")
    probe = (firmware / "audio_probe.cpp").read_text(encoding="utf-8")
    output = (firmware / "speaker_output.cpp").read_text(encoding="utf-8")
    assert "kCodecUnityVolume = 0xBF" in output
    assert "kCodecBuiltInLoudVolume = 0xD2" in output
    assert "SpeakerGainProfile::BuiltInLoud" in sound
    assert "SpeakerGainProfile::BuiltInLoud" not in probe
    assert "startStopWatchSpeaker(192)" in probe


def test_firmware_version_is_visible_on_settings_page():
    main = (ROOT / "03-Src/stopwatch-grok-avatar/src/main.cpp").read_text(
        encoding="utf-8")
    assert 'kFirmwareVersion[] = "v0.9.0-dev"' in main
    assert 'drawDiagnosticLine(102, "Firmware", kFirmwareVersion' in main


def test_all_speaker_shutdowns_disable_the_gpio14_pa_gate():
    firmware = ROOT / "03-Src/stopwatch-grok-avatar/src"
    main = (firmware / "main.cpp").read_text(encoding="utf-8")
    sound = (firmware / "sound_control.cpp").read_text(encoding="utf-8")
    probe = (firmware / "audio_probe.cpp").read_text(encoding="utf-8")
    output = (firmware / "speaker_output.cpp").read_text(encoding="utf-8")
    assert "M5.Speaker.end()" not in main
    assert "M5.Speaker.end()" not in sound
    assert "M5.Speaker.end()" not in probe
    assert main.count("stopStopWatchSpeaker()") == 1
    assert sound.count("stopStopWatchSpeaker()") >= 2
    assert probe.count("stopStopWatchSpeaker()") >= 3
    assert output.count("M5.Speaker.end()") == 2


def test_sound_client_matches_request_and_ignores_stale_event():
    class FakeBle:
        is_connected = True
        async def start_notify(self, uuid, callback): self.callback = callback
        async def write_gatt_char(self, uuid, data, response):
            request = SoundFrame.decode(data)
            self.callback(None, SoundFrame(COMPLETED, request.request_id - 1 or 9, 0, 2).encode())
            self.callback(None, SoundFrame(COMPLETED, request.request_id, 0, request.argument).encode())
    async def run():
        sound = SoundClient(); await sound.attach(FakeBle())
        result = await sound.play(2)
        assert result["request_id"] == 1 and result["sound_id"] == 2
    asyncio.run(run())


def test_sound_client_waits_for_terminal_completion_after_started():
    class FakeBle:
        is_connected = True
        async def start_notify(self, uuid, callback): self.callback = callback
        async def write_gatt_char(self, uuid, data, response):
            request = SoundFrame.decode(data)
            self.callback(None, SoundFrame(ACCEPTED, request.request_id, 40, request.argument).encode())
            self.callback(None, SoundFrame(STARTED, request.request_id, 40, request.argument).encode())
            asyncio.get_running_loop().call_soon(
                self.callback, None,
                SoundFrame(COMPLETED, request.request_id, 0, request.argument).encode())
    async def run():
        sound = SoundClient(); await sound.attach(FakeBle())
        result = await sound.play(3)
        assert result == {"request_id": 1, "event": COMPLETED,
                          "event_name": "completed", "value": 0,
                          "sound_id": 3, "accepted": True, "started": True}
    asyncio.run(run())
