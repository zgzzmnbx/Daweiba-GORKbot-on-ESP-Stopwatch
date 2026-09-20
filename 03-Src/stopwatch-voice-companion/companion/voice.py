"""HTTP-only adapter: never reads voice engine files, environment or keys."""
import io
import uuid
import wave

import httpx


class VoiceError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def check_wav(data, *, microphone=False):
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or rate not in (16000, 24000):
                raise ValueError("需要 PCM16 单声道 WAV")
            if microphone and (rate != 16000 or not 0.1 <= frames / rate <= 30 or len(data) > 2097152):
                raise ValueError("录音需要 0.1–30 秒、16 kHz，且不超过 2 MiB")
            if frames <= 0 or len(wav.readframes(frames)) != frames * 2:
                raise ValueError("WAV 不完整")
    except (wave.Error, EOFError, ValueError) as exc:
        raise VoiceError(415, "AUDIO_INVALID", str(exc) or "音频格式无效") from exc
    return data


class VoiceClient:
    def __init__(self, base_url, timeout=60, transport=None):
        self.http = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport, trust_env=False)
        self.session = None

    async def call(self, method, path, *, session=None, **kwargs):
        token = session if session is not None else self.session
        headers = {"X-Voice-Session": token} if token else {}
        try:
            response = await self.http.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise VoiceError(504, "VOICE_TIMEOUT", "语音请求超时；请停止本轮后重试") from exc
        except httpx.RequestError as exc:
            raise VoiceError(503, "VOICE_OFFLINE", "语音服务未连接，请先启动独立语音服务") from exc
        if response.is_error:
            try:
                error = response.json()["error"]
            except (ValueError, KeyError):
                error = {"code": "VOICE_HTTP", "message": "语音服务返回异常"}
            if response.status_code == 401 and token == self.session:
                self.session = None
            raise VoiceError(response.status_code, error["code"], error["message"])
        return response

    async def health(self):
        return (await self.call("GET", "/v1/health")).json()

    async def capabilities(self):
        return (await self.call("GET", "/v1/capabilities")).json()

    async def connect(self, replace=False):
        value = (await self.call("POST", "/v1/sessions", json={"replace": replace})).json()
        self.session = value["session_id"]
        if value.get("protocol_version") != 1:
            await self.release()
            raise VoiceError(502, "PROTOCOL_VERSION", "语音服务协议不兼容，需要 protocol_version=1")
        return value

    async def routing(self, value):
        return (await self.call("PATCH", "/v1/settings", json=value)).json()["routing"]

    async def turn(self):
        return (await self.call("POST", f"/v1/sessions/{self.session}/turns")).json()["turn_id"]

    async def alive(self):
        return (await self.call("GET", "/v1/session", timeout=3)).json()

    async def transcribe(self, data, turn, request_id):
        check_wav(data, microphone=True)
        result = (await self.call("POST", "/v1/asr/transcribe",
            data={"request_id": request_id, "turn_id": str(turn)},
            files={"audio": ("recording.wav", data, "audio/wav")})).json()
        return result["result"]["text"]

    async def synthesize(self, text, turn, request_id):
        response = await self.call("POST", "/v1/tts/synthesize", json={
            "request_id": request_id, "turn_id": turn, "text": text,
            "speaker_id": 3, "speed": 1.0, "sample_rate": 24000})
        if response.headers.get("content-type", "").split(";")[0] != "audio/wav":
            raise VoiceError(502, "AUDIO_INVALID", "语音服务没有返回完整 WAV")
        return check_wav(response.content)

    async def status(self, request_id):
        return (await self.call("GET", f"/v1/requests/{request_id}")).json()

    async def cancel(self, request_id, turn, session):
        return (await self.call("POST", f"/v1/requests/{request_id}/cancel",
            session=session, json={"turn_id": turn}, timeout=5)).json()

    async def release(self):
        token, self.session = self.session, None
        if token:
            await self.call("DELETE", f"/v1/sessions/{token}", session=token)

    async def close(self):
        try:
            await self.release()
        except VoiceError:
            pass
        await self.http.aclose()

    @staticmethod
    def request_id(kind):
        return f"sw-{uuid.uuid4().hex}-{kind}"
