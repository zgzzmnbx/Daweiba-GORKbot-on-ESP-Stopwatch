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


def test_capability_and_invalid_voice(client):
    caps = client.get('/v1/capabilities').json()
    assert caps['cloud']['voices'] == CLOUD_VOICES
    assert caps['cloud']['request_voice'] and caps['cloud']['speeds'] == [1.0]
    headers, turn = identity(client)
    response = client.post('/v1/tts/synthesize', headers=headers,
        json={'request_id':'invalid-voice','turn_id':turn,'text':'test','cloud_voice':'not-supported'})
    assert response.status_code == 400 and response.json()['error']['code'] == 'VOICE_INVALID'


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
