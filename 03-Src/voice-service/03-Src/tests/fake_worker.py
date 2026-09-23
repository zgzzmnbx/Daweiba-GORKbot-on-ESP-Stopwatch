"""Test-only process for failure and cancellation injection; never a provider."""
import time
import numpy as np
from voice_service.audio import encode_wav


def worker(connection, config):
    connection.send({"status": {"asr": {"state": "ready"}, "tts": {"state": "ready"}}})
    try:
        while True:
            message = connection.recv()
            if message is None:
                return
            time.sleep(0.25)
            result = {"text": "测试夹具", "input_seconds": 1.0} if message["kind"] == "asr" else {"audio": encode_wav(np.zeros(2400), 24000), "sample_rate": 24000}
            connection.send({"ok": True, "value": {"provider": "test_fixture", "result": result, "metrics": {"inference_ms": 250, "rtf": 0.25}}})
    except (EOFError, BrokenPipeError):
        pass
