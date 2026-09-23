"""Real offline providers. Loaded only inside the inference process or CLI."""
import time
import os
from pathlib import Path

import numpy as np
import sherpa_onnx

from .audio import decode_wav, encode_wav, resample
from .config import ROOT


def native_directory(value):
    """Avoid espeak's ANSI absolute-path handling on Windows Chinese workspaces."""
    path = Path(value)
    if os.name == "nt":
        path = Path(os.path.relpath(path, Path.cwd()))
        if not str(path).isascii():
            raise ValueError("Native model paths must have ASCII relative names")
    return path


class LocalEngines:
    def __init__(self, config):
        os.chdir(ROOT)
        self.config = config
        self.asr = self.tts = None
        self.status = {}
        for kind in ("asr", "tts"):
            start = time.perf_counter()
            try:
                getattr(self, f"_load_{kind}")()
                loaded = time.perf_counter()
                if kind == "asr":
                    stream = self.asr.create_stream()
                    stream.accept_waveform(16000, np.zeros(8000, dtype=np.float32))
                    self.asr.decode_stream(stream)
                else:
                    self.tts.generate("你好。", sid=config.speaker, speed=1.0)
                self.status[kind] = {"state": "ready", "load_ms": round((loaded-start)*1000, 2),
                    "warmup_ms": round((time.perf_counter()-loaded)*1000, 2)}
            except Exception as exc:
                setattr(self, kind, None)
                self.status[kind] = {"state": "error", "error": type(exc).__name__,
                    "message": f"{kind.upper()} 模型加载失败，请检查模型文件与本地运行日志"}

    def _load_asr(self):
        root = native_directory(self.config.asr_dir)
        for name in ("model.int8.onnx", "tokens.txt"):
            if not (root / name).is_file():
                raise FileNotFoundError(name)
        self.asr = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(root / "model.int8.onnx"), tokens=str(root / "tokens.txt"),
            num_threads=self.config.asr_threads, provider="cpu", language="", use_itn=True)

    def _load_tts(self):
        root = native_directory(self.config.tts_dir)
        for name in ("model.int8.onnx", "voices.bin", "tokens.txt", "lexicon-zh.txt", "lexicon-us-en.txt", "espeak-ng-data"):
            if not (root / name).exists():
                raise FileNotFoundError(name)
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(root / "model.int8.onnx"), voices=str(root / "voices.bin"), tokens=str(root / "tokens.txt"),
                    data_dir=str(root / "espeak-ng-data"),
                    lexicon=",".join(str(root / name) for name in ("lexicon-zh.txt", "lexicon-us-en.txt"))),
                num_threads=self.config.tts_threads, provider="cpu", debug=False),
            rule_fsts=",".join(str(root / name) for name in ("date-zh.fst", "number-zh.fst", "phone-zh.fst") if (root / name).exists()),
            max_num_sentences=1)
        if not config.validate():
            raise ValueError("Invalid Kokoro configuration")
        self.tts = sherpa_onnx.OfflineTts(config)

    def run(self, kind, payload):
        if self.status[kind]["state"] != "ready":
            raise RuntimeError("Model unavailable")
        start = time.perf_counter()
        if kind == "asr":
            samples, duration = decode_wav(payload["audio"], self.config.max_seconds, self.config.max_upload)
            if np.sqrt(np.mean(samples**2)) < 0.0001:
                result = {"text": "", "language": "", "warning": "录音中未检测到有效声音", "input_seconds": duration}
            else:
                stream = self.asr.create_stream()
                stream.accept_waveform(16000, samples)
                self.asr.decode_stream(stream)
                result = {"text": stream.result.text.strip(), "language": getattr(stream.result, "lang", ""), "input_seconds": duration}
            provider = "sherpa_sensevoice"
        else:
            output = self.tts.generate(payload["text"], sid=payload["speaker_id"], speed=payload["speed"])
            rate = payload["sample_rate"]
            samples = resample(output.samples, output.sample_rate, rate)
            duration = len(samples) / rate
            if duration > 180:
                raise ValueError("Output audio exceeds 180 seconds")
            result = {"audio": encode_wav(samples, rate), "sample_rate": rate, "native_sample_rate": output.sample_rate,
                "output_seconds": round(duration, 3), "speaker_id": payload["speaker_id"], "streaming": False}
            provider = "sherpa_kokoro"
        elapsed = (time.perf_counter() - start) * 1000
        return {"provider": provider, "result": result, "metrics": {"inference_ms": round(elapsed, 2), "rtf": round(elapsed / 1000 / duration, 4)}}


def worker_main(connection, config):
    # No network clients are constructed in this process.
    try:
        engines = LocalEngines(config)
        connection.send({"status": engines.status, "sherpa_version": sherpa_onnx.__version__})
        while True:
            item = connection.recv()
            if item is None:
                break
            try:
                connection.send({"ok": True, "value": engines.run(item["kind"], item["payload"])})
            except Exception as exc:
                connection.send({"ok": False, "error": type(exc).__name__})
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()
