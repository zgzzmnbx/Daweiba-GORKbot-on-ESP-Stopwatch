import asyncio
import json
import os
import struct
from dataclasses import replace

import httpx
import numpy as np
import pytest

from voice_service.audio import encode_wav, decode_wav
from voice_service.cloud import CloudEngines, CloudError, audio_url
from voice_service.config import Settings


def test_cloud_streaming_length_marker_and_resampling():
    from voice_service.cloud import decode_output
    raw=bytearray(encode_wav(np.sin(np.arange(24000)*.1)*.2,24000))
    struct.pack_into('<I',raw,4,2147483583)
    struct.pack_into('<I',raw,40,2147483547)
    output,rate,duration=decode_output(bytes(raw),16000)
    samples,decoded_duration=decode_wav(output)
    assert rate==24000 and duration==decoded_duration==1
    assert len(samples)==16000 and np.max(np.abs(samples))>.1


@pytest.mark.parametrize('case',['truncated','odd_marker','empty_marker','stereo_marker','long_marker'])
def test_cloud_length_repair_does_not_accept_invalid_audio(case):
    from voice_service.cloud import decode_output
    raw=bytearray(encode_wav(np.zeros(24000),24000))
    if case=='truncated': raw=raw[:-2]
    else:
        struct.pack_into('<I',raw,40,2147483547)
        if case=='odd_marker': raw=raw[:-1]
        if case=='empty_marker': raw=raw[:44]
        if case=='stereo_marker': struct.pack_into('<H',raw,22,2)
        if case=='long_marker': raw.extend(b'\0'*(24000*2*180))
    with pytest.raises(CloudError) as err: decode_output(bytes(raw),16000)
    assert err.value.code=='CLOUD_AUDIO_INVALID'


def test_qwen_payloads_audio_download_and_redaction(monkeypatch):
    monkeypatch.setenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY','fixture-secret-not-real')
    calls=[]
    async def handle(request):
        calls.append(request)
        if request.method=='GET':
            assert 'authorization' not in request.headers and request.url.scheme=='https'
            return httpx.Response(200,content=encode_wav(np.sin(np.arange(24000)*.1)*.2,24000))
        body=json.loads(request.content)
        assert request.headers['Authorization']=='Bearer fixture-secret-not-real'
        if body['model']=='qwen3-asr-flash':
            assert body['messages'][0]['content'][0]['input_audio']['data'].startswith('data:audio/wav;base64,')
            assert body['asr_options']['enable_itn'] and not body['stream']
            return httpx.Response(200,json={'choices':[{'message':{'content':'测试转写'}}],'usage':{'prompt_tokens':12,'secret':'omit'}})
        assert body=={'model':'qwen3-tts-flash','input':{'text':'测试文本','voice':'Cherry','language_type':'Chinese'}}
        return httpx.Response(200,json={'output':{'audio':{'url':'http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/test.wav?Signature=private'}},'usage':{'characters':4}})
    engine=CloudEngines(Settings(),httpx.MockTransport(handle))
    async def scenario():
        asr=await engine.run('asr',{'audio':encode_wav(np.zeros(16000),16000)})
        assert asr['result']['text']=='测试转写' and asr['result']['usage']=={'prompt_tokens':12}
        tts=await engine.run('tts',{'text':'测试文本','speaker_id':3,'speed':1.,'sample_rate':16000})
        _,duration=decode_wav(tts['result']['audio'])
        assert duration==1 and tts['result']['native_sample_rate']==24000
        assert 'cloud_api_ms' in tts['metrics'] and 'inference_ms' not in tts['metrics']
        assert 'private' not in str(tts) and 'fixture-secret' not in str(tts)
    asyncio.run(scenario())
    assert len(calls)==3


@pytest.mark.parametrize('status,code',[(401,'CLOUD_AUTH'),(403,'CLOUD_AUTH'),(429,'CLOUD_RATE_LIMIT'),(500,'CLOUD_HTTP'),(302,'CLOUD_HTTP')])
def test_http_failure_no_retry_or_secret_echo(monkeypatch,status,code):
    monkeypatch.setenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY','fixture-secret')
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(status,text='private input and API key must not escape')
    engine=CloudEngines(Settings(),httpx.MockTransport(handle))
    with pytest.raises(CloudError) as err:
        asyncio.run(engine.run('asr',{'audio':encode_wav(np.zeros(16000),16000)}))
    assert err.value.code==code and 'private' not in str(err.value) and len(calls)==1


@pytest.mark.parametrize('url',['https://127.0.0.1/x','https://example.com/x','https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com.evil/x','https://user@dashscope-result-bj.oss-cn-beijing.aliyuncs.com/x','http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com:80/x'])
def test_unsafe_audio_url_is_rejected(url):
    with pytest.raises(CloudError): audio_url(url)


def test_missing_key_timeout_bad_json_and_bad_audio(monkeypatch):
    monkeypatch.delenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY',raising=False)
    def never(request): raise AssertionError('Unexpected network request')
    with pytest.raises(CloudError) as err:
        asyncio.run(CloudEngines(Settings(),httpx.MockTransport(never)).run('tts',{}))
    assert err.value.code=='CLOUD_NOT_CONFIGURED'
    monkeypatch.setenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY','fixture-secret')
    async def slow(request):
        await asyncio.sleep(.1)
        return httpx.Response(200,json={})
    with pytest.raises(CloudError) as err:
        asyncio.run(CloudEngines(replace(Settings(),cloud_timeout=.02),httpx.MockTransport(slow)).run('asr',{'audio':encode_wav(np.zeros(16000),16000)}))
    assert err.value.code=='CLOUD_TIMEOUT'
    for response in (httpx.Response(200,text='not-json'),httpx.Response(200,json={'choices':[]})):
        with pytest.raises(CloudError) as err:
            asyncio.run(CloudEngines(Settings(),httpx.MockTransport(lambda _:response)).run('asr',{'audio':encode_wav(np.zeros(16000),16000)}))
        assert err.value.code=='CLOUD_RESPONSE'


@pytest.mark.parametrize('case',['oversize','invalid_wav','redirect','error_body'])
def test_bounded_response_invalid_audio_and_no_redirect(monkeypatch,case):
    monkeypatch.setenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY','fixture-secret')
    calls=[]
    def handle(request):
        calls.append(request)
        if request.method=='POST':
            if case=='oversize': return httpx.Response(200,content=b'x'*(1024*1024+1))
            if case=='error_body': return httpx.Response(200,json={'code':'InvalidApiKey','message':'never echo private'})
            return httpx.Response(200,json={'output':{'audio':{'url':'https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/a.wav'}}})
        if case=='redirect': return httpx.Response(302,headers={'Location':'http://127.0.0.1/private'})
        return httpx.Response(200,content=b'not-wav')
    with pytest.raises(CloudError) as err:
        asyncio.run(CloudEngines(Settings(),httpx.MockTransport(handle)).run('tts',{'text':'fixture','speed':1.,'sample_rate':24000}))
    assert err.value.code=={'oversize':'CLOUD_TOO_LARGE','invalid_wav':'CLOUD_AUDIO_INVALID','redirect':'CLOUD_HTTP','error_body':'CLOUD_RESPONSE'}[case]
    assert len(calls)<=2 and 'private' not in str(err.value)
