"""Versioned, local-only library of the sentinel's fixed Cherry announcements."""
import hashlib
from pathlib import Path
import wave

from .robot import read_wav

VOICE = 'Cherry'
VOICE_LABEL = '芊悦 · Cherry'
MODEL = 'qwen3-tts-flash'
PHRASES = (
    ('conversion_start', '转换', '开始转换'),
    ('match_start', '匹配', '开始匹配'),
    ('match_review', '匹配', '匹配完成，请复核结果'),
    ('match_result', '匹配', '匹配完成，请查看结果'),
    ('match_failed', '匹配', '匹配未完成'),
    ('warning_start', '预警', '开始运行预警'),
    ('warning_result', '预警', '预警完成，请查看结果'),
    ('warning_failed', '预警', '预警未完成'),
    ('report_generated', '报告', '报告已生成'),
    ('feishu_review_requested', '复核', '飞书复核已发起'),
    ('other_review_requested', '复核', '协同复核已发起'),
    ('feishu_review_sent', '复核', '飞书复核已发送'),
    ('other_review_sent', '复核', '协同复核已发送'),
    ('task_failed', '任务', '本次处理失败，请查看错误。'),
    ('task_interrupted', '任务', '本次处理可能中断，请核对任务状态。'),
    ('task_review', '任务', '本次处理结束，请复核结果。'),
    ('task_completed', '任务', '本次处理结束，请查看结果。'),
    ('task_attention', '任务', '有事项需要复核，请查看结果。'),
)
BY_ID = {item[0]: item for item in PHRASES}
BY_TEXT = {item[2]: item for item in PHRASES}


def cache_dir():
    return Path(__file__).resolve().parents[3] / 'Codex-Temp' / 'sentinel-speech' / 'cherry-qwen3-tts-flash-v1'


def path_for(phrase):
    if phrase not in BY_TEXT:
        raise ValueError('Unknown fixed sentinel phrase')
    digest = hashlib.sha256(f'{MODEL}\0{VOICE}\0{phrase}'.encode('utf-8')).hexdigest()[:24]
    return cache_dir() / f'{digest}.wav'


def validate(data):
    """The same size, rate and duration constraints as Watch playback."""
    try:
        read_wav(data)
    except (wave.Error, EOFError, ValueError) as exc:
        raise ValueError('Invalid sentinel WAV') from exc
    return data


def cached_path(phrase):
    path = path_for(phrase)
    if not path.is_file():
        raise FileNotFoundError(f'播报语音尚未生成：{phrase}')
    try:
        validate(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f'播报语音文件损坏：{phrase}') from exc
    return path


def save(phrase, data):
    validate(data)
    path = path_for(phrase)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def catalogue():
    entries = []
    for item_id, group, phrase in PHRASES:
        try:
            cached_path(phrase)
            ready = True
        except (FileNotFoundError, ValueError):
            ready = False
        entries.append({'id': item_id, 'group': group, 'text': phrase, 'ready': ready})
    return {'voice': VOICE, 'voice_label': VOICE_LABEL, 'model': MODEL,
            'ready': sum(item['ready'] for item in entries), 'total': len(entries),
            'items': entries}
