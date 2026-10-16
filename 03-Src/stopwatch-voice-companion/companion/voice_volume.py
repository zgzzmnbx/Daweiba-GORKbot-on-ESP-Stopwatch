"""Local PC speech gain; never modifies system/Watch volume or cached audio."""
from array import array
import io
import json
from pathlib import Path
import sys
import wave

class VoiceVolume:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.value = 100
        if self.path:
            try:
                value = json.loads(self.path.read_text(encoding='utf-8'))['volume']
                if type(value) is int and 0 <= value <= 100:
                    self.value = value
            except (OSError, ValueError, TypeError, KeyError):
                pass

    def save(self, value):
        if self.path:
            from .external_setup import write_private
            write_private(self.path, {'volume': value})
        self.value = value


def scale_speech_wav(audio, volume):
    if volume == 100:
        return audio
    with wave.open(io.BytesIO(audio), 'rb') as source:
        params = source.getparams()
        if source.getsampwidth() != 2 or source.getcomptype() != 'NONE':
            raise ValueError('PC speech volume requires PCM16 WAV')
        samples = array('h', source.readframes(source.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    samples = array('h', (round(sample * volume / 100) for sample in samples))
    if sys.byteorder != 'little':
        samples.byteswap()
    result = io.BytesIO()
    with wave.open(result, 'wb') as target:
        target.setparams(params)
        target.writeframes(samples.tobytes())
    return result.getvalue()
