import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from .voices import CLOUD_VOICE_IDS

SERVICE_ROOT = Path(__file__).resolve().parents[2]
ROOT = SERVICE_ROOT.parents[1]


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    max_queue: int = 2
    max_seconds: int = 30
    max_upload: int = 2097152
    max_text: int = 300
    asr_dir: str = str(ROOT / "Codex-Temp/voice-runtime/models/sensevoice")
    tts_dir: str = str(ROOT / "Codex-Temp/voice-runtime/models/kokoro")
    asr_threads: int = 4
    tts_threads: int = 4
    asr_timeout: float = 15
    tts_timeout: float = 20
    speaker: int = 3
    asr_mode: str = "local"
    tts_mode: str = "local"
    allow_audio_upload: bool = False
    allow_text_upload: bool = False
    cloud_region: str = "beijing"
    cloud_workspace: str = ""
    cloud_key_env: str = "ZHISUAN_VOICE_DASHSCOPE_API_KEY"
    cloud_asr_model: str = "qwen3-asr-flash"
    cloud_tts_model: str = "qwen3-tts-flash"
    cloud_voice: str = "Cherry"
    cloud_timeout: float = 20
    cloud_request_limit: int = 60


def load_settings(path=None):
    path = Path(path or os.environ.get("VOICE_CONFIG", SERVICE_ROOT / "03-Src/config/voice.example.toml"))
    if not path.is_absolute():
        path = ROOT / path
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported configuration schema")
    for section in ("asr", "tts"):
        if data[section]["mode"] not in ("local", "cloud") or data[section]["execution_provider"] != "cpu":
            raise ValueError("Use local CPU or cloud engines")
    if data['asr']['local_provider'] != 'sherpa_sensevoice' or data['tts']['local_provider'] != 'sherpa_kokoro':
        raise ValueError('Unknown local provider')
    if data['service']['max_active_sessions'] != 1:
        raise ValueError('Only one active session is supported')
    if data["business"]["enabled"] or data["device"]["enabled"]:
        raise ValueError("Business/device integration is not implemented")
    if any(data["privacy"].values()):
        raise ValueError("Persistent recordings/transcript logging are not supported")
    def model_dir(section):
        value = Path(data[section]["model_directory"])
        return str(value if value.is_absolute() else ROOT / value)
    s, a, t = data["service"], data["asr"], data["tts"]
    c = data['cloud']
    if c['region'] not in ('', 'beijing') or c['max_attempts'] != 1:
        raise ValueError('v0.3.0 supports Beijing, one attempt per request')
    if c['asr_base_url'] or c['tts_base_url']:
        raise ValueError('Endpoints are derived from region/workspace; leave base URLs empty')
    if c['workspace_id'] and not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', c['workspace_id']):
        raise ValueError('Invalid workspace ID')
    if c['api_key_env'] != 'ZHISUAN_VOICE_DASHSCOPE_API_KEY':
        raise ValueError('Use this project dedicated API key environment variable')
    if c['asr_model'] != 'qwen3-asr-flash' or c['tts_model'] != 'qwen3-tts-flash' or c['tts_voice'] not in CLOUD_VOICE_IDS:
        raise ValueError('Unsupported cloud model or voice')
    if not (1 <= c['request_timeout_seconds'] <= 120 and 1 <= c['session_request_limit'] <= 300):
        raise ValueError('Invalid cloud request limits')
    if any(type(c[k]) is not bool for k in ('allow_audio_upload', 'allow_text_upload')):
        raise ValueError('Cloud upload permissions must be boolean')
    config = Settings(host=s["host"], port=s["port"], max_queue=s["max_queued_requests"],
        max_seconds=s["max_recording_seconds"], max_upload=s["max_upload_bytes"], max_text=s["max_tts_characters"],
        asr_dir=model_dir("asr"), tts_dir=model_dir("tts"), asr_threads=a["num_threads"], tts_threads=t["num_threads"],
        asr_timeout=a["hard_timeout_seconds"], tts_timeout=t["hard_timeout_seconds"], speaker=t["speaker_id"],
        asr_mode=a['mode'], tts_mode=t['mode'], allow_audio_upload=c['allow_audio_upload'], allow_text_upload=c['allow_text_upload'],
        cloud_workspace=c['workspace_id'], cloud_key_env=c['api_key_env'], cloud_region=c['region'] or 'beijing',
        cloud_asr_model=c['asr_model'], cloud_tts_model=c['tts_model'], cloud_voice=c['tts_voice'],
        cloud_timeout=c['request_timeout_seconds'], cloud_request_limit=c['session_request_limit'])
    if config.host != "127.0.0.1" or not 1024 <= config.port <= 65535:
        raise ValueError("Loopback and an unprivileged port are required")
    if not (1 <= config.max_queue <= 8 and 1 <= config.max_seconds <= 30 and 1 <= config.max_text <= 300):
        raise ValueError("Invalid request limits")
    if not (1024 <= config.max_upload <= 2097152 and 1 <= config.asr_threads <= 16 and 1 <= config.tts_threads <= 16):
        raise ValueError("Invalid upload/thread limits")
    if not (1 <= config.asr_timeout <= 120 and 1 <= config.tts_timeout <= 120 and 3 <= config.speaker <= 102):
        raise ValueError("Invalid timeout or Chinese speaker ID")
    return config
