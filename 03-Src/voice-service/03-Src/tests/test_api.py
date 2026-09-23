import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from voice_service.app import create_app
from voice_service.audio import encode_wav
from voice_service.broker import Broker
from voice_service.config import Settings
from tests.fake_worker import worker


@pytest.fixture
def client():
    config = Settings()
    with TestClient(create_app(config, Broker(config, worker)), base_url='http://127.0.0.1:8765') as client:
        for _ in range(500):
            if client.get('/v1/health').json()['ready']:
                break
            time.sleep(.02)
        else:
            raise AssertionError('Worker not ready')
        yield client


def identity(client):
    s = client.post('/v1/sessions', json={}).json()['session_id']
    headers = {'X-Voice-Session': s}
    t = client.post(f'/v1/sessions/{s}/turns', headers=headers).json()['turn_id']
    return headers, t


def test_real_http_contract_with_explicit_fixture(client):
    headers, turn = identity(client)
    wav = encode_wav(np.zeros(16000), 16000)
    r = client.post('/v1/asr/transcribe', headers=headers, files={'audio': ('x.wav', wav, 'audio/wav')}, data={'request_id': 'a', 'turn_id': turn})
    assert r.status_code == 200 and r.json()['provider'] == 'test_fixture'
    assert client.get('/v1/requests/a').status_code == 401
    body = {'request_id': 'b', 'turn_id': turn, 'text': '测试语音'}
    r = client.post('/v1/tts/synthesize', headers=headers, json=body)
    assert r.status_code == 200 and r.content.startswith(b'RIFF')
    assert r.headers['content-type'] == 'audio/wav'
    assert 'audio' not in client.get('/v1/requests/b', headers=headers).json()['result']
    with client.websocket_connect('ws://127.0.0.1:8765/v1/events') as ws:
        ws.send_json({'session_id': headers['X-Voice-Session']})
        assert ws.receive_json()['type'] == 'health'
        ws.send_text('close')


def test_origin_size_validation_and_no_input_echo(client):
    assert client.post('/v1/sessions', json={}, headers={'Origin': 'https://untrusted.example'}).status_code == 403
    assert client.get('/v1/health', headers={'Host': 'evil.example'}).status_code == 403
    assert client.post('/v1/tts/synthesize', content=b'x'*17000).status_code == 413
    assert client.post('/v1/asr/transcribe', content=b'x'*(2200000)).status_code == 413
    secret = 'DO_NOT_ECHO_INPUT'
    response = client.post('/v1/tts/synthesize', json={'text': secret, 'unexpected': secret})
    assert response.status_code == 400 and secret not in response.text
    headers, turn = identity(client)
    response = client.post('/v1/asr/transcribe', headers=headers, files={'audio': ('x.wav', b'fake')}, data={'request_id': 'bad', 'turn_id': turn})
    assert response.status_code == 415
    response = client.post('/v1/tts/synthesize', headers=headers, json={'request_id': 'cloud', 'turn_id': turn, 'text': '测试', 'provider': 'cloud'})
    assert response.status_code == 400


def test_settings_expose_no_cloud_or_model_paths(client):
    settings = client.get('/v1/settings').json()
    assert not settings['cloud']['allow_audio_upload']
    assert not settings['cloud']['allow_text_upload']
    assert 'api_key' not in str(settings) and 'model_directory' not in str(settings)
    assert client.get('/').status_code == 200


def test_cloud_selection_auth_permission_revocation_and_missing_key(client,monkeypatch):
    monkeypatch.delenv('ZHISUAN_VOICE_DASHSCOPE_API_KEY',raising=False)
    body={'asr':'local','tts':'cloud','allow_audio_upload':False,'allow_text_upload':True}
    assert client.patch('/v1/settings',json=body).status_code==401
    headers,_=identity(client)
    result=client.patch('/v1/settings',headers=headers,json=body)
    assert result.status_code==200 and result.json()['routing']==body
    session=headers['X-Voice-Session']
    turn=client.post(f'/v1/sessions/{session}/turns',headers=headers).json()['turn_id']
    result=client.post('/v1/tts/synthesize',headers=headers,json={'request_id':'cloud-key-missing','turn_id':turn,'text':'测试'})
    assert result.status_code==503 and result.json()['error']['code']=='CLOUD_NOT_CONFIGURED'
    body['allow_text_upload']=False
    assert client.patch('/v1/settings',headers=headers,json=body).status_code==200
    result=client.post('/v1/tts/synthesize',headers=headers,json={'request_id':'cloud-forbidden','turn_id':turn,'text':'测试'})
    assert result.status_code==403 and result.json()['error']['code']=='UPLOAD_PERMISSION_REQUIRED'
    assert client.get('/v1/health').json()['cloud']['process_requests']==0
