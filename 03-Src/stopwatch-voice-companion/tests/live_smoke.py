"""Opt-in LOCAL-ONLY integration: generated WAV -> ASR, never uses a microphone."""
import array
import io
import json
import sys
import uuid
import wave

import httpx


def run(base_url='http://127.0.0.1:8766'):
    with httpx.Client(base_url=base_url, timeout=60, trust_env=False,
            headers={'X-Companion-Client':str(uuid.uuid4())}) as client:
        connect = client.post('/api/session', json={'replace':False})
        connect.raise_for_status()  # Never take over an existing session for a test.
        try:
            assert connect.json()['routing'] == {'asr':'local','tts':'local','allow_audio_upload':False,'allow_text_upload':False}
            client.post('/api/begin',json={'generation':1}).raise_for_status()
            response = client.post('/api/tts',json={'generation':1,'text':'你好，今天是个好天气，我们开始测试。'})
            response.raise_for_status()
            assert response.headers['content-type'].startswith('audio/wav')
            with wave.open(io.BytesIO(response.content),'rb') as wav:
                assert wav.getnchannels()==1 and wav.getsampwidth()==2 and wav.getframerate()==24000
                pcm = array.array('h',wav.readframes(wav.getnframes()))
                if sys.byteorder!='little': pcm.byteswap()
            # Linear resampling of synthetic 24k speech, for service plumbing only.
            reduced = array.array('h')
            for n in range(int(len(pcm)*2/3)):
                x=n*1.5; start=int(x); mix=x-start
                reduced.append(round(pcm[start]*(1-mix)+pcm[min(start+1,len(pcm)-1)]*mix))
            if sys.byteorder!='little': reduced.byteswap()
            output=io.BytesIO()
            with wave.open(output,'wb') as wav:
                wav.setparams((1,2,16000,0,'NONE','NONE')); wav.writeframes(reduced.tobytes())
            client.post('/api/begin',json={'generation':2}).raise_for_status()
            text = client.post('/api/asr',content=output.getvalue(),headers={'Content-Type':'audio/wav','X-Generation':'2'})
            text.raise_for_status(); assert text.json()['text'].strip()
            client.post('/api/stop',json={'generation':3}).raise_for_status()
            stale=client.post('/api/tts',json={'generation':2,'text':'不应播放'})
            assert stale.status_code==409
            print(json.dumps({'local_tts_wav_bytes':len(response.content),'synthetic_asr_text':text.json()['text'],
                'stale_request':stale.status_code,'cloud_upload':False,'microphone_used':False},ensure_ascii=False))
        finally:
            client.delete('/api/session').raise_for_status()


if __name__=='__main__': run()
