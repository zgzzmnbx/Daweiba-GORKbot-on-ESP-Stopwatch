"""Beijing DashScope adapters. No retries, no persistent inputs, no secret-bearing errors."""
import asyncio
import base64
import io
import json
import os
import struct
import time
import wave
from urllib.parse import urlsplit, urlunsplit

import httpx
import numpy as np

from .audio import decode_wav, encode_wav, resample


class CloudError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def audio_url(value):
    """Only known provider result buckets, HTTPS, no redirects or forwarded credentials."""
    try:
        url = urlsplit(value)
        allowed = {'dashscope-result-bj.oss-cn-beijing.aliyuncs.com',
                   'dashscope-result-wlcb.oss-cn-wulanchabu.aliyuncs.com'}
        if url.scheme not in ('http', 'https') or url.hostname not in allowed or url.port not in (None,443) or url.username or url.password or url.fragment:
            raise ValueError()
        return urlunsplit(('https', url.netloc, url.path, url.query, ''))
    except (ValueError, TypeError):
        raise CloudError(502, 'CLOUD_AUDIO_URL', '云端音频地址不在允许范围，已停止下载') from None


def usage_fields(value):
    if not isinstance(value, dict):
        return {}
    return {k:v for k,v in value.items() if k in ('characters','input_tokens','output_tokens','total_tokens','prompt_tokens','completion_tokens')
            and type(v) in (int,float) and 0 <= v < 10**9}


def decode_output(raw, target_rate):
    try:
        # DashScope's completed download can retain its streaming length marker.
        # Normalize only the observed canonical header, not arbitrary truncated WAVs.
        if (len(raw) >= 44 and raw[:4] == b'RIFF' and raw[8:16] == b'WAVEfmt '
                and struct.unpack_from('<I', raw, 16)[0] == 16
                and raw[36:40] == b'data'
                and struct.unpack_from('<I', raw, 40)[0] == 2147483547):
            if (len(raw)-44) % 2:
                raise ValueError()
            normalized = bytearray(raw)
            struct.pack_into('<I', normalized, 4, len(raw)-8)
            struct.pack_into('<I', normalized, 40, len(raw)-44)
            raw = bytes(normalized)
        with wave.open(io.BytesIO(raw),'rb') as wav:
            rate, frames = wav.getframerate(), wav.getnframes()
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getcomptype()!='NONE' or rate not in (16000,24000,44100,48000) or not 0 < frames <= rate*180:
                raise ValueError()
            pcm=wav.readframes(frames)
            if len(pcm)!=frames*2:
                raise ValueError()
        samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768.
        return encode_wav(resample(samples,rate,target_rate),target_rate), rate, frames/rate
    except (ValueError, wave.Error, EOFError, OSError):
        raise CloudError(502,'CLOUD_AUDIO_INVALID','云端未返回有效的单声道 PCM WAV') from None


class CloudEngines:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport
        self.verified = {'asr':False, 'tts':False}

    def available(self):
        return bool(os.environ.get(self.config.cloud_key_env,'').strip())

    def status(self):
        return {'state':'configured' if self.available() else 'missing_key',
                'message':'已配置密钥，真实可用性需请求验证' if self.available() else '尚未配置本模块的百炼 API Key',
                'region':self.config.cloud_region,'live_verified':dict(self.verified)}

    async def _read(self, client, method, url, limit, **kwargs):
        async with client.stream(method,url,**kwargs) as response:
            code=response.status_code
            if code in (401,403):
                raise CloudError(502,'CLOUD_AUTH','云端鉴权失败，请核对北京地域 API Key 与模型权限')
            if code==429:
                raise CloudError(429,'CLOUD_RATE_LIMIT','云端限流或额度不足；本次不自动重试')
            if not 200 <= code < 300:
                raise CloudError(502,'CLOUD_HTTP','云端请求失败；请检查模型权限或稍后手动重试')
            body=bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body)>limit:
                    raise CloudError(502,'CLOUD_TOO_LARGE','云端响应超过大小限制')
            return bytes(body)

    async def run(self, kind, payload):
        key=os.environ.get(self.config.cloud_key_env,'').strip()
        if not key:
            raise CloudError(503,'CLOUD_NOT_CONFIGURED','请先在本机配置本模块的百炼 API Key')
        start=time.perf_counter()
        try:
            async with asyncio.timeout(self.config.cloud_timeout):
                async with httpx.AsyncClient(timeout=self.config.cloud_timeout, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                    headers={'Authorization':f'Bearer {key}'}
                    if self.config.cloud_workspace:
                        headers['X-DashScope-WorkSpace']=self.config.cloud_workspace
                    if kind=='asr':
                        _, duration=decode_wav(payload['audio'],self.config.max_seconds,self.config.max_upload)
                        host=f'{self.config.cloud_workspace}.cn-beijing.maas.aliyuncs.com' if self.config.cloud_workspace else 'dashscope.aliyuncs.com'
                        url=f'https://{host}/compatible-mode/v1/chat/completions'
                        body={'model':self.config.cloud_asr_model,'stream':False,'messages':[{'role':'user','content':[{'type':'input_audio','input_audio':{'data':'data:audio/wav;base64,'+base64.b64encode(payload['audio']).decode('ascii')}}]}], 'asr_options':{'enable_itn':True}}
                    else:
                        if payload['speed']!=1.:
                            raise CloudError(400,'CLOUD_SPEED','当前云端音色仅支持自然语速，请选择 1.0×')
                        url='https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
                        from .voices import CLOUD_VOICE_IDS
                        voice = payload.get('cloud_voice') or self.config.cloud_voice
                        if voice not in CLOUD_VOICE_IDS:
                            raise CloudError(400, 'VOICE_INVALID', '请选择服务提供的云端音色')
                        body={'model':self.config.cloud_tts_model,'input':{'text':payload['text'],'voice':voice,'language_type':'Chinese'}}
                    raw=await self._read(client,'POST',url,1024*1024,headers=headers,json=body)
                    api_ms=round((time.perf_counter()-start)*1000,2)
                    data=json.loads(raw)
                    if not isinstance(data,dict) or data.get('code') or data.get('error') or data.get('status_code',200)!=200:
                        raise CloudError(502,'CLOUD_RESPONSE','云端返回错误或不完整结果')
                    usage=usage_fields(data.get('usage'))
                    if kind=='asr':
                        result_text=data['choices'][0]['message']['content']
                        if not isinstance(result_text,str) or len(result_text)>10000:
                            raise ValueError()
                        result={'text':result_text.strip(),'language':'','input_seconds':duration,'usage':usage}
                    else:
                        download_start=time.perf_counter()
                        safe_url=audio_url(data['output']['audio']['url'])
                        # Do not pass the API Authorization header to object storage.
                        wav=await self._read(client,'GET',safe_url,18*1024*1024)
                        download_ms=round((time.perf_counter()-download_start)*1000,2)
                        audio, native_rate, duration=decode_output(wav,payload['sample_rate'])
                        result={'audio':audio,'sample_rate':payload['sample_rate'],'native_sample_rate':native_rate,
                                'output_seconds':round(duration,3),'voice':voice,'streaming':False,'usage':usage}
                    metrics={'cloud_api_ms':api_ms,'provider_elapsed_ms':round((time.perf_counter()-start)*1000,2)}
                    if kind=='tts': metrics['audio_download_ms']=download_ms
                    if self.transport is None:
                        self.verified[kind] = True
                    return {'provider':f'dashscope_qwen_{kind}','result':result,'metrics':metrics}
        except CloudError:
            raise
        except (TimeoutError,httpx.TimeoutException):
            raise CloudError(504,'CLOUD_TIMEOUT','云端请求超时；未重试，停止后不会播放迟到音频') from None
        except httpx.HTTPError:
            raise CloudError(502,'CLOUD_NETWORK','无法连接云端，请检查网络；本次不自动重试') from None
        except (KeyError,IndexError,TypeError,ValueError):
            raise CloudError(502,'CLOUD_RESPONSE','云端返回格式不符合接口契约') from None
