# StopWatch 对接语音服务：接口交接 v1.0.0

> 2026-09-20；依据语音服务 v0.3.1 app.py/broker.py 实现。文档版本独立于运行版本。
> 权威文件在语音仓库 00-docs/02-交接/StopWatch-语音服务接口契约-v1.0.0-【codex】.md；StopWatch 中同名文件为此次冻结副本。变更先更新权威文件，再同步副本并记录兼容性。

## 分工与基线

- StopWatch 仓库：机器人交互、电脑端连接程序、录音/播放、BLE 连接、表情/气泡、取消状态机；以后设备音频固件也在该仓库。
- 语音仓库：独立 ASR/TTS 服务、本地/云端适配、凭据及上传权限、取消/状态接口。不得把模型、venv 或 Key 复制到机器人项目。
- 造价智算：以后提供业务答案与依据。本轮只做听写回读，界面明确标为“跟读测试”，不冒充自由对话或造价问答。
- 语音 GitHub：https://github.com/zgzzmnbx/Daweiba-Voice-bot；交接前 main=c0e9b88，v0.3.1 功能提交 da599d4。
- 语音当前目录：D:/Codex-Temp/260921-【语音】语音智能体模块；StopWatch：D:/Codex-Temp/260529-ESP-32-M5StopWatch。仅作为本机定位，代码用可配置路径和服务地址。

## 连接与网络边界

默认 http://127.0.0.1:8765；GET /v1/health、/v1/capabilities、/v1/settings、/openapi.json 可只读探测。
当前 protocol_version=1。health.ready 仅表示两项本地模型均就绪；云端需看 cloud.state、live_verified 以及对应上传许可，configured 不保证账号额度/权限。
建议 StopWatch 电脑后端通过 HTTP 调用语音服务，再服务自己的同源网页。语音服务会拒绝其他端口网页直接跨源访问，不要放开通配 CORS，也不要借用语音诊断页的浏览器会话或注入脚本。现有 /v1/events 是状态事件，不是麦克风 PCM 流接口。

## 实际接口

| 方法 / 路径 | 输入与输出 |
| --- | --- |
| POST /v1/sessions | JSON {"replace":false}；返回 session_id、turn_id、protocol_version。已有会话返回 409 SESSION_BUSY；仅用户点击明确的“接管”后传 true |
| PATCH /v1/settings | X-Voice-Session 头；必须提交完整四字段，见下方。返回 routing |
| POST /v1/sessions/{session_id}/turns | 相同会话头；无业务正文；返回 turn_id，取消上一轮未完成请求 |
| POST /v1/asr/transcribe | 会话头；multipart 的 request_id、turn_id、audio；阻塞到完成后返回 JSON，转写在 result.text，不是顶层 text |
| POST /v1/tts/synthesize | 会话头；JSON 的 request_id、turn_id、text、speaker_id、speed、sample_rate；阻塞到完成后返回 audio/wav 字节，不是 JSON URL |
| GET /v1/requests/{request_id} | 会话头；返回 status、provider、metrics、result、error；不含音频字节 |
| POST /v1/requests/{request_id}/cancel | 会话头；JSON {"turn_id":当前轮次}；即使取消先到也记取消标记 |
| DELETE /v1/sessions/{session_id} | 会话头；结束自己的会话，清理缓存 |
| WS /v1/events | 连接后 5 秒内发送 {"session_id":"会话令牌"}；不把令牌写进 URL；事件只作辅助，新连接不重放历史，断线后用 HTTP 查状态 |

推荐 LC 配置（必须由 UI 明确允许文字上传后发送）：
```json
{"asr":"local","tts":"cloud","allow_audio_upload":false,"allow_text_upload":true}
```

TTS 请求示例（标识与轮次由客户端产生/获取）：
```json
{"request_id":"robot-1-tts","turn_id":1,"text":"你好，大尾巴。","speaker_id":3,"speed":1.0,"sample_rate":24000}
```

新会话会重置选路/权限到服务默认值；不能把“配了 Key”当作同意上传。PATCH 保存下一轮选路，因此先 PATCH 再创建 turn；撤销上传许可会立即取消相关云请求。识别上传录音、朗读上传文字必须各有独立开关。云端 TTS 固定 Cherry、speed=1.0。

## 时序、格式与停止

1. 探测服务 → 创建会话（不偷偷抢占诊断页）→ 用户选择路由和上传许可 → PATCH → 每轮开始 POST turns。
2. 浏览器录音由 StopWatch 电脑程序接收；实际转换成 PCM16、单声道、16kHz WAV，再调用 ASR。限制 0.1–30 秒、2MiB。不能将 WebM 改扩展名。
3. 跟读测试显示转写，可编辑后点击回读；同一 turn 下 ASR/TTS 使用不同 request_id。TTS text 最大 300 字符；长文本由交互层明确分段或提示，不截掉关键数字。
4. 收到完整 WAV → 解码并开始电脑播放，才进入 speaking；收到服务 completed 不等于播放已经开始。播放结束恢复 idle。
5. 停止必须先停止本地播放/录音、递增本地 generation，再发 cancel、丢弃所有旧轮次音频和 BLE 队列项，最后请求 idle/清气泡。网络取消不是扬声器静音证据。
6. 每会话仅一个控制端，服务队列最多两个等待项；单次原生推理取消可能只是作废输出。不要在取消后无限重试。
7. request_id 为 1–80 位英数、下划线或短横线；建议整个客户端会话内唯一。同轮同输入幂等，异输入冲突；跨轮或取消后不用旧 ID 重播。
8. 客户端请求超时留出排队与推理余量（建议首轮 60 秒），并能单独发取消；云端本次调用总超时 20 秒。取消/失败也可能产生云账单。

错误为 {"error":{"code":"…","message":"…","retryable":false}}；不要仅根据 retryable 自动重试云调用。401 SESSION_INVALID 重新建立会话并重新确认设置；409 SESSION_BUSY/旧轮/取消分别提示；429 队列/额度限制；503 模型未就绪等待；502 CLOUD_AUTH 核对本机 Key 权限，不误判为本地会话失效。

## BLE 与验收边界

复用 StopWatch tools/ble-expression-console.py 与固件 ble_control.cpp 协议。加密配对、单连接；BLE GATT 单包 20 字节，文字 F0/F1/F2、清屏 F3，整条 24 个 BMP 字符且不超过 72 UTF-8 字节。:say/:clear 是控制台命令，不是直接写给设备的字符串。
所有表情/文字发送必须串行；旧客户端 send_command 有旧状态读回误报风险，集成前增加匹配/超时/迟到回执测试。无法关联确认时显示“未确认”，不当成功。重连后只恢复当前状态，不重放旧轮次气泡和音频。设备离线只降级机器人显示，不阻断电脑语音。

语音既有证据：38 自动测试、真实 ASR/TTS、20 本地取消；云端朗读少样本 HTTP 完成约 1.84–2.39s。真人术语/主观音质/稳定性未完成。StopWatch v0.5.0 已写入和读回，但气泡实屏与蓝牙长期稳定性仍待验收。
新增功能尚未实现；不得据本文件宣称完成机器人交互。
