# v0.9.0 语音模块接入说明

Gork 通过独立语音服务的版本化 HTTP 接口使用 ASR/TTS。服务、模型、虚拟环境与凭据仍在语音项目；本仓库只保留客户端适配、浏览器采集/播放模块和调用示例。

## 可复用边界

- `companion/voice.py` 的 `VoiceClient` 只依赖 `httpx` 和标准库，不导入 Gork 页面、角色、BLE、模型或凭据。
- `static/audio-client.js` 提供无页面业务依赖的 `Recorder` 和 `WavPlayer`；调用方显式启动、停止和释放资源。
- `tools/examples/voice_service_http_example.py` 可独立探测能力；传入 `--text` 才会请求本地 TTS，保存 PCM WAV 但不自动播放、录音或请求云端。

## 最小调用

```powershell
& 'Codex-Temp/.venv-companion/Scripts/python.exe' tools/examples/voice_service_http_example.py --url http://127.0.0.1:8765
& 'Codex-Temp/.venv-companion/Scripts/python.exe' tools/examples/voice_service_http_example.py --url http://127.0.0.1:8765 --text '这是本地语音服务的独立调用示例' --output Codex-Temp/example.wav
```

服务协议为 `protocol_version=1`。本地 TTS 返回 PCM WAV；ASR 需要调用方明确提供 WAV。语音服务是单活会话：第二消费者应处理 HTTP 409，先由原消费者释放会话，不能自动抢占。Gork 的“仅释放语音会话”不释放角色/StopWatch 工作台控制权。

## 本轮验收边界

V01、V04、V05、V06、V07、V08 已由模块和模拟回归覆盖。V02/V03 已在临时 `127.0.0.1:8875` 独立服务实测：示例 TTS 生成 147,244 字节 PCM WAV；语音仓库自带的非私人 `zh.wav` 经 ASR 返回非空文本。服务处于单活会话时，第二会话实测返回 HTTP 409，释放后新会话可创建。本轮未启动 Gork 后端/Electron、未使用麦克风、未发云端请求，也未占用正式实例。
