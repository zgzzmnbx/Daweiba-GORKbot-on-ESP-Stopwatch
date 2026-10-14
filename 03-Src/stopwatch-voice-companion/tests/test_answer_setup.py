import asyncio
import json
import uuid
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from companion.answer import AnswerClient, DEFAULT_PROMPT, system_message
from companion.answer_store import AnswerStore, BASE_URL
from companion.app import create_app
from companion.control import Controller
from test_companion import FakeRobot, FakeVoice
from companion.network_store import protect
import base64

DUMMY_KEY='fixture-private-deepseek-key'

def test_old_store_migrates_prompt_without_replacing_key_and_invalid_edit_is_atomic(tmp_path):
    path=tmp_path/'answer.local.json'
    path.write_bytes(base64.b64encode(protect(json.dumps(dict(key=DUMMY_KEY,model='deepseek-flash')).encode())))
    baseline=path.read_bytes();store=AnswerStore(path)
    assert store.key==DUMMY_KEY and store.system_prompt==DEFAULT_PROMPT and store.max_chars==20
    assert path.read_bytes()==baseline
    store.save('','deepseek-flash','只用一句中文直接回答。',12)
    restored=AnswerStore(path)
    assert restored.key==DUMMY_KEY and restored.system_prompt=='只用一句中文直接回答。' and restored.max_chars==12
    saved=path.read_bytes()
    for prompt,limit in [('',20),('x'*2001,20),('valid',4),('valid',301),('valid',True)]:
        with pytest.raises(ValueError):store.save('','deepseek-flash',prompt,limit)
        assert path.read_bytes()==saved and store.max_chars==12
    assert DUMMY_KEY not in json.dumps(restored.snapshot())

def test_saved_preview_is_exact_system_message_for_both_routes_and_budget_is_bounded(tmp_path):
    store=AnswerStore(tmp_path/'answer.local.json');store.save(DUMMY_KEY,'deepseek-flash','精简直接回答。',20)
    async def run():
        calls=[]
        async def server(request):
            payload=json.loads(request.content);calls.append(payload)
            return httpx.Response(200,json={'choices':[{'message':{'content':'我在。'},'finish_reason':'stop'}]})
        a=AnswerClient(BASE_URL,store.model,api_key=store.key,system_prompt=store.system_prompt,max_chars=store.max_chars,transport=httpx.MockTransport(server))
        try:
            await a.complete('你好',[]);await a.complete('你好',[],short=True)
            public=store.snapshot()
            assert calls[0]['messages'][0]['content']==public['effective_prompt']
            assert calls[1]['messages'][0]['content']==public['watch_prompt']
            assert '20个字' in public['watch_prompt'] and '35个汉字' not in public['watch_prompt']
            assert all(call['thinking']=={'type':'disabled'} and call['max_tokens']==64 for call in calls)
        finally:await a.close()
    asyncio.run(run())

def test_token_limit_does_not_read_an_incomplete_answer():
    from companion.voice import VoiceError
    async def run():
        async def server(request):return httpx.Response(200,json={'choices':[{'message':{'content':'残缺内容'},'finish_reason':'length'}]})
        a=AnswerClient(BASE_URL,'deepseek-flash',api_key=DUMMY_KEY,transport=httpx.MockTransport(server))
        try:
            with pytest.raises(VoiceError) as failure:await a.complete('你好',[])
            assert failure.value.code=='ANSWER_TOO_LONG'
        finally:await a.close()
    asyncio.run(run())

def test_dpapi_roundtrip_update_and_corrupt_preserve(tmp_path):
    path=tmp_path/'answer.local.json';store=AnswerStore(path)
    store.save(DUMMY_KEY,'deepseek-flash')
    assert DUMMY_KEY not in path.read_text()
    restored=AnswerStore(path)
    assert restored.key==DUMMY_KEY and restored.model=='deepseek-flash'
    restored.save('','deepseek-v4-pro')
    assert AnswerStore(path).key==DUMMY_KEY
    assert AnswerStore(path).model=='deepseek-v4-pro'
    with pytest.raises(ValueError):restored.save('bad\nkey','deepseek-flash')
    path.write_text('corrupted');failed=AnswerStore(path)
    assert not failed.key and failed.error and path.read_text()=='corrupted'
    assert DUMMY_KEY not in json.dumps(restored.snapshot())

def test_official_deepseek_adapter_uses_explicit_key_and_disables_thinking():
    async def run():
        async def server(request):
            assert str(request.url)=='https://api.deepseek.com/chat/completions'
            assert request.headers['Authorization']=='Bearer '+DUMMY_KEY
            payload=json.loads(request.content)
            assert payload['model']=='deepseek-flash' and payload['thinking']=={'type':'disabled'}
            assert payload['tools']==[] and not payload['stream']
            return httpx.Response(200,json={'choices':[{'message':{'content':'你好，我在。'}}]})
        client=AnswerClient(BASE_URL,'deepseek-flash',api_key=DUMMY_KEY,transport=httpx.MockTransport(server))
        try:
            assert client.capability()['enabled']
            assert await client.complete('你好',[],short=True)=='你好，我在。'
            assert DUMMY_KEY not in json.dumps(client.capability())
        finally:await client.close()
    asyncio.run(run())

def test_config_endpoint_requires_owner_and_never_echoes_key(tmp_path,monkeypatch):
    control=Controller(FakeVoice(),FakeRobot());who=str(uuid.uuid4());control.owner=who
    config={'auto_connect_device':False,'auto_connect_voice':False,'answer_state_path':tmp_path/'answer.local.json'}
    app=create_app(config,controller=control)
    with TestClient(app,base_url='http://127.0.0.1:8766') as web:
        headers={'X-Companion-Client':who}
        body=dict(api_key=DUMMY_KEY,model='deepseek-flash')
        denied=web.post('/api/answer/config',headers={'X-Companion-Client':str(uuid.uuid4())},json=body)
        assert denied.status_code==401 and not Path(config['answer_state_path']).exists()
        saved=web.post('/api/answer/config',headers=headers,json={**body,'system_prompt':'用一句中文简短回答。','max_chars':20})
        assert saved.status_code==200 and saved.json()['capability']['enabled']
        assert DUMMY_KEY not in saved.text
        assert control.answer.base_url==BASE_URL
        assert control.answer.system_prompt=='用一句中文简短回答。' and control.answer.max_chars==20
        assert saved.json()['watch_prompt']==system_message('用一句中文简短回答。',20,short=True)
        public=web.get('/api/answer/config').text
        assert DUMMY_KEY not in public and 'protected' not in public
        invalid=web.post('/api/answer/config',headers=headers,json={**body,'model':'private-invalid-model'})
        assert invalid.status_code==422 and DUMMY_KEY not in invalid.text
        control.answer_tasks.add('fixture-running')
        busy=web.post('/api/answer/config',headers=headers,json=body)
        assert busy.status_code==409
        control.answer_tasks.clear()
    # New formal-style app reads only this encrypted test fixture on startup.
    monkeypatch.setattr('companion.app.Robot.start',lambda self:None)
    restarted=create_app(config)
    with TestClient(restarted,base_url='http://127.0.0.1:8766') as web:
        assert web.get('/api/answer/config').json()['key_saved']
        assert web.get('/api/answer/config').json()['system_prompt']=='用一句中文简短回答。'
        assert DUMMY_KEY not in web.get('/api/answer/config').text
