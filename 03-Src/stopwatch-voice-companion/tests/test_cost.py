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


@pytest.mark.parametrize('url', ['https://127.0.0.1:8000', 'http://example.com',
                                'http://user:pass@localhost', 'http://localhost/api',
                                'http://localhost?secret=x'])
def test_only_loopback_configuration(url):
    with pytest.raises(ValueError):
        CostClient(url)


def test_contract_default_search_and_explicit_ai_preserve_demo_and_sources():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            if request.url.path == '/api/health':
                return httpx.Response(200, json={'service':'guankanzhisuan', 'status':'ok'})
            source = {'id':'s1','source_file':'规则.md','snippet':'原文 100 元', 'secret':'hidden'}
            return httpx.Response(200, json={'results':[source], 'sources':[source],
                'answer':'完整回答', 'evidence_found':True, 'answer_mode':'curated_demo',
                'preset_answer':True, 'generated_by_model':False, 'debug':{'api_key':'secret'}})
        cost = CostClient(transport=httpx.MockTransport(handler))
        result = await cost.query('依据？')
        assert calls[-1].url.path == '/api/knowledge/search'
        assert json.loads(calls[-1].content)['retrieval_mode'] == 'classic'
        assert result['answer_mode'] == 'local_search'
        assert 'secret' not in json.dumps(result)
        result = await cost.query('依据？', True)
        assert calls[-1].url.path == '/api/knowledge/ask'
        assert result['preset_answer'] and not result['generated_by_model']
        assert result['sources'][0]['snippet'] == '原文 100 元'
        await cost.close()
    asyncio.run(run())


def test_identity_failure_does_not_send_business_request():
    async def run():
        paths = []
        def handler(request):
            paths.append(request.url.path)
            return httpx.Response(200, json={'status':'ok','service':'other'})
        cost = CostClient(transport=httpx.MockTransport(handler))
        with pytest.raises(VoiceError, match='不是'):
            await cost.query('hello')
        assert paths == ['/api/health']
        await cost.close()
    asyncio.run(run())


def test_facade_requires_owner_not_voice_and_rejects_stale_and_unknown_fields():
    async def run():
        cost = CostClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'status':'ok','service':'guankanzhisuan'} if request.url.path == '/api/health'
            else {'results':[], 'evidence_found':False})))
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app(controller=control, cost_client=cost)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8766',
                headers={'X-Companion-Client':str(uuid.uuid4())}) as client:
            payload = {'generation':1, 'question':'what'}
            assert (await client.post('/api/cost/query', json=payload)).status_code == 401
            assert (await client.post('/api/workspace', json={})).status_code == 200
            response = await client.post('/api/cost/query', json=payload)
            assert response.status_code == 200 and not response.json()['evidence_found']
            assert control.voice.session is None
            assert (await client.post('/api/cost/query', json=payload)).status_code == 409
            assert (await client.post('/api/cost/query', json={**payload,'url':'http://evil'})).status_code == 422
            assert (await client.delete('/api/cost/projects/a')).status_code == 405
        await control.close(); await cost.close()
    asyncio.run(run())


def test_stop_cancels_pending_query_without_voice():
    async def run():
        started = asyncio.Event()
        class SlowCost:
            async def query(self, *_):
                started.set()
                await asyncio.Event().wait()
            async def close(self): pass
        control = Controller(FakeVoice(), FakeRobot())
        app = create_app(controller=control, cost_client=SlowCost())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8766',
                headers={'X-Companion-Client':str(uuid.uuid4())}) as client:
            await client.post('/api/workspace', json={})
            task = asyncio.create_task(client.post('/api/cost/query', json={'generation':1,'question':'hello'}))
            await started.wait()
            assert (await client.post('/api/desktop/stop')).status_code == 200
            result = await task
            assert result.status_code == 409
            assert not control.answer_tasks
        await control.close()
    asyncio.run(run())


def test_project_read_contract_and_redaction():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            path = request.url.path
            if path == '/api/health':
                data = {'service':'guankanzhisuan','status':'ok'}
            elif path.endswith('/tasks'):
                data = {'items':[{'task_id':'t1','task_name':'试验任务','status_label':'待审核','instructions':'secret'}]}
            elif path == '/api/projects':
                data = {'items':[{'project_id':'prj_123','project_name':'测试项目','secret':'omit'}], 'total':21}
            else:
                data = {'project_id':'prj_123','project_name':'测试项目','status_label':'处理中','latest_run':{'private':'omit'}}
            return httpx.Response(200,json=data)
        cost = CostClient(transport=httpx.MockTransport(handler))
        result = await cost.projects(2)
        assert result['page'] == 2 and result['total'] == 21
        assert calls[-1].url.params['page'] == '2'
        result = await cost.project('prj_123')
        assert result['tasks'][0]['status_label'] == '待审核'
        assert 'instructions' not in result['tasks'][0] and 'latest_run' not in result['project']
        assert all(request.method == 'GET' for request in calls)
        with pytest.raises(VoiceError):
            await cost.project('../secrets')
        await cost.close()
    asyncio.run(run())


def test_bad_schema_is_not_empty_success_and_errors_do_not_leak_upstream_body():
    async def run():
        for status, body in [(200, {'results':None}), (500, {'api_key':'DO_NOT_EXPOSE'})]:
            def handler(request):
                if request.url.path == '/api/health':
                    return httpx.Response(200,json={'service':'guankanzhisuan','status':'ok'})
                return httpx.Response(status,json=body)
            cost = CostClient(transport=httpx.MockTransport(handler))
            with pytest.raises(VoiceError) as error:
                await cost.query('test')
            assert 'DO_NOT_EXPOSE' not in str(error.value)
            await cost.close()
    asyncio.run(run())
