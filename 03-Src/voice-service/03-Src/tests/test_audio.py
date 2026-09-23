import io
import wave
import numpy as np
import pytest
from voice_service.audio import AudioError, decode_wav, encode_wav, resample


def test_pcm_roundtrip_and_true_resampling():
    source = np.sin(2 * np.pi * 440 * np.arange(24000) / 24000).astype(np.float32) * 0.3
    converted = resample(source, 24000, 16000)
    assert len(converted) == 16000
    audio, duration = decode_wav(encode_wav(converted, 16000))
    assert duration == 1
    assert np.max(np.abs(audio - converted)) < 0.0001
    frequency = np.argmax(np.abs(np.fft.rfft(audio)))
    assert frequency == 440  # Changing only a WAV header would fail this test.


@pytest.mark.parametrize("value", [b"not wav", b"", b"RIFF1234WAVE"])
def test_invalid_wav(value):
    with pytest.raises(AudioError):
        decode_wav(value)


def test_truncated_clipped_long_and_wrong_rate():
    valid = encode_wav(np.zeros(16000), 16000)
    for value in (valid[:-10], encode_wav(np.ones(16000), 16000), encode_wav(np.zeros(16000*31), 16000), encode_wav(np.zeros(24000), 24000)):
        with pytest.raises(AudioError):
            decode_wav(value)


def test_stereo_rejected():
    output = io.BytesIO()
    with wave.open(output, "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(16000); f.writeframes(b"\0" * 64000)
    with pytest.raises(AudioError):
        decode_wav(output.getvalue())
