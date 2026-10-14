"""Source isolation, persisted opt-in and cancellation at the console API boundary."""
import asyncio
import json
import uuid

import httpx
import pytest

from companion.app import create_app
from companion.control import Controller
from companion.cost import CostClient
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice


@pytest.mark.parametrize('expected,actual,accepted', [
    ('guankanzhisuan', 'guankanzhisuan', True),
    ('guankanzhisuan', 'zhisuan-astra', False),
    ('zhisuan-astra', 'zhisuan-astra', True),
    ('zhisuan-astra', 'guankanzhisuan', False),
])
def test_source_identity_is_exact(expected, actual, accepted):
    async def run():
        calls = []
        def respond(request):
            calls.append(request)
            data = {'status': 'ok', 'service': actual} if request.url.path == '/api/health' else {'task': None, 'recent': [], 'events': []}
            return httpx.Response(200, json=data)
        client = CostClient(expected_service=expected, transport=httpx.MockTransport(respond))
        try:
            if accepted:
                assert (await client.monitor_feed())['task'] is None
            else:
                with pytest.raises(VoiceError):
                    await client.monitor_feed()
                assert [r.url.path for r in calls] == ['/api/health']
            assert all(r.method == 'GET' for r in calls)
        finally:
            await client.close()
    asyncio.run(run())


class Source:
    def __init__(self, name):
        self.name, self.reads, self.events = name, 0, []
        self.fail = False
    async def health(self):
        if self.fail:
            raise VoiceError(502, 'COST_IDENTITY', '来源不匹配')
        return {'status': 'ok'}
    async def monitor_feed(self):
        self.reads += 1
        return {'task': None, 'recent': [], 'events': list(self.events)}
    async def monitor_task(self, task_id):
        raise VoiceError(404, 'COST_NOT_FOUND', '当前来源没有该任务')
    async def projects(self, page):
        return {'items': [{'project_id': self.name}], 'page': page}
    async def project(self, project_id):
        return {'project': {'project_id': self.name}, 'tasks': []}
    async def close(self): pass


def test_source_switch_baselines_old_events_delivers_new_once_and_persists(tmp_path):
    async def run():
        path = tmp_path / 'sentinel.json'
        path.write_text(json.dumps({'enabled': False}), encoding='utf-8')
        legacy, astra = Source('legacy'), Source('astra')
        task_id = 'tsk_' + 'a' * 24
        old = {'event_id': '1' * 32, 'task_id': task_id, 'stage': 'report_generated', 'status': 'completed', 'task_name': 'Astra 任务'}
        astra.events = [old]
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app({'sentinel_state_path': path}, controller=control, cost_client=legacy, astra_client=astra)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8766', headers={'X-Companion-Client': str(uuid.uuid4())}) as client:
                config = {'source': 'astra', 'enabled': True, 'target': 'desktop', 'sound': False}
                assert (await client.put('/api/cost/sentinel', json=config)).status_code == 401
                await client.post('/api/workspace', json={})
                assert (await client.get('/api/cost/sentinel/projects?source=astra')).json()['items'][0]['project_id'] == 'astra'
                assert (await client.get('/api/cost/sentinel/projects?source=legacy')).json()['items'][0]['project_id'] == 'legacy'
                response = await client.put('/api/cost/sentinel', json=config)
                assert response.status_code == 200, response.text
                await asyncio.sleep(0.02)
                monitor = app.state.task_monitor
                assert monitor.seen_event_ids == {old['event_id']}
                assert not monitor.history and legacy.reads == 0
                astra.events.insert(0, {**old, 'event_id': '2' * 32})
                for _ in range(150):
                    if monitor.history: break
                    await asyncio.sleep(0.01)
                assert [e['kind'] for e in monitor.history] == ['report_generated']
                await asyncio.sleep(1.1)
                assert len(monitor.history) == 1
                # A task from the other source must not replace this active configuration.
                saved = path.read_bytes()
                response = await client.put('/api/cost/sentinel', json={**config, 'mode': 'specific', 'task_id': task_id})
                assert response.status_code == 404
                assert path.read_bytes() == saved and monitor.enabled
                legacy.fail = True
                response = await client.put('/api/cost/sentinel', json={**config, 'source': 'legacy'})
                assert response.status_code == 502
                assert path.read_bytes() == saved and monitor.cost is astra
                # Changing the task context must not display another task's last result.
                async def known_task(_): return None
                astra.monitor_task = known_task
                monitor.last_result = {'task_id': 'previous-task'}
                response = await client.put('/api/cost/sentinel', json={**config, 'mode': 'specific', 'task_id': task_id})
                assert response.status_code == 200
                assert response.json()['last_result'] is None and not response.json()['history']
                # A deliberate disabled switch can be saved without contacting an offline source.
                assert (await client.put('/api/cost/sentinel', json={**config, 'source': 'legacy', 'enabled': False})).status_code == 200
                assert not monitor.history and not monitor.last_success_at
                assert not monitor.seen_event_ids and monitor.worker is None
                # Preserve a paused Astra selection on restart.
                await client.put('/api/cost/sentinel', json={**config, 'enabled': False})
        restored = Source('astra')
        next_app = create_app({'sentinel_state_path': path}, controller=Controller(FakeVoice(), FakeRobot()), cost_client=Source('legacy'), astra_client=restored)
        async with next_app.router.lifespan_context(next_app):
            monitor = next_app.state.task_monitor
            assert monitor.cost is restored and not monitor.enabled
            await asyncio.sleep(0)
            assert restored.reads == 0
    asyncio.run(run())


def test_source_change_cancels_inflight_old_read(tmp_path):
    async def run():
        started, cancelled = asyncio.Event(), asyncio.Event()
        class Slow(Source):
            async def monitor_feed(self):
                started.set()
                try: await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
        app = create_app({'sentinel_state_path': tmp_path / 'prefs.json'}, controller=Controller(FakeVoice(), FakeRobot()), cost_client=Slow('legacy'), astra_client=Source('astra'))
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(started.wait(), 1)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8766', headers={'X-Companion-Client': str(uuid.uuid4())}) as client:
                await client.post('/api/workspace', json={})
                reply = await client.put('/api/cost/sentinel', json={'source': 'astra', 'enabled': True})
                assert reply.status_code == 200 and cancelled.is_set()
                assert reply.json()['source'] == 'astra'
                assert not reply.json()['history']
    asyncio.run(run())
