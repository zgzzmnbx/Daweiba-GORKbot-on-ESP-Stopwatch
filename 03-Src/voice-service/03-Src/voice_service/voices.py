"""Supported subset of Qwen3-TTS-Flash voices, checked 2026-09-23.

Source: https://www.alibabacloud.com/help/zh/model-studio/qwen-tts-voice-list
Keep this catalogue in the service; clients discover it through capabilities.
"""
CLOUD_VOICES = [
    {"id": "Cherry", "label": "芊悦 · Cherry"},
    {"id": "Serena", "label": "苏瑶 · Serena"},
    {"id": "Ethan", "label": "晨煦 · Ethan"},
    {"id": "Chelsie", "label": "千雪 · Chelsie"},
    {"id": "Momo", "label": "茉兔 · Momo"},
    {"id": "Moon", "label": "月白 · Moon"},
]
CLOUD_VOICE_IDS = frozenset(item["id"] for item in CLOUD_VOICES)
