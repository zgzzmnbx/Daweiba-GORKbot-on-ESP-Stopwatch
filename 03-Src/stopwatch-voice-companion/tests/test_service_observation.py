"""Passive metadata only; all requests are isolated MockTransport calls."""
import asyncio
import json
import httpx
import pytest
from companion.answer import AnswerClient
from companion.voice import VoiceClient, VoiceError
from test_companion import wav_bytes


def test_answer_observation_changes_only_on_actual_calls_and_contains_no_payload():
    async def run():
        calls=[]
        def respond(request):
            calls.append(request)
            if len(calls)==2:return httpx.Response(401,json={'secret':'do not expose'})
            return httpx.Response(200,json={'choices':[{'message':{'content':'reply private'},'finish_reason':'stop'}]})
        client=AnswerClient('http://localhost','model',transport=httpx.MockTransport(respond))
        assert client.capability()['observation'] is None
        assert not calls
        await client.complete('private input',[])
        seen=client.capability()['observation'];assert seen['state']=='success' and seen['at']>0
        with pytest.raises(VoiceError):await client.complete('private input',[])
        assert client.capability()['observation']['state']=='error'
        assert set(client.observation)=={'state','at'}
        assert 'private' not in json.dumps(client.observation)
        await client.close()
    asyncio.run(run())


def test_tts_observation_tracks_real_route_success_failure_and_invalid_audio():
    async def run():
        calls=[]
        def respond(request):
            calls.append(request.url.path)
            if request.url.path=='/v1/settings':return httpx.Response(200,json={'routing':{'tts':'cloud'}})
            if len(calls)==3:return httpx.Response(503,json={'error':{'code':'CLOUD_HTTP','message':'private upstream'}})
            if len(calls)==4:return httpx.Response(200,content=b'bad',headers={'content-type':'audio/wav'})
            return httpx.Response(200,content=wav_bytes(24000),headers={'content-type':'audio/wav','X-Voice-Mode':'cloud'})
        client=VoiceClient('http://localhost',transport=httpx.MockTransport(respond))
        assert client.tts_observation is None
        await client.routing({'tts':'cloud'})
        await client.synthesize('private',1,'test')
        assert client.tts_observation['state']=='success' and client.tts_observation['route']=='cloud'
        for _ in range(2):
            with pytest.raises(VoiceError):await client.synthesize('private',1,'test')
            assert client.tts_observation['state']=='error'
        assert set(client.tts_observation)=={'state','at','route'}
        await client.close()
    asyncio.run(run())
