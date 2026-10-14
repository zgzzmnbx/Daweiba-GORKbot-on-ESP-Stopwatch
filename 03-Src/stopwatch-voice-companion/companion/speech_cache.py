"""Local exact-text audio reuse, including already rendered business values."""
import hashlib
import json
from pathlib import Path
import uuid

from .voice import check_wav, VoiceError


def cache_dir():
    return Path(__file__).resolve().parents[3] / 'Codex-Temp/sentinel-speech/current-voice-v1'


def cacheable_text(text):
    return (isinstance(text, str) and 0 < len(text) <= 300 and bool(text.strip())
            and '{' not in text and '}' not in text)


def key_for(text, profile):
    if not cacheable_text(text):
        raise ValueError('Only complete rendered text can be cached')
    value = json.dumps({'schema': 1, 'text': text, 'profile': profile}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read(text, profile):
    key = key_for(text, profile)
    root = cache_dir()
    try:
        metadata = json.loads((root / (key + '.json')).read_text(encoding='utf-8'))
        audio = (root / (key + '.wav')).read_bytes()
        if not isinstance(metadata, dict) or metadata.get('profile') != profile or metadata.get('sha256') != hashlib.sha256(audio).hexdigest():
            return None
        check_wav(audio)
        return audio
    except (OSError, ValueError, VoiceError):
        return None


def save(text, profile, audio):
    check_wav(audio)
    key = key_for(text, profile)
    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    wav = root / (key + '.wav')
    metadata = root / (key + '.json')
    suffix = '.' + uuid.uuid4().hex + '.tmp'
    staged_wav, staged_metadata = wav.with_name(wav.name + suffix), metadata.with_name(metadata.name + suffix)
    try:
        staged_wav.write_bytes(audio)
        staged_metadata.write_text(json.dumps({'profile':profile, 'sha256':hashlib.sha256(audio).hexdigest()}, sort_keys=True), encoding='utf-8')
        staged_wav.replace(wav)
        staged_metadata.replace(metadata)
    finally:
        staged_wav.unlink(missing_ok=True)
        staged_metadata.unlink(missing_ok=True)
    # Keep repeated business values bounded as well as fixed prompt edits.
    files = sorted(root.glob('*.wav'), key=lambda path:path.stat().st_mtime, reverse=True)
    total = 0
    for index, path in enumerate(files):
        total += path.stat().st_size
        if index >= 256 or total > 64 * 1024 * 1024:
            path.unlink(missing_ok=True)
            path.with_suffix('.json').unlink(missing_ok=True)
