import io
import math
import wave

import numpy as np
from scipy.signal import resample_poly


class AudioError(ValueError):
    pass


def decode_wav(data, max_seconds=30, max_bytes=2097152):
    if len(data) > max_bytes:
        raise AudioError("音频超过大小限制")
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise AudioError("仅支持 16kHz、16bit、单声道 PCM WAV，请使用页面录音或先转换文件")
            frames = audio.getnframes()
            if not 1600 <= frames <= max_seconds * 16000:
                raise AudioError(f"音频时长须为 0.1～{max_seconds} 秒")
            raw = audio.readframes(frames)
            if len(raw) != frames * 2:
                raise AudioError("WAV 数据被截断")
    except (wave.Error, EOFError, OSError) as exc:
        raise AudioError("无法读取 PCM WAV 文件") from exc
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if np.mean(np.abs(samples) >= 0.999) > 0.1:
        raise AudioError("录音严重削波，请降低麦克风增益后重试")
    return samples, frames / 16000


def encode_wav(samples, rate):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.size == 0 or not np.isfinite(samples).all():
        raise AudioError("模型未返回有效音频")
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return output.getvalue()


def resample(samples, source_rate, target_rate):
    if source_rate == target_rate:
        return samples
    factor = math.gcd(source_rate, target_rate)
    return resample_poly(samples, target_rate // factor, source_rate // factor).astype(np.float32)
