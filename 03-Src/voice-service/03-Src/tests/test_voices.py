import asyncio
import json

import httpx
import numpy as np
import pytest

from voice_service.audio import encode_wav
from voice_service.cloud import CloudEngines, CloudError
from voice_service.config import Settings
from voice_service.voices import CLOUD_VOICES
from tests.test_api import client, identity
from fastapi.testclient import TestClient
from voice_service.app import create_app
from voice_service.broker import Broker
from tests.fake_worker import worker


def test_capability_and_invalid_voice(client):
    caps = client.get('/v1/capabilities').json()
    assert caps['cloud']['voices'] == CLOUD_VOICES
    assert caps['cloud']['request_voice'] and caps['cloud']['speeds'] == [1.0]
    headers, turn = identity(client)
    response = client.post('/v1/tts/synthesize', headers=headers,
        json={'request_id':'invalid-voice','turn_id':turn,'text':'test','cloud_voice':'not-supported'})
    assert response.status_code == 400 and response.json()['error']['code'] == 'VOICE_INVALID'


def test_synthesis_headers_report_selected_cloud_voice_over_successive_turns():
    class Cloud:
        def available(self):return True
        def status(self):return {'state':'configured'}
        async def run(self,kind,payload):
            return {'provider':'fixture','result':{'audio':encode_wav(np.zeros(2400),24000),
                'voice':payload['cloud_voice']},'metrics':{'provider_elapsed_ms':1}}
    config=Settings()
    with TestClient(create_app(config,Broker(config,worker,Cloud())),base_url='http://127.0.0.1:8765') as c:
        headers,turn=identity(c)
        assert c.patch('/v1/settings',headers=headers,json={'asr':'local','tts':'cloud','allow_audio_upload':False,'allow_text_upload':True}).status_code==200
        for i in range(3):
            session=headers['X-Voice-Session']
            turn=c.post(f'/v1/sessions/{session}/turns',headers=headers).json()['turn_id']
            result=c.post('/v1/tts/synthesize',headers=headers,json={'request_id':f'voice-{i}',
                'turn_id':turn,'text':'测试','cloud_voice':'Ethan'})
            assert result.status_code==200
            assert result.headers['X-Voice-Id']=='Ethan' and result.headers['X-Voice-Mode']=='cloud'


@pytest.mark.parametrize('voice', [item['id'] for item in CLOUD_VOICES])
def test_selected_voice_reaches_cloud_and_result(monkeypatch, voice):
    monkeypatch.setenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY','fixture-only')
    def upstream(request):
        if request.method == 'POST':
            assert json.loads(request.content)['input']['voice'] == voice
            return httpx.Response(200,json={'output':{'audio':{'url':'https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/test.wav'}}})
        assert 'authorization' not in request.headers
        return httpx.Response(200,content=encode_wav(np.zeros(2400),24000))
    async def run():
        engine = CloudEngines(Settings(),httpx.MockTransport(upstream))
        result = await engine.run('tts',{'text':'test','cloud_voice':voice,'speed':1.,'sample_rate':24000})
        assert result['result']['voice'] == voice
        with pytest.raises(CloudError):
            await engine.run('tts',{'text':'test','cloud_voice':'bad','speed':1.,'sample_rate':24000})
    asyncio.run(run())
