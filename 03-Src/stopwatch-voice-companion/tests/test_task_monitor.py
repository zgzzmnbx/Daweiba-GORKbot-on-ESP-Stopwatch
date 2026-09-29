import asyncio
import time
import uuid

import httpx
import pytest

from companion.app import create_app, _sentinel_preferences
from companion.control import Controller
from companion.cost import CostClient, monitor_snapshot
from companion.robot import Robot
import companion.task_monitor as task_monitor_module
from companion.task_monitor import TaskMonitor, _event, _stage_event, _fixed_wav, _start_superseded
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice


def snapshot(status, attempt='a', review=None, warning=None):
    return {'task_id': 'tsk_' + 'a' * 24, 'task_name': '测试任务', 'project_id': '',
            'task_status': 'processing', 'activity': {'status': status, 'attempt': attempt},
            'attention': {'review_rows': review, 'warning_rows': warning}}


def test_baseline_completion_and_new_attempt_semantics():
    assert _event(None, snapshot('completed', review=1)) is None
    assert _event(snapshot('running'), snapshot('completed', review=2))[0:2] == (
        'review', '本次处理结束，请复核结果。')
    assert _event(snapshot('running'), snapshot('completed'))[1] == '本次处理结束，请查看结果。'
    assert _event(snapshot('running'), snapshot('failed'))[0] == 'failed'
    assert _event(snapshot('running'), snapshot('interrupted'))[1] == '本次处理可能中断，请核对任务状态。'
    assert _event(snapshot('completed', review=0), snapshot('completed', review=1))[0] == 'review'
    assert _event(snapshot('running', 'a'), snapshot('completed', 'b')) is None
    assert _event(snapshot('completed'), snapshot('completed')) is None


def test_disabled_never_reads_and_stop_invalidates_pending_output():
    class Cost:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = False
        async def monitor_feed(self):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
    class Control:
        def auto_available(self):
            return True
    async def run():
        cost = Cost()
        monitor = TaskMonitor(cost, Control())
        assert not monitor.enabled and not cost.started.is_set()
        await monitor.configure(enabled=True)
        await asyncio.wait_for(cost.started.wait(), 1)
        await monitor.stop()
        assert cost.cancelled and not monitor.enabled and monitor.current is None
        assert monitor.presentation is None and not monitor.history
    asyncio.run(run())


def test_cost_monitor_contract_filters_untrusted_fields_and_validates_identity():
    async def run():
        paths = []
        def handler(request):
            paths.append(request.url.path)
            if request.url.path == '/api/health':
                return httpx.Response(200, json={'service':'guankanzhisuan','status':'ok'})
            item = snapshot('running', review=None)
            item.update({'data_status':'linked', 'debug':{'secret':'do not forward'},
                         'activity':{'type':'batch_match','status':'running','attempt':'a',
                                     'started_at':'2026-09-28T10:00:00+08:00','debug':'hidden'},
                         'attention':{'review_rows':None,'warning_rows':None,'warning_checked':False}})
            return httpx.Response(200, json={'task':item,'recent':[]} if request.url.path.endswith('/current') else item)
        cost = CostClient(transport=httpx.MockTransport(handler))
        current = await cost.current_task()
        assert current['activity']['status'] == 'running'
        assert current['attention']['review_rows'] is None
        assert 'secret' not in str(current) and 'hidden' not in str(current)
        await cost.monitor_task(current['task_id'])
        assert paths == ['/api/health','/api/task-monitor/current',
                         '/api/health',f"/api/tasks/{current['task_id']}/monitor"]
        await cost.close()
    asyncio.run(run())


def test_unknown_cost_activity_cannot_be_presented_as_batch_matching():
    value = snapshot('running')
    value['activity']['type'] = 'other_operation'
    with pytest.raises(VoiceError):
        monitor_snapshot(value)


def test_sentinel_api_requires_workspace_and_keeps_manual_off_after_restart(tmp_path):
    class Cost:
        def __init__(self):
            self.reads = 0
        async def monitor_feed(self):
            self.reads += 1
            return {'task': None, 'recent': []}
        async def close(self):
            pass
    async def run():
        path = tmp_path / 'sentinel.local.json'
        cost = Cost()
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app({'sentinel_state_path': path}, controller=control, cost_client=cost)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url='http://127.0.0.1:8766',
                    headers={'X-Companion-Client':str(uuid.uuid4())}) as client:
                assert (await client.get('/api/cost/sentinel')).json()['enabled'] is True
                await asyncio.sleep(0)
                assert cost.reads >= 1
                payload = {'enabled': False, 'mode': 'auto', 'target': 'both', 'sound': True}
                assert (await client.put('/api/cost/sentinel', json=payload)).status_code == 401
                assert (await client.post('/api/workspace', json={})).status_code == 200
                assert (await client.put('/api/cost/sentinel', json={**payload,'enabled':True,'mode':'specific'})).status_code == 422
                assert (await client.put('/api/cost/sentinel', json=payload)).status_code == 200
                assert (await client.get('/api/cost/sentinel')).json()['enabled'] is False
        next_cost = Cost()
        next_app = create_app({'sentinel_state_path': path}, controller=Controller(FakeVoice(), FakeRobot()), cost_client=next_cost)
        async with next_app.router.lifespan_context(next_app):
            assert next_app.state.task_monitor.state()['enabled'] is False
            await asyncio.sleep(0)
            assert next_cost.reads == 0
            assert next_app.state.task_monitor.state()['target'] == 'both'
    asyncio.run(run())


def test_invalid_saved_sentinel_setting_stays_off(tmp_path):
    path = tmp_path / 'sentinel.local.json'
    assert _sentinel_preferences(path)['enabled'] is True
    path.write_text('{broken', encoding='utf-8')
    assert _sentinel_preferences(path)['enabled'] is False


def test_desktop_auto_layer_yields_to_manual_and_voice():
    control = Controller(FakeVoice(), FakeRobot())
    monitor = TaskMonitor(None, control)
    control.task_monitor = monitor
    monitor.enabled = True
    monitor.current = snapshot('running')
    assert control.desktop_state()['character']['expression'] == 'working'
    control.character['manual'] = True
    control.manual_until = time.monotonic() + 15
    assert control.desktop_state()['character'].get('auto') is None
    control.manual_until = 0
    assert control.desktop_state()['character']['expression'] == 'working'
    control.phase = 'listening'
    assert control.desktop_state()['character'].get('auto') is None


def test_busy_completion_is_delivered_once_after_manual_priority(monkeypatch):
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        await original_sleep(0.001)

    monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', fast_sleep)

    class Cost:
        def __init__(self):
            self.calls = 0
            self.terminal_seen = asyncio.Event()

        async def monitor_feed(self):
            self.calls += 1
            if self.calls == 1:
                return {'task': snapshot('running'), 'recent': []}
            self.terminal_seen.set()
            return {'task': None, 'recent': [snapshot('completed', review=2)]}

    class Robot:
        def __init__(self):
            self.notified = asyncio.Event()
            self.messages = []

        async def auto_expression(self, _expression, _guard):
            return 'accepted'

        async def auto_notify(self, expression, message, guard):
            if not guard():
                return 'suppressed'
            self.messages.append((expression, message))
            self.notified.set()
            return 'accepted'

    class Control:
        def __init__(self):
            self.busy = True
            self.robot = Robot()

        def auto_available(self):
            return not self.busy

        def auto_block_reason(self):
            return '人工角色操作优先' if self.busy else ''

    async def run():
        cost, control = Cost(), Control()
        monitor = TaskMonitor(cost, control)
        await monitor.configure(enabled=True, target='both')
        await asyncio.wait_for(cost.terminal_seen.wait(), 1)
        await original_sleep(0.03)
        assert monitor.pending and monitor.history == []
        assert monitor.state()['deferred']['reason'] == '人工角色操作优先'
        control.busy = False
        await asyncio.wait_for(control.robot.notified.wait(), 1)
        await original_sleep(0.03)
        assert len(monitor.history) == 1
        assert monitor.history[0]['delivery']['desktop'] == 'displayed'
        assert monitor.history[0]['delivery']['watch'] == 'accepted'
        assert control.robot.messages == [('curious', '本次处理结束，请复核结果。')]
        await monitor.stop()

    asyncio.run(run())


def test_short_task_completion_survives_poll_gap_without_replaying_old_tasks(monkeypatch):
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        await original_sleep(0.001)

    monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', fast_sleep)
    old = snapshot('completed', attempt='old')
    current = {**snapshot('completed', attempt='new'), 'task_id': 'tsk_' + 'b' * 24}
    with_warning = {**current, 'attention': {'review_rows': 0, 'warning_rows': 2}}

    class Cost:
        calls = 0

        async def monitor_feed(self):
            self.calls += 1
            if self.calls == 1:
                return {'task': None, 'recent': [old]}
            if self.calls == 2:
                return {'task': None, 'recent': [current, old]}
            return {'task': None, 'recent': [with_warning, old]}

    class Robot:
        def __init__(self):
            self.messages = []
            self.twice = asyncio.Event()

        async def auto_notify(self, expression, message, guard):
            assert guard()
            self.messages.append((expression, message))
            if len(self.messages) == 2:
                self.twice.set()
            return 'accepted'

    class Control:
        def __init__(self):
            self.robot = Robot()

        def auto_available(self):
            return True

    async def run():
        cost, control = Cost(), Control()
        monitor = TaskMonitor(cost, control)
        await monitor.configure(enabled=True, target='both')
        await asyncio.wait_for(control.robot.twice.wait(), 1)
        await original_sleep(0.03)
        assert [row['task_id'] for row in monitor.history] == [current['task_id'], current['task_id']]
        assert [row['kind'] for row in reversed(monitor.history)] == ['completed', 'review']
        assert len(control.robot.messages) == 2
        assert monitor.last_result['attention']['warning_rows'] == 2
        await monitor.stop()

    asyncio.run(run())


def test_watch_auto_command_yields_after_waiting_for_manual_ble_writer():
    class Device:
        connected = True

        def __init__(self):
            self.commands = []

        async def send_command(self, value):
            self.commands.append(value)
            return 'OK'

        async def send_text(self, value):
            self.commands.append(value)
            return 'OK'

    async def run():
        device = Device()
        robot = Robot(client=device)
        robot.enabled = True
        control = Controller(FakeVoice(), robot)
        monitor = TaskMonitor(None, control)
        monitor.enabled = True
        guard = lambda: monitor.enabled and control.auto_available()
        async with robot.lock:
            pending = asyncio.create_task(robot.auto_notify('curious', '请复核结果', guard))
            await asyncio.sleep(0)
            control.manual_until = time.monotonic() + 15
        assert await pending == 'suppressed'
        assert device.commands == []

    asyncio.run(run())


def test_stage_text_expressions_and_fixed_speech():
    expected = {
        'conversion_start': ('working', '开始转换'),
        'match_start': ('working', '开始匹配'),
        'match_result': ('curious', '匹配完成，请复核结果'),
        'warning_start': ('working', '开始运行预警'),
        'warning_result': ('curious', '预警完成，请查看结果'),
        'report_generated': ('happy', '报告已生成'),
        'review_requested': ('curious', '协同复核已发起'),
        'review_sent': ('curious', '协同复核已发送'),
    }
    for stage, (expression, phrase) in expected.items():
        event = _stage_event({'stage': stage, 'status': 'completed',
                              'review_rows': 2, 'warning_rows': 1})
        assert event[2] == expression and event[4] == phrase
    assert '2 项待复核' in _stage_event({'stage': 'match_result', 'status': 'completed',
                                     'review_rows': 2})[1]
    assert _stage_event({'stage': 'warning_result', 'status': 'failed'})[2] == 'confused'
    assert _stage_event({'stage': 'review_sent', 'status': 'sent', 'platform': 'feishu'})[1].startswith('飞书复核已发送')


def test_start_cue_is_discarded_when_its_result_is_already_visible():
    task_id = 'tsk_' + 'a' * 24
    def milestone(stage, second, attempt=''):
        return {'event_id': str(second).zfill(32), 'task_id': task_id, 'task_name': '任务',
                'stage': stage, 'status': 'running' if stage.endswith('start') else 'completed',
                'attempt': attempt, 'occurred_at': f'2026-09-29T01:00:{second:02d}+08:00'}
    conversion = milestone('conversion_start', 10)
    match = milestone('match_start', 12, 'current')
    result = milestone('match_result', 14, 'current')
    old_result = milestone('match_result', 9, 'previous')
    warning = milestone('warning_start', 16)
    warning_result = milestone('warning_result', 18)
    assert _start_superseded(conversion, [match, result])
    assert _start_superseded(match, [result])
    assert _start_superseded(warning, [warning_result])
    assert not _start_superseded(match, [old_result])
    assert not _start_superseded(milestone('match_start', 19, 'next'), [result])


def test_idle_and_running_poll_interval_is_one_second(monkeypatch):
    async def exercise(active):
        times = []
        class Cost:
            async def monitor_feed(self):
                return {'task': snapshot('running') if active else None, 'recent': [], 'events': []}
        class Control:
            def auto_available(self): return True
        monitor = TaskMonitor(Cost(), Control())
        monitor.enabled = True
        async def pause(seconds):
            times.append(seconds)
            monitor.enabled = False
        monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', pause)
        await monitor._run(monitor.epoch)
        return times
    assert asyncio.run(exercise(False)) == [1]
    assert asyncio.run(exercise(True)) == [1]


def test_pc_cue_starts_while_watch_notification_is_in_flight(monkeypatch, tmp_path):
    from threading import Event
    import wave
    started = Event()
    cached = tmp_path / 'cue.wav'
    with wave.open(str(cached), 'wb') as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(16000)
        sound.writeframes(b'\0\0' * 160)
    monkeypatch.setattr(task_monitor_module, '_fixed_wav', lambda _: cached)
    monkeypatch.setattr(task_monitor_module, '_pc_speech', lambda _path, _guard: (started.set(), 'played_by_os')[1])
    class Robot:
        async def auto_notify(self, _expression, _message, _guard):
            assert await asyncio.to_thread(started.wait, 0.5)
            return 'accepted'
    class Control:
        robot = Robot()
        def auto_available(self): return True
    async def run():
        monitor = TaskMonitor(None, Control())
        monitor.enabled = True
        monitor.target, monitor.sound, monitor.sound_target = 'both', True, 'pc'
        event = _stage_event({'stage': 'conversion_start', 'status': 'running'})
        assert await monitor._notify(monitor.epoch, snapshot('running'), event)
        assert monitor.history[0]['delivery']['watch'] == 'accepted'
        assert monitor.history[0]['delivery']['sound'] == 'played_by_os'
    asyncio.run(run())


def test_waiting_start_cue_is_removed_after_result_arrives(monkeypatch):
    original_sleep = asyncio.sleep
    monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', lambda _: original_sleep(0.001))
    task_id = 'tsk_' + 'a' * 24
    start = {'event_id': '1' * 32, 'task_id': task_id, 'task_name': '任务',
             'stage': 'match_start', 'status': 'running', 'attempt': 'a',
             'occurred_at': '2026-09-29T01:00:00+08:00'}
    result = {**start, 'event_id': '2' * 32, 'stage': 'match_result',
              'status': 'completed', 'occurred_at': '2026-09-29T01:00:01+08:00'}
    class Cost:
        calls = 0
        async def monitor_feed(self):
            self.calls += 1
            return {'task': None, 'recent': [],
                    'events': [] if self.calls == 1 else [start] if self.calls == 2 else [result, start]}
    class Control:
        def __init__(self, cost): self.cost = cost
        def auto_available(self): return self.cost.calls >= 3
    async def run():
        cost = Cost()
        monitor = TaskMonitor(cost, Control(cost))
        await monitor.configure(enabled=True)
        for _ in range(50):
            if monitor.history: break
            await original_sleep(0.005)
        assert [item['kind'] for item in monitor.history] == ['match_result']
        assert monitor.history[0]['source_at'] == result['occurred_at']
        assert monitor.history[0]['detected_at']
        await monitor.stop()
    asyncio.run(run())


def test_stage_feed_baselines_old_events_and_delivers_new_once(monkeypatch):
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        await original_sleep(0.001)

    monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', fast_sleep)
    task_id = 'tsk_' + 'a' * 24
    old = {'event_id': '1' * 32, 'task_id': task_id, 'task_name': '任务',
           'stage': 'conversion_start', 'status': 'running'}
    new = {'event_id': '2' * 32, 'task_id': task_id, 'task_name': '任务',
           'stage': 'report_generated', 'status': 'completed'}

    class Cost:
        calls = 0

        async def monitor_feed(self):
            self.calls += 1
            return {'task': None, 'recent': [], 'events': [old] if self.calls == 1 else [new, old]}

    class Robot:
        def __init__(self):
            self.notified = asyncio.Event()
            self.messages = []

        async def auto_notify(self, expression, message, guard):
            self.messages.append((expression, message))
            self.notified.set()
            return 'accepted'

    class Control:
        robot = Robot()

        def auto_available(self):
            return True

    async def run():
        monitor = TaskMonitor(Cost(), Control())
        await monitor.configure(enabled=True, target='both')
        await asyncio.wait_for(monitor.control.robot.notified.wait(), 1)
        await original_sleep(0.02)
        assert [row['kind'] for row in monitor.history] == ['report_generated']
        assert monitor.control.robot.messages == [('happy', '报告已生成，请查看成果。')]
        await monitor.stop()

    asyncio.run(run())


def test_warning_milestone_does_not_duplicate_legacy_attention_notice(monkeypatch):
    original_sleep = asyncio.sleep
    monkeypatch.setattr(task_monitor_module.asyncio, 'sleep', lambda _: original_sleep(0.001))
    task_id = 'tsk_' + 'a' * 24
    warning = {'event_id': '3' * 32, 'task_id': task_id, 'task_name': '任务',
               'stage': 'warning_result', 'status': 'completed', 'warning_rows': 2}

    class Cost:
        calls = 0

        async def monitor_feed(self):
            self.calls += 1
            value = snapshot('completed', warning=0 if self.calls == 1 else 2)
            return {'task': None, 'recent': [value], 'events': [] if self.calls == 1 else [warning]}

    class Control:
        def auto_available(self):
            return True

    async def run():
        monitor = TaskMonitor(Cost(), Control())
        await monitor.configure(enabled=True)
        for _ in range(100):
            if monitor.history:
                break
            await original_sleep(0.005)
        assert [record['kind'] for record in monitor.history] == ['warning_result']
        await monitor.stop()

    asyncio.run(run())


def test_fixed_phrase_routes_to_watch_without_cloud_tts(monkeypatch, tmp_path):
    cached = tmp_path / 'fixed.wav'
    cached.write_bytes(b'fixed-wave')
    phrases = []
    monkeypatch.setattr(task_monitor_module, '_fixed_wav', lambda phrase: (phrases.append(phrase), cached)[1])

    class Robot:
        def __init__(self):
            self.calls = []

        async def auto_notify(self, expression, message, guard):
            self.calls.append(('text', expression, message))
            return 'accepted'

        async def auto_speech(self, wav, text, guard, expression=None):
            assert guard()
            self.calls.append(('speech', wav, text, expression))
            return 'device_playback_completed'

    class Control:
        robot = Robot()

        def auto_available(self):
            return True

    async def run():
        monitor = TaskMonitor(None, Control())
        monitor.enabled = True
        monitor.target, monitor.sound, monitor.sound_kind, monitor.sound_target = 'both', True, 'speech', 'watch'
        event = _stage_event({'stage': 'match_result', 'status': 'completed', 'review_rows': 2})
        assert await monitor._notify(monitor.epoch, snapshot('completed'), event)
        assert phrases == ['匹配完成，请复核结果']
        assert monitor.control.robot.calls == [
            ('text', 'curious', '匹配完成，2 项待复核。'),
            ('speech', b'fixed-wave', '匹配完成，2 项待复核。', 'curious')]
        assert monitor.history[0]['delivery']['sound'] == 'device_playback_completed'

    asyncio.run(run())
