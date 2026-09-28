"""Process-local Gork sentinel for verified cost task snapshots."""
import asyncio
import contextlib
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import subprocess
import time
import sys

from .voice import VoiceError


def _now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _pc_beep(guard):
    if not guard():
        return 'suppressed'
    if sys.platform != 'win32':
        return 'unavailable'
    import winsound
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    return 'played_by_os'


def _fixed_wav(phrase):
    """Generate one local PCM file per fixed phrase; never call a cloud voice API."""
    if sys.platform != 'win32':
        raise RuntimeError('Windows speech unavailable')
    powershell = shutil.which('powershell.exe')
    if not powershell:
        raise RuntimeError('Windows PowerShell unavailable')
    folder = Path(__file__).resolve().parents[3] / 'Codex-Temp' / 'sentinel-speech'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(phrase.encode('utf-8')).hexdigest() + '.wav')
    if not path.is_file():
        temporary = path.with_suffix('.tmp.wav')
        try:
            subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File',
                            str(Path(__file__).with_name('sentinel_speech.ps1')),
                            '-OutputPath', str(temporary), '-Text', phrase],
                           check=True, timeout=20, capture_output=True)
            from .robot import read_wav
            pcm, rate = read_wav(temporary.read_bytes())
            if len(pcm) > rate * 2 * 10:
                raise RuntimeError('Fixed phrase is too long for Watch')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def _pc_speech(path, guard):
    if not guard():
        return 'suppressed'
    import winsound
    winsound.PlaySound(str(path), winsound.SND_FILENAME)
    return 'played_by_os'


def _attention(snapshot):
    value = snapshot['attention']
    return (value['review_rows'] or 0) > 0 or (value['warning_rows'] or 0) > 0


def _event(previous, current):
    if previous is None or previous['task_id'] != current['task_id']:
        return None
    before, after = previous['activity'], current['activity']
    if before['attempt'] != after['attempt']:
        return None  # A new attempt becomes the next baseline.
    if before['status'] == 'running' and after['status'] == 'failed':
        return ('failed', '本次处理失败，请查看错误。', 'confused', 5)
    if before['status'] == 'running' and after['status'] == 'interrupted':
        return ('interrupted', '本次处理可能中断，请核对任务状态。', 'confused', 5)
    if before['status'] == 'running' and after['status'] == 'completed':
        if _attention(current):
            return ('review', '本次处理结束，请复核结果。', 'curious', 2)
        return ('completed', '本次处理结束，请查看结果。', 'happy', 2)
    if not _attention(previous) and _attention(current):
        return ('review', '有事项需要复核，请查看结果。', 'curious', 2)
    return None


def _terminal_event(previous, current):
    status = current['activity']['status']
    if status not in ('completed', 'failed', 'interrupted'):
        return None
    if previous and previous['activity']['status'] == status:
        if status == 'completed' and not _attention(previous) and _attention(current):
            return ('review', '有事项需要复核，请查看结果。', 'curious', 2)
        return None
    if status == 'failed':
        return ('failed', '本次处理失败，请查看错误。', 'confused', 5)
    if status == 'interrupted':
        return ('interrupted', '本次处理可能中断，请核对任务状态。', 'confused', 5)
    if _attention(current):
        return ('review', '本次处理结束，请复核结果。', 'curious', 2)
    return ('completed', '本次处理结束，请查看结果。', 'happy', 2)


def _stage_event(item):
    stage, status = item['stage'], item['status']
    reviews, warnings = item.get('review_rows'), item.get('warning_rows')
    if stage == 'conversion_start':
        return ('conversion_start', '开始转换，正在识别表格。', 'working', 1, '开始转换')
    if stage == 'match_start':
        return ('match_start', '开始匹配，正在核对规则。', 'working', 1, '开始匹配')
    if stage == 'match_result':
        if status == 'failed':
            return ('match_failed', '匹配未完成，请查看错误。', 'confused', 5, '匹配未完成')
        if reviews is not None and reviews > 0:
            return ('match_result', f'匹配完成，{reviews} 项待复核。', 'curious', 2, '匹配完成，请复核结果')
        return ('match_result', '匹配完成，请查看结果。', 'happy', 2, '匹配完成，请查看结果')
    if stage == 'warning_start':
        return ('warning_start', '正在运行经验池预警。', 'working', 1, '开始运行预警')
    if stage == 'warning_result':
        if status == 'failed':
            return ('warning_failed', '预警未完成，请查看错误。', 'confused', 5, '预警未完成')
        if warnings is not None and warnings > 0:
            return ('warning_result', f'预警完成，{warnings} 项需关注。', 'curious', 2, '预警完成，请查看结果')
        return ('warning_result', '预警完成，请查看结果。', 'happy', 2, '预警完成，请查看结果')
    if stage == 'report_generated':
        return ('report_generated', '报告已生成，请查看成果。', 'happy', 2, '报告已生成')
    if stage == 'review_requested':
        label = '飞书复核' if item.get('platform') == 'feishu' else '协同复核'
        return ('review_requested', f'{label}已发起，等待投递确认。', 'curious', 2, f'{label}已发起')
    if stage == 'review_sent':
        label = '飞书复核' if item.get('platform') == 'feishu' else '协同复核'
        return ('review_sent', f'{label}已发送，请等待同事反馈。', 'curious', 2, f'{label}已发送')
    raise ValueError(stage)


class TaskMonitor:
    def __init__(self, cost, control):
        self.cost, self.control = cost, control
        self.enabled = False
        self.mode = 'auto'
        self.task_id = ''
        self.target = 'desktop'
        self.sound = False
        self.sound_kind = 'speech'
        self.sound_target = 'pc'
        self.epoch = 0
        self.worker = None
        self.current = None
        self.last_result = None
        self.last_success_at = ''
        self.connection_error = ''
        self.history = []
        self.presentation = None
        self.pending = []
        self.watch_started_for = None
        self.seen = {}
        self.seen_event_ids = set()

    def state(self):
        presentation = self.presentation if self.presentation and time.monotonic() < self.presentation['until'] else None
        deferred = self.pending[0] if self.pending and time.monotonic() < self.pending[0]['until'] else None
        return {'enabled': self.enabled, 'mode': self.mode, 'task_id': self.task_id,
                'target': self.target, 'sound': self.sound, 'sound_kind': self.sound_kind,
                'sound_target': self.sound_target,
                'current': self.current,
                'last_result': self.last_result, 'last_success_at': self.last_success_at,
                'connection_error': self.connection_error, 'history': list(self.history),
                'deferred': ({'task_id': deferred['snapshot']['task_id'],
                              'message': deferred['event'][1],
                              'reason': self.control.auto_block_reason()}
                             if deferred else None),
                'presentation': ({key: value for key, value in presentation.items() if key != 'until'}
                                 if presentation else None)}

    async def configure(self, *, enabled, mode='auto', task_id='', target='desktop', sound=False,
                        sound_kind='speech', sound_target='pc'):
        if (mode not in ('auto', 'specific') or target not in ('desktop', 'watch', 'both')
                or sound_target not in ('pc', 'watch') or sound_kind not in ('speech', 'beep')):
            raise VoiceError(422, 'MONITOR_SETTINGS', '任务哨兵设置无效')
        if enabled and mode == 'specific' and not task_id:
            raise VoiceError(422, 'MONITOR_TASK_REQUIRED', '指定任务模式需选择任务')
        # Changes invalidate old HTTP/BLE work before cancellation is awaited.
        self.epoch += 1
        old = self.worker
        self.worker = None
        if old:
            old.cancel()
        self.enabled, self.mode, self.task_id = enabled, mode, task_id if mode == 'specific' else ''
        self.target, self.sound, self.sound_kind, self.sound_target = target, sound, sound_kind, sound_target
        self.current = None
        self.connection_error = ''
        self.presentation = None
        self.pending = []
        self.watch_started_for = None
        self.seen = {}
        self.seen_event_ids = set()
        if old:
            with contextlib.suppress(asyncio.CancelledError):
                await old
        if enabled:
            self.worker = asyncio.create_task(self._run(self.epoch))
        return self.state()

    async def stop(self):
        await self.configure(enabled=False)

    async def _run(self, epoch):
        failures = 0
        baseline = False
        while self.enabled and epoch == self.epoch:
            try:
                recent, events = [], []
                if self.mode == 'specific':
                    snapshot = await self.cost.monitor_task(self.task_id)
                    feed = await self.cost.monitor_feed()
                    events = [item for item in feed.get('events', []) if item['task_id'] == self.task_id]
                else:
                    feed = await self.cost.monitor_feed()
                    snapshot, recent = feed['task'], feed['recent']
                    events = feed.get('events', [])
                if epoch != self.epoch or not self.enabled:
                    return
                self.connection_error = ''
                self.last_success_at = _now()
                match_results = {(item['task_id'], item.get('attempt')) for item in events
                                 if item['stage'] == 'match_result' and item.get('attempt')}
                fresh_warnings = {item['task_id'] for item in events if item['stage'] == 'warning_result'
                                  and item['event_id'] not in self.seen_event_ids}
                for item in reversed(events):
                    event_id = item['event_id']
                    if baseline and event_id not in self.seen_event_ids:
                        self.pending.append({'snapshot': item, 'event': _stage_event(item),
                                             'until': time.monotonic() + 300, 'milestone': True})
                    self.seen_event_ids.add(event_id)
                if len(self.seen_event_ids) > 2000:
                    self.seen_event_ids = {item['event_id'] for item in events}
                observed = ([snapshot] if snapshot else []) + list(reversed(recent))
                for item in observed:
                    attempt = item['activity']['attempt']
                    if not attempt:
                        continue
                    key = (item['task_id'], attempt)
                    previous = self.seen.get(key)
                    if baseline and key not in match_results and item['task_id'] not in fresh_warnings:
                        event = _terminal_event(previous, item)
                        if event:
                            self.pending.append({'snapshot': item, 'event': event,
                                                 'until': time.monotonic() + 90})
                            self.last_result = item
                    elif event := next((entry for entry in events if entry['task_id'] == item['task_id']
                                        and entry['stage'] == 'match_result'
                                        and entry.get('attempt') == attempt), None):
                        self.last_result = item
                    self.seen[key] = item
                while len(self.seen) > 1000:
                    del self.seen[next(iter(self.seen))]
                baseline = True
                if snapshot is not None:
                    watch_key = (snapshot['task_id'], snapshot['activity']['attempt'])
                    if (snapshot['activity']['status'] == 'running'
                            and self.target in ('watch', 'both')
                            and watch_key != self.watch_started_for
                            and self.control.auto_available()):
                        guard = lambda: self.enabled and epoch == self.epoch and self.control.auto_available()
                        try:
                            if await self.control.robot.auto_expression('working', guard) == 'accepted':
                                self.watch_started_for = watch_key
                        except Exception:
                            pass
                    self.current = snapshot if self.mode == 'specific' or snapshot['activity']['status'] == 'running' else None
                else:
                    self.current = None

                if self.pending:
                    pending = self.pending[0]
                    if time.monotonic() >= pending['until']:
                        self.pending.pop(0)
                    elif self.control.auto_available():
                        if await self._notify(epoch, pending['snapshot'], pending['event']):
                            self.pending.pop(0)
                failures = 0
                delay = 1 if self.pending else (2 if snapshot and snapshot['activity']['status'] == 'running' else 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                if epoch != self.epoch:
                    return
                self.connection_error = '造价智算连接暂不可用；上次状态保留。'
                # Recovered connections establish a fresh baseline.
                baseline = False
                self.seen.clear()
                self.pending = []
                self.seen_event_ids.clear()
                failures += 1
                delay = min(30, 2 ** min(failures, 5))
            await asyncio.sleep(delay)

    async def _notify(self, epoch, snapshot, event):
        kind, message, expression, sound_id = event[:4]
        speech = event[4] if len(event) > 4 else message
        valid = lambda: self.enabled and epoch == self.epoch and self.control.auto_available()
        if not valid():
            return False
        delivery = {'desktop': 'not_requested', 'watch': 'not_requested', 'sound': 'off'}
        if self.target in ('desktop', 'both'):
            self.presentation = {'expression': expression, 'bubble': message,
                                 'at': _now(), 'until': time.monotonic() + 12}
            delivery['desktop'] = 'displayed'
        if self.target in ('watch', 'both'):
            try:
                watch_message = message if len(message) <= 24 else message[:23] + '…'
                delivery['watch'] = await self.control.robot.auto_notify(expression, watch_message, valid)
            except Exception:
                delivery['watch'] = 'failed'
        if self.sound and valid():
            try:
                if self.sound_kind == 'speech':
                    wav = await asyncio.to_thread(_fixed_wav, speech)
                    if not valid():
                        delivery['sound'] = 'suppressed'
                    elif self.sound_target == 'pc':
                        delivery['sound'] = await asyncio.to_thread(_pc_speech, wav, valid)
                    else:
                        watch_text = message if self.target in ('watch', 'both') else ''
                        delivery['sound'] = await self.control.robot.auto_speech(
                            wav.read_bytes(), watch_text, valid,
                            expression if watch_text else None)
                elif self.sound_target == 'pc':
                    delivery['sound'] = await asyncio.to_thread(_pc_beep, valid)
                else:
                    delivery['sound'] = await self.control.robot.auto_sound(sound_id, valid)
            except Exception:
                delivery['sound'] = 'failed'
        if epoch != self.epoch:
            return False
        self.history.insert(0, {'at': _now(), 'task_id': snapshot['task_id'],
                                'task_name': snapshot['task_name'], 'kind': kind,
                                'message': message, 'delivery': delivery})
        del self.history[20:]
        return True
