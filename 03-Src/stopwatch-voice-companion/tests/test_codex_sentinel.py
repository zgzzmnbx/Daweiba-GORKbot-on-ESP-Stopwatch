import asyncio
from datetime import datetime, timezone
import json
import io
import os
from pathlib import Path
import time
import uuid
import importlib.util
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from companion.app import CodexSettings, _codex_preferences, create_app
from companion.codex_monitor import CodexMonitor, quota_snapshot, quota_window
from companion.codex_source import JsonlSource, HookSpool, QuotaRPC, normalize_hook, normalize_jsonl
from companion.control import Controller
from companion.notification_coordinator import NotificationCoordinator
from companion.task_monitor import TaskMonitor, _stage_event
from test_companion import FakeRobot, FakeVoice
from test_task_monitor import snapshot


THREAD = '12345678-1234-1234-1234-123456789abc'


def line(kind, turn, stamp=None, **extra):
    return json.dumps({'timestamp': stamp or datetime.now(timezone.utc).isoformat(),
                       'type': 'event_msg', 'payload': {'type': kind, 'turn_id': turn, **extra}},
                      ensure_ascii=False) + '\n'


def test_jsonl_old_directory_initial_baseline_then_short_task(tmp_path):
    root = tmp_path / 'sessions'
    old = root / '2026' / '09' / '20'
    old.mkdir(parents=True)
    path = old / f'rollout-2026-09-20T10-00-00-{THREAD}.jsonl'
    path.write_text(line('task_started', 'old') + line('task_complete', 'old'), encoding='utf-8')
    source = JsonlSource(root)
    first = source.poll()
    assert [event['kind'] for event in first] == ['running', 'turn_completed']
    assert all(event['baseline'] for event in first)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(line('task_started', 'new') + line('task_complete', 'new', last_agent_message='secret answer'))
    fresh = source.poll()
    assert [event['kind'] for event in fresh] == ['running', 'turn_completed']
    assert all(not event['baseline'] for event in fresh)
    assert all(event['thread_id'] == THREAD for event in fresh)
    assert 'secret' not in str(fresh)


def test_new_jsonl_file_after_enable_and_partial_line(tmp_path):
    source = JsonlSource(tmp_path)
    assert source.poll() == []
    now = datetime.now(timezone.utc)
    folder = tmp_path / now.strftime('%Y') / now.strftime('%m') / now.strftime('%d')
    folder.mkdir(parents=True)
    path = folder / f'rollout-new-{THREAD}.jsonl'
    content = line('task_started', 'new') + line('task_complete', 'new')
    path.write_text(content[:-4], encoding='utf-8')
    source.last_discovery = 0
    assert [event['kind'] for event in source.poll()] == ['running']
    with path.open('a', encoding='utf-8') as handle: handle.write(content[-4:])
    assert [event['kind'] for event in source.poll()] == ['turn_completed']


def test_jsonl_truncate_replace_and_malformed_line_are_bounded(tmp_path):
    source = JsonlSource(tmp_path)
    assert source.poll() == []
    now = datetime.now(timezone.utc)
    folder = tmp_path / now.strftime('%Y') / now.strftime('%m') / now.strftime('%d')
    folder.mkdir(parents=True)
    path = folder / f'rollout-new-{THREAD}.jsonl'
    path.write_text('{bad json}\n' + line('task_started', 'first') + 'x' * 600, encoding='utf-8')
    source.last_discovery = 0
    assert [item['kind'] for item in source.poll()] == ['running']
    # Truncation is a fresh baseline, and a later complete line is incremental.
    path.write_text(line('task_started', 'replacement'), encoding='utf-8')
    observed = source.poll()
    assert len(observed) == 1 and observed[0]['baseline']
    with path.open('a', encoding='utf-8') as handle: handle.write(line('task_complete', 'replacement'))
    assert [item['kind'] for item in source.poll()] == ['turn_completed']
    moved = folder / f'rollout-moved-{THREAD}.jsonl'
    path.rename(moved)
    source.last_discovery = 0
    assert len(source.poll()) <= 2


def test_delayed_discovery_of_more_than_40_old_files_never_replays(tmp_path):
    async def run():
        root = tmp_path / 'sessions'
        folder = root / '2026' / '09' / '20'
        folder.mkdir(parents=True)
        historical = '2026-09-20T10:00:00+00:00'
        for index in range(45):
            path = folder / f'rollout-{index:02d}-{THREAD}.jsonl'
            path.write_text(line('task_started', f'old_{index}', historical)
                            + line('task_complete', f'old_{index}', historical), encoding='utf-8')
            os.utime(path, (time.time() - 1000 + index, time.time() - 1000 + index))
        source = JsonlSource(root)
        control = Controller(FakeVoice(), Robot())
        monitor = CodexMonitor(control, jsonl=source, hooks=Hooks(), rpc=RPC())
        control.codex_monitor = monitor
        await monitor.configure(DEFAULTS)
        for entry in source.poll(): await monitor.accept(entry)
        assert not monitor.history
        # A file outside the first 40 is later touched and enters discovery.
        late = folder / f'rollout-00-{THREAD}.jsonl'
        os.utime(late, None)
        source.last_full_discovery = source.last_discovery = 0
        late_events = source.poll()
        assert late_events and any(not entry['baseline'] for entry in late_events)
        for entry in late_events: await monitor.accept(entry)
        await asyncio.sleep(.02)
        assert monitor.history == []
        # A genuine new turn appended to that old-date file remains observable.
        with late.open('a', encoding='utf-8') as handle:
            handle.write(line('task_started', 'fresh') + line('task_complete', 'fresh'))
        for entry in source.poll(): await monitor.accept(entry)
        await asyncio.sleep(.04)
        assert [entry['kind'] for entry in monitor.history] == ['turn_completed']
        await monitor.stop()
    asyncio.run(run())


def test_recovery_cutoff_suppresses_delayed_historical_terminal():
    async def run():
        control = Controller(FakeVoice(), Robot())
        monitor = CodexMonitor(control, jsonl=Source(), hooks=Hooks(), rpc=RPC())
        control.codex_monitor = monitor
        await monitor.configure(DEFAULTS)
        old = event('turn_completed', 'old', at='2026-09-20T10:00:00+00:00')
        await monitor.accept(old)
        await asyncio.sleep(.02)
        assert monitor.history == []
        monitor.accept_after = time.time()  # same cutoff used after source recovery
        await monitor.accept(event('turn_completed', 'another', at='2026-09-20T11:00:00+00:00'))
        await asyncio.sleep(.02)
        assert monitor.history == []
        await monitor.stop()
    asyncio.run(run())


def test_sources_discard_sensitive_fields_and_unknown_schema():
    raw = {'hook_event_name': 'PermissionRequest', 'session_id': THREAD, 'turn_id': 'turn_1',
           'prompt': 'secret prompt', 'tool_input': {'token': 'secret token'}}
    event = normalize_hook(raw)
    assert event['kind'] == 'waiting_approval'
    assert 'secret' not in str(event)
    assert normalize_hook({**raw, 'hook_event_name': 'Mystery'}) is None
    assert normalize_hook({**raw, 'hook_event_name': 'Stop', 'stop_hook_active': True}) is None
    assert normalize_jsonl({'type': 'response_item', 'payload': {'type': 'message', 'content': 'secret'}}, THREAD) is None


def test_hook_spool_baseline_and_cleanup(tmp_path):
    spool = HookSpool(tmp_path)
    spool.heartbeat()
    old = tmp_path / 'old.json'
    old.write_text('{}', encoding='utf-8')
    spool.reset_baseline()
    assert not old.exists()
    record = {'hook_event_name': 'PermissionRequest', 'session_id': THREAD, 'turn_id': 'turn_1',
              'event_id': uuid.uuid4().hex, 'timestamp': datetime.now(timezone.utc).isoformat()}
    (tmp_path / 'new.json').write_text(json.dumps(record), encoding='utf-8')
    result = spool.poll()
    assert len(result) == 1 and not result[0]['baseline']
    assert not (tmp_path / 'new.json').exists()
    spool.disable()
    assert not (tmp_path / 'enabled.json').exists()


def test_hook_bridge_to_spool_is_silent_and_disabled_noop(tmp_path):
    bridge = Path(__file__).resolve().parents[3] / 'tools' / 'codex_sentinel_hook.py'
    environment = {**os.environ, 'GORK_CODEX_HOOK_QUEUE': str(tmp_path)}
    payload = json.dumps({'hook_event_name': 'PermissionRequest', 'session_id': THREAD,
                          'turn_id': 'turn_1', 'tool_input': {'token': 'secret'}})
    def invoke():
        return subprocess.run([sys.executable, str(bridge)], input=payload, text=True,
                              capture_output=True, env=environment, check=True)
    assert invoke().stdout == '' and list(tmp_path.glob('*.json')) == []
    spool = HookSpool(tmp_path); spool.heartbeat()
    assert invoke().stdout == ''
    events = spool.poll()
    assert len(events) == 1 and events[0]['kind'] == 'waiting_approval'
    assert 'secret' not in str(events)
    spool.disable()


def test_hook_bridge_rejects_oversize_input_without_output_or_event(tmp_path, monkeypatch, capsys):
    bridge = Path(__file__).resolve().parents[3] / 'tools' / 'codex_sentinel_hook.py'
    spec = importlib.util.spec_from_file_location('gork_hook_bridge', bridge)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    spool = HookSpool(tmp_path); spool.heartbeat()
    monkeypatch.setenv('GORK_CODEX_HOOK_QUEUE', str(tmp_path))
    class Input:
        buffer = io.BytesIO(json.dumps({'hook_event_name': 'Stop', 'session_id': THREAD,
                                        'turn_id': 'one', 'last_assistant_message': 'x' * 1048576}).encode())
    monkeypatch.setattr(module.sys, 'stdin', Input())
    module.main()
    assert capsys.readouterr().out == ''
    assert spool.poll() == []
    spool.disable()


def test_quota_buckets_windows_and_invalid_numbers():
    raw = {'rateLimitsByLimitId': {
        'codex': {'limitName': 'Codex', 'primary': {'usedPercent': 25, 'windowDurationMins': 300,
                                                  'resetsAt': time.time() + 3600},
                  'secondary': {'usedPercent': 100, 'windowDurationMins': 10080}},
        'other': {'primary': {'usedPercent': 0, 'windowDurationMins': 60}},
    }}
    parsed = quota_snapshot(raw)
    assert parsed['buckets']['codex']['windows'][0]['remaining_percent'] == 75
    assert parsed['buckets']['codex']['windows'][1]['remaining_percent'] == 0
    assert parsed['buckets']['other']['windows'][0]['remaining_percent'] == 100
    assert '7 天' in parsed['buckets']['codex']['windows'][1]['name']
    assert quota_window({'usedPercent': None}, 1)['remaining_percent'] is None
    assert quota_window({'usedPercent': float('nan')}, 1)['remaining_percent'] is None
    assert quota_window({'usedPercent': 140}, 1)['remaining_percent'] == 0
    assert quota_snapshot({'rateLimits': {'primary': {'usedPercent': 0}}})['buckets']['default']['windows'][0]['remaining_percent'] == 100


def test_quota_rpc_matches_ids_with_early_response_and_ignores_notifications(monkeypatch):
    class Input:
        def __init__(self): self.lines = []
        def write(self, data): self.lines.append(json.loads(data))
        async def drain(self): pass
    class Output:
        def __init__(self):
            self.lines = [
                {'jsonrpc': '2.0', 'method': 'account/updated', 'params': {'secret': 'ignore'}},
                {'jsonrpc': '2.0', 'id': 1, 'result': {}},
                {'jsonrpc': '2.0', 'id': 3, 'result': {'rateLimits': {'primary': {'usedPercent': 25}}}},
                {'jsonrpc': '2.0', 'id': 99, 'result': {'secret': 'ignore'}},
                {'jsonrpc': '2.0', 'id': 2, 'result': {'account': {'type': 'chatgpt'}}},
            ]
        async def readline(self):
            return (json.dumps(self.lines.pop(0)) + '\n').encode() if self.lines else b''
    class Process:
        def __init__(self): self.stdin = Input(); self.stdout = Output(); self.returncode = None
        def kill(self): self.returncode = 0
        async def wait(self): return self.returncode
    process = Process()
    async def create(*_args, **_kwargs): return process
    monkeypatch.setattr('companion.codex_source.shutil.which', lambda _: 'codex')
    monkeypatch.setattr('companion.codex_source.asyncio.create_subprocess_exec', create)
    result = asyncio.run(QuotaRPC().read())
    assert result['rateLimits']['primary']['usedPercent'] == 25
    assert [item.get('method') for item in process.stdin.lines] == [
        'initialize', 'initialized', 'account/read', 'account/rateLimits/read']
    assert process.returncode == 0


def test_low_quota_hysteresis_notifies_once_per_crossing():
    async def run():
        robot = Robot(); control = Controller(FakeVoice(), robot)
        monitor = CodexMonitor(control, jsonl=Source(), hooks=Hooks(), rpc=RPC())
        monitor.enabled = True; monitor.target = 'watch'; monitor.threshold = 20
        control.codex_monitor = monitor
        reset = time.time() + 3600
        async def sample(remaining):
            monitor.quota = quota_snapshot({'rateLimits': {'primary': {
                'usedPercent': 100 - remaining, 'windowDurationMins': 300, 'resetsAt': reset}}})
            monitor.quota_at = time.time()
            await monitor._check_low(monitor.epoch)
            await asyncio.sleep(.03)
        for value in (30, 19, 18, 24, 25, 19): await sample(value)
        assert [item['kind'] for item in monitor.history] == ['quota_low', 'quota_low']
        assert len(robot.calls) == 2
        await monitor.stop()
    asyncio.run(run())


def event(kind, turn, *, eid=None, at=None, baseline=False):
    return {'source': 'jsonl', 'source_instance': THREAD, 'thread_id': THREAD,
            'turn_id': turn, 'event_id': eid or uuid.uuid4().hex, 'kind': kind,
            'occurred_at': at or datetime.now(timezone.utc).isoformat(),
            'capabilities': ['running', 'turn_completed'], 'sanitized_label': THREAD[:8],
            'baseline': baseline}


class Robot:
    def __init__(self):
        self.calls = []
        self.in_flight = 0
        self.overlap = False
    def audio_snapshot(self): return {}
    def snapshot(self): return {'connected': False}
    async def auto_notify(self, face, text, guard):
        self.in_flight += 1
        if self.in_flight > 1: self.overlap = True
        await asyncio.sleep(.02)
        self.calls.append((face, text))
        self.in_flight -= 1
        return 'accepted'
    async def auto_expression(self, *_): return 'offline'


class Source:
    capability = 'available'
    def poll(self): return []
    def reset_baseline(self): pass


class Hooks(Source):
    def heartbeat(self): pass
    def disable(self): pass


class RPC:
    def __init__(self): self.calls = 0
    async def read(self):
        self.calls += 1
        return {'rateLimits': {'primary': {'usedPercent': 30, 'windowDurationMins': 300}}}
    async def close(self): pass


DEFAULTS = {'enabled': True, 'mode': 'auto', 'thread_id': '', 'target': 'desktop',
            'sound': False, 'sound_target': 'pc', 'threshold': 20, 'bucket_id': '', 'ring_mode': 'visible'}


def test_quota_ring_defaults_hidden_and_legacy_checkbox_does_not_enable_it(tmp_path):
    assert CodexSettings().ring_mode == 'hidden'
    assert CodexSettings(ring_mode='hover').ring_mode == 'hover'
    with pytest.raises(ValueError):
        CodexSettings(ring_mode='invalid')
    saved = tmp_path / 'codex.json'
    saved.write_text(json.dumps({'enabled': True, 'target': 'watch', 'show_ring': True}), encoding='utf-8')
    preferences = _codex_preferences(saved)
    assert preferences['enabled'] is False
    assert preferences['target'] == 'watch'
    assert preferences['ring_mode'] == 'hidden'
    assert 'show_ring' not in preferences
    monitor = CodexMonitor(Controller(FakeVoice(), Robot()), jsonl=Source(), hooks=Hooks(), rpc=RPC())
    monitor.enabled = True
    assert monitor.desktop_summary()['enabled'] is False
    monitor.ring_mode = 'hover'
    assert monitor.desktop_summary()['enabled'] is True
    assert monitor.desktop_summary()['ring_mode'] == 'hover'


def test_codex_short_turn_waiting_recovery_stale_and_stop():
    async def run():
        control = Controller(FakeVoice(), Robot())
        monitor = CodexMonitor(control, jsonl=Source(), hooks=Hooks(), rpc=RPC())
        control.codex_monitor = monitor
        await monitor.configure(DEFAULTS)
        await monitor.accept(event('running', 'one', baseline=True, at='2026-01-01T00:00:00+00:00'))
        assert monitor.threads[THREAD]['status'] == 'running'
        assert not monitor.history
        control.manual_until = time.monotonic() + 10
        await monitor.accept(event('waiting_approval', 'one'))
        await asyncio.sleep(.01)
        assert monitor.threads[THREAD]['status'] == 'waiting_approval'
        await monitor.accept(event('running', 'one'))
        assert monitor.threads[THREAD]['status'] == 'running'
        control.manual_until = 0
        await monitor.accept(event('turn_completed', 'one'))
        await asyncio.sleep(.04)
        assert monitor.threads[THREAD]['status'] == 'turn_completed'
        assert [x['kind'] for x in monitor.history] == ['turn_completed']
        presentation = control.notifications.current()
        assert presentation['bubble'] == '本轮已结束，请查看结果。'
        assert presentation['dismiss_on_click'] is True
        assert 299 < presentation['until'] - time.monotonic() <= 300
        assert control.desktop_state()['character']['dismissOnClick'] is True
        presentation['blocks_until'] = time.monotonic() - 1
        assert control.notifications.blocking_current() is None
        assert await control.notifications.dispatch(source='cost', priority=2,
            valid=lambda: True, action=lambda: asyncio.sleep(0))
        await monitor.stop()
        assert not monitor.enabled and not control.notifications.queue
    asyncio.run(run())


def test_codex_running_pose_is_sent_through_real_desktop_state():
    async def run():
        control = Controller(FakeVoice(), Robot())
        monitor = CodexMonitor(control, jsonl=Source(), hooks=Hooks(), rpc=RPC())
        control.codex_monitor = monitor
        await monitor.configure(DEFAULTS)
        await monitor.accept(event('running', 'one', baseline=True))
        assert control.desktop_state()['character']['expression'] == 'working'
        assert control.desktop_state()['character']['auto'] is True
        control.manual_until = time.monotonic() + 15
        assert not control.desktop_state()['character'].get('auto')
        await monitor.stop()
    asyncio.run(run())


def test_real_cost_and_codex_monitors_share_one_delivery_lane():
    async def run():
        robot = Robot()
        control = Controller(FakeVoice(), robot)
        cost = TaskMonitor(None, control)
        codex = CodexMonitor(control, jsonl=Source(), hooks=Hooks(), rpc=RPC())
        control.task_monitor = cost; control.codex_monitor = codex
        cost.enabled = True; cost.target = 'watch'
        await codex.configure({**DEFAULTS, 'target': 'watch'})
        await codex.accept(event('running', 'one', baseline=True))
        event_cost = _stage_event({'stage': 'match_result', 'status': 'completed', 'review_rows': 1})
        first = asyncio.create_task(cost._notify(cost.epoch, snapshot('completed'), event_cost))
        await asyncio.sleep(.003)
        await codex.accept(event('turn_completed', 'one'))
        await first
        await asyncio.sleep(.05)
        assert len(robot.calls) == 2 and not robot.overlap
        await codex.stop()
    asyncio.run(run())


def test_coordinator_cancel_queued_token_and_manual_priority():
    async def run():
        control = Controller(FakeVoice(), Robot())
        control.manual_until = time.monotonic() + 10
        lane = control.notifications
        task = asyncio.create_task(lane.dispatch(source='codex', priority=2, valid=lambda: True,
                                                  action=lambda: asyncio.sleep(0)))
        await asyncio.sleep(.01)
        assert lane.queue
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert not lane.queue
        control.manual_until = 0
        assert await lane.dispatch(source='cost', priority=2, valid=lambda: True,
                                   action=lambda: asyncio.sleep(0))
    asyncio.run(run())


def test_codex_api_is_off_each_start_and_owner_protects_changes(tmp_path):
    import httpx
    class Cost:
        async def monitor_feed(self):
            raise AssertionError('cost monitor must remain off in this isolated test')
        async def close(self): pass
    async def run():
        config = {'sentinel_state_path': tmp_path / 'cost.json',
                  'codex_state_path': tmp_path / 'codex.json',
                  'codex_jsonl_root': tmp_path / 'sessions',
                  'codex_hook_queue': tmp_path / 'hooks'}
        (tmp_path / 'cost.json').write_text('{"enabled":false}', encoding='utf-8')
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app(config, controller=control, cost_client=Cost())
        app.state.codex_monitor.rpc = RPC()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url='http://127.0.0.1:8766',
                    headers={'X-Companion-Client': str(uuid.uuid4())}) as client:
                assert not (await client.get('/api/codex/sentinel')).json()['enabled']
                settings = dict(DEFAULTS)
                assert (await client.put('/api/codex/sentinel', json=settings)).status_code == 401
                assert (await client.post('/api/workspace', json={})).status_code == 200
                assert (await client.put('/api/codex/sentinel', json=settings)).status_code == 200
                assert (await client.get('/api/codex/sentinel')).json()['enabled']
                assert (await client.put('/api/codex/sentinel', json={**settings, 'threshold': 100})).status_code == 422
                assert (await client.post('/api/codex/quota/refresh')).status_code == 200
                assert (await client.get('/api/desktop/state')).json()['codex']['enabled']
                assert (await client.get('/api/codex/sentinel', headers={'Origin': 'https://evil.example'})).status_code == 403
                assert (await client.post('/api/desktop/stop')).status_code == 200
                assert not (await client.get('/api/codex/sentinel')).json()['enabled']
        next_app = create_app(config, controller=Controller(FakeVoice(), FakeRobot()), cost_client=Cost())
        async with next_app.router.lifespan_context(next_app):
            assert not next_app.state.codex_monitor.enabled
    asyncio.run(run())


def test_codex_api_new_tab_busy_takeover_and_global_stop(tmp_path):
    import httpx
    class Cost:
        async def monitor_feed(self): raise AssertionError('isolated cost monitor must remain off')
        async def close(self): pass
    async def run():
        config = {'sentinel_state_path': tmp_path / 'cost.json',
                  'codex_state_path': tmp_path / 'codex.json',
                  'codex_jsonl_root': tmp_path / 'sessions',
                  'codex_hook_queue': tmp_path / 'hooks'}
        (tmp_path / 'cost.json').write_text('{"enabled":false}', encoding='utf-8')
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app(config, controller=control, cost_client=Cost())
        app.state.codex_monitor.rpc = RPC()
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:8766') as owner, \
                    httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:8766') as new_tab:
                owner.headers['X-Companion-Client'] = str(uuid.uuid4())
                new_tab.headers['X-Companion-Client'] = str(uuid.uuid4())
                assert (await owner.post('/api/workspace', json={})).status_code == 200
                assert (await owner.put('/api/codex/sentinel', json=DEFAULTS)).status_code == 200
                assert (await new_tab.get('/api/codex/sentinel')).json()['enabled']
                assert (await new_tab.post('/api/workspace', json={})).status_code == 409
                assert (await new_tab.put('/api/codex/sentinel', json={**DEFAULTS, 'enabled': False})).status_code == 401
                assert (await new_tab.post('/api/workspace', json={'replace': True})).status_code == 200
                assert (await new_tab.put('/api/codex/sentinel', json={**DEFAULTS, 'enabled': False})).status_code == 200
                assert not (await owner.get('/api/codex/sentinel')).json()['enabled']
                assert (await new_tab.put('/api/codex/sentinel', json=DEFAULTS)).status_code == 200
                control.workspace_deadline = time.monotonic() - 1
                assert (await owner.post('/api/workspace', json={})).status_code == 200
                assert (await owner.put('/api/codex/sentinel', json={**DEFAULTS, 'enabled': False})).status_code == 200
                assert (await owner.put('/api/codex/sentinel', json=DEFAULTS)).status_code == 200
                # Emergency stop is intentionally available without a workspace lease.
                assert (await new_tab.post('/api/desktop/stop')).status_code == 200
                assert not (await new_tab.get('/api/codex/sentinel')).json()['enabled']
    asyncio.run(run())


def test_hook_configuration_merges_exact_entry_and_dry_run(tmp_path, capsys):
    tool = Path(__file__).resolve().parents[3] / 'tools' / 'codex_sentinel_hooks_config.py'
    spec = importlib.util.spec_from_file_location('gork_hook_config', tool)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    existing = {'hooks': {'Stop': [{'description': 'other', 'hooks': [{'command': 'other'}]}]},
                'custom': {'keep': True}}
    command = 'python bridge.py --gork-codex-sentinel-v0.18.0'
    installed = module.merge(existing, command)
    assert module.merge(installed, command) == installed
    assert module.merge(installed, command, remove=True) == existing
    assert existing['hooks']['Stop'][0]['description'] == 'other'
    target = tmp_path / 'hooks.json'
    target.write_text(json.dumps(existing), encoding='utf-8')
    module.main([str(target)])
    assert 'dry-run' in capsys.readouterr().out and json.loads(target.read_text(encoding='utf-8')) == existing
