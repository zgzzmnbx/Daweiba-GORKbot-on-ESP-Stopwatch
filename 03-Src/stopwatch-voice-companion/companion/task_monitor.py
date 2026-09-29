"""Process-local Gork sentinel for verified cost task snapshots."""
import asyncio
import contextlib
from datetime import datetime
import time
import sys
import wave

from .voice import VoiceError
from .sentinel_voice_library import cached_path


def _now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _now_ms():
    return datetime.now().astimezone().isoformat(timespec='milliseconds')


def _pc_beep(guard):
    if not guard():
        return 'suppressed'
    if sys.platform != 'win32':
        return 'unavailable'
    import winsound
    winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    return 'started_by_os'


def _fixed_wav(phrase):
    """Read a pre-generated Cherry WAV; never synthesize during a task reminder."""
    return cached_path(phrase)


def _pc_speech(path, guard):
    if not guard():
        return 'suppressed'
    import winsound
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    return 'started_by_os'


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


def _start_superseded(item, events):
    """Do not announce a start after the same operation has already advanced."""
    followups = {'conversion_start': {'match_start', 'match_result'},
                 'match_start': {'match_result'}, 'warning_start': {'warning_result'}}
    expected = followups.get(item['stage'])
    if not expected:
        return False
    try:
        started = datetime.fromisoformat(item['occurred_at'])
        if started.tzinfo is None:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    for later in events:
        if later['task_id'] != item['task_id'] or later['stage'] not in expected:
            continue
        if item['stage'] == 'match_start' and (not item.get('attempt') or later.get('attempt') != item['attempt']):
            continue
        try:
            finished = datetime.fromisoformat(later['occurred_at'])
            if finished.tzinfo is not None and finished > started:
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


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
                    if baseline and event_id not in self.seen_event_ids and not _start_superseded(item, events):
                        self.pending.append({'snapshot': item, 'event': _stage_event(item),
                                             'until': time.monotonic() + 300, 'milestone': True,
                                             'detected_at': _now_ms()})
                    self.seen_event_ids.add(event_id)
                self.pending = [entry for entry in self.pending
                                if not entry.get('milestone') or not _start_superseded(entry['snapshot'], events)]
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
                                                 'until': time.monotonic() + 90,
                                                 'detected_at': _now_ms()})
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
                    self.current = snapshot if self.mode == 'specific' or snapshot['activity']['status'] == 'running' else None
                else:
                    self.current = None

                if self.pending:
                    pending = self.pending[0]
                    if time.monotonic() >= pending['until']:
                        self.pending.pop(0)
                    elif self.control.auto_available():
                        if await self._notify(epoch, pending['snapshot'], pending['event'],
                                              pending.get('detected_at', '')):
                            if (snapshot is not None and pending['event'][0] in ('conversion_start', 'match_start')
                                    and pending['snapshot']['task_id'] == snapshot['task_id']
                                    and (not pending['snapshot'].get('attempt')
                                         or pending['snapshot']['attempt'] == snapshot['activity']['attempt'])
                                    and self.history and self.history[0]['delivery']['watch'] == 'accepted'):
                                self.watch_started_for = (snapshot['task_id'], snapshot['activity']['attempt'])
                            self.pending.pop(0)
                if snapshot is not None:
                    watch_key = (snapshot['task_id'], snapshot['activity']['attempt'])
                    if (snapshot['activity']['status'] == 'running'
                            and self.target in ('watch', 'both')
                            and watch_key != self.watch_started_for
                            and not getattr(getattr(self.control, 'notifications', None), 'active', False)
                            and not getattr(getattr(self.control, 'notifications', None), 'queue', [])
                            and self.control.auto_available()):
                        guard = lambda: self.enabled and epoch == self.epoch and self.control.auto_available()
                        try:
                            if await self.control.robot.auto_expression('working', guard) == 'accepted':
                                self.watch_started_for = watch_key
                        except Exception:
                            pass
                failures = 0
                # Event discovery should not trail a new operation by an idle 5 s or running 2 s sleep.
                # Drain already queued milestones immediately, but wait when human/device priority blocks output.
                delay = 0 if self.pending and self.control.auto_available() else 1
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

    async def _notify(self, epoch, snapshot, event, detected_at=''):
        kind, message, expression, sound_id = event[:4]
        speech = event[4] if len(event) > 4 else message
        valid = lambda: self.enabled and epoch == self.epoch and self.control.auto_available()
        if not valid():
            return False
        async def coordinated():
            return await self._notify_locked(epoch, snapshot, event, detected_at)
        coordinator = getattr(self.control, 'notifications', None)
        if coordinator is None:
            return await coordinated()
        return await coordinator.dispatch(
            source='cost', priority=event[3] if len(event) > 3 else 2,
            valid=valid, action=coordinated)

    async def _notify_locked(self, epoch, snapshot, event, detected_at=''):
        kind, message, expression, sound_id = event[:4]
        speech = event[4] if len(event) > 4 else message
        valid = lambda: self.enabled and epoch == self.epoch and self.control.auto_available()
        if not valid():
            return False
        started_at = _now_ms()
        delivery = {'desktop': 'not_requested', 'watch': 'not_requested', 'sound': 'off'}
        if self.target in ('desktop', 'both'):
            self.presentation = {'expression': expression, 'bubble': message,
                                 'at': _now(), 'until': time.monotonic() + 12}
            if getattr(self.control, 'notifications', None):
                self.control.notifications.show('cost', expression, message,
                                                self.epoch + len(self.history) + 1,
                                                priority=sound_id)
            delivery['desktop'] = 'displayed'
        async def pc_alert():
            try:
                if self.sound_kind == 'speech':
                    wav = await asyncio.to_thread(_fixed_wav, speech)
                    if not valid():
                        return 'suppressed'
                    with wave.open(str(wav), 'rb') as sound:
                        duration = min(15, sound.getnframes() / sound.getframerate())
                    result = _pc_speech(wav, valid)
                else:
                    duration = 0.5
                    result = _pc_beep(valid)
                await asyncio.sleep(duration)
                return result if valid() else 'suppressed'
            except asyncio.CancelledError:
                self.control.stop_auto_tone()
                raise
            except FileNotFoundError:
                return 'cache_missing'
            except Exception:
                return 'failed'
        # PC audio can start while Watch receives its independent expression/text channel.
        pc_task = (asyncio.create_task(pc_alert())
                   if self.sound and self.sound_target == 'pc' and valid() else None)
        try:
            if self.target in ('watch', 'both'):
                try:
                    watch_message = message if len(message) <= 24 else message[:23] + '…'
                    delivery['watch'] = await self.control.robot.auto_notify(expression, watch_message, valid)
                except Exception:
                    delivery['watch'] = 'failed'
            if pc_task:
                delivery['sound'] = await pc_task
            elif self.sound and valid():
                try:
                    if self.sound_kind == 'speech':
                        wav = await asyncio.to_thread(_fixed_wav, speech)
                        if not valid():
                            delivery['sound'] = 'suppressed'
                        else:
                            watch_text = message if self.target in ('watch', 'both') else ''
                            delivery['sound'] = await self.control.robot.auto_speech(
                                wav.read_bytes(), watch_text, valid,
                                expression if watch_text else None)
                    else:
                        delivery['sound'] = await self.control.robot.auto_sound(sound_id, valid)
                except FileNotFoundError:
                    delivery['sound'] = 'cache_missing'
                except Exception:
                    delivery['sound'] = 'failed'
        finally:
            if pc_task and not pc_task.done():
                pc_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pc_task
        if epoch != self.epoch:
            return False
        self.history.insert(0, {'at': _now(), 'source_at': snapshot.get('occurred_at') or snapshot.get('activity', {}).get('updated_at', ''),
                                'detected_at': detected_at, 'response_started_at': started_at,
                                'task_id': snapshot['task_id'],
                                'task_name': snapshot['task_name'], 'kind': kind,
                                'message': message, 'delivery': delivery})
        del self.history[20:]
        return True
