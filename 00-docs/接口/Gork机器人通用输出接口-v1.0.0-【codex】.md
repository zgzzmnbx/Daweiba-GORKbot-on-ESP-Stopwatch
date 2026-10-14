# Gork 机器人通用输出接口 v1.0.0

协议 `1.0`，PC 候选 v0.20.28-dev。接口只接本机程序的输出请求：表情、文字、语音。Gork 统一驱动网页小人、独立桌面小人及 Watch。外部程序负责业务阶段与输出内容的映射；Gork 不解释 `stage`，不启动或修改业务，不提供录音入口。

## 三分钟接入

1. 在 Gork「通知哨兵 → 程序接入」登记程序标识，授予显示端、声音端和最高优先级，再启用一次。登记默认关闭、声音默认无授权。令牌仅首次返回；保存到调用程序的私有配置，不放前端、日志或 Git。
2. 或在 Gork 模块目录运行下述命令，将令牌直接写入调用程序的私有文件。命令不输出令牌；然后在 Gork 界面编辑权限并启用。

```powershell
python -m companion.external_setup --source astra --token-file "调用程序目录/config/astra-gork-token.local.json"
```

3. 调用端可直接复制 `companion/external_client.py`，仅依赖 Python 标准库。发送前查 `/status`；创建同一任务单调递增且跨重启保存的 `sequence`。同一个请求重试须保留完全相同的 event_id、occurred_at 和内容。

```python
from external_client import GorkClient
client = GorkClient('config/astra-gork-token.local.json')
request = client.event(task_id='task-123', attempt='match-2', stage='match_start',
                       sequence=42, kind='state', expression='working',
                       expression_mode='loop', text='正在匹配', display_target='both')
receipt = client.send(request)  # HTTP 202 是已入队，不是已播放
# 定时检查回执；生效后每10秒续期，queued 状态先等待，不复活过期记录。
if client.receipt(request['event_id'])['status'] in ('active', 'dispatching', 'partial'):
    client.heartbeat(request['event_id'], 'task-123', 'match-2')
# 新阶段用新的 event_id 和更高 sequence；普通通知可加 speech={'text':'匹配完成'}
```

业务简单事件可由 SDK `event(...)` 构造；完整控制请求直接 `send(dict)`。两种进入相同校验/排队流程。默认地址 `http://127.0.0.1:8766`，只能 loopback HTTP。本机身份并不免除独立授权，Host/Origin 也须匹配本机地址。当前不开放远端访问、跨站 CORS、WebSocket、外部音频上传或音色覆写；协议版本为以后扩展预留。

## HTTP 路由

所有程序调用带 `Authorization: Bearer <本程序令牌>`。不用控制台 `X-Companion-Client`，不接管人的语音会话。

| 方法与路径（前缀 /api/external） | 用途 |
| --- | --- |
| GET /capabilities | 无令牌可读；协议、表情、完整 JSON Schema、容量限制 |
| GET /protocol | 无令牌可读；本文 |
| GET /status | 本来源启用状态、输出权限、暂停状态、当前声音位置 |
| POST /notifications | 接收一次输出；新请求 202，完全相同重试 200 |
| GET /notifications/{event_id} | 只读本来源回执 |
| DELETE /notifications/{event_id} | 取消本来源该条，移除显示；显式取消可停止该条语音 |
| POST /heartbeat | 状态续期，不重新播放、不复活失效状态 |
| POST /cancel | 取消本来源 task_id + attempt；24小时拒绝该轮次晚到事件 |

控制台所有者专用：GET /overview，POST /clients，PUT /clients/{source}，POST /owner-cancel，PATCH /output，POST /resume。需当前工作台 X-Companion-Client，并校验所有权；外部令牌不能调用这些操作。全局停止通过已有 `/api/desktop/stop`：清队列、停止输出并暂停外部通知，需用户在哨兵页恢复；恢复不会重播旧事件。

## 请求字段

PC v0.20.31-dev，用户最新确认覆盖 v30：`speech.mode=tts` 每次即时合成；`auto` 对完整渲染文本复用当前音色/模型/区域/语速/采样率/服务版本缓存，缺失时合成并保存；`cached` 只读已有缓存。金额、风险项数和任务变量也可复用，完整文字有变化则是新缓存键。缓存不改变通知幂等与事件回执，仍遵循当前会话、上传许可、取消与人工优先；电脑/Watch 共享 WAV，设备播放限长仍由原通道独立检查。

```json
{
  "protocol_version":"1.0", "source":"astra", "event_id":"f142b4b2da1d4736bceabc4f6417a071",
  "task_id":"task-123", "attempt":"match-2", "stage":"match_result", "sequence":43,
  "kind":"notice", "occurred_at":"2026-10-08T10:00:00+08:00",
  "expression":"happy", "expression_mode":"once", "text":"匹配完成，请复核",
  "display_target":"both", "duration_ms":8000,
  "speech":{"text":"匹配完成，请复核。", "target":"current", "mode":"auto"},
  "priority":2, "ttl_ms":90000
}
```

| 字段 | 规则与默认值 |
| --- | --- |
| protocol_version | 必填，严格 1.0 |
| source | 必填，小写程序ID，`[a-z][a-z0-9_-]{0,39}`，必须等于令牌来源 |
| event_id | 必填，1–100字符 `[A-Za-z0-9_.:-]`，本来源唯一；内容改变须换新ID |
| task_id / attempt | 必填，各1–100字符。attempt 是真实执行轮次；没有轮次时可标明 `event:<event_id>`，不能假充旧匹配轮次 |
| stage | 必填，1–60字符 `[A-Za-z0-9_-]`，纯标签 |
| sequence | 必填正整数；同来源同task严格递增，跨attempt/程序重启延续，调用端持久化 |
| kind | notice 默认：短通知；state：持续状态 |
| occurred_at | 必填，带时区ISO8601；未来最多30秒，超过TTL拒绝 |
| expression | 默认idle；内置ASCII ID或真实 `motion-*` 自定义ID，缺失条目422；`happy-work`仅Watch |
| expression_mode | 默认once；loop允许；不改用户表情参数 |
| text | 默认空，最多300字；Watch按现有24字/72 UTF-8字节显示限制生成短摘要，桌面保留全文 |
| display_target | desktop/watch/both/none；默认both，必须在来源授权内 |
| duration_ms | notice显示时长500–60000ms，默认8000；不缩短已经开始的语音 |
| speech | 默认null，即无声音；text1–300字，target默认current，可pc/watch；mode默认auto，可tts/cached |
| priority | 整数0–5，默认2，不能超过登记上限。0背景、1低、2普通、3重要、4失败、5紧急；仍不抢占人工录音 |
| ttl_ms | 入队有效期1000–90000ms，默认30000。建议完成/失败90000，普通30000 |
| lease_ms | state租约1000–90000ms，默认30000；建议每10秒续期 |
| supersedes | 最多20个本来源旧event_id；仍不会默认中断已开始的语音 |
| amount_summary | 可选兼容金额元数据；value十进制字符串、CNY、yuan、basis tax_included/tax_excluded、attempt相同、calculation_status recalculated/unconfirmed；不自动改写朗读文字 |

严格拒绝未知字段和字符串化整数，不接受任意URL、HTML、音频文件路径、音色、音量、上传许可和麦克风控制字段。完整机器Schema以 `/capabilities` 中 `schema` 为准，随本文提供相同静态JSON。

语音 `current` 沿用控制台当前声音输出；只选一个声音端，表情/文字可双端。音色、语速、云上传许可沿用已应用设置。`auto` 优先使用匹配当前音色的固定短句缓存，否则走当前TTS；当前固定缓存为Cherry，仅用户也选择cloud/Cherry时使用。`cached` 找不到短句或音色不符会在回执报告失败，不偷偷换人声。云TTS仍须现有语音会话和文字上传许可，保存阶段映射不会调用云。

## 排队、取代、租约与恢复

- 各来源共用自动通知通道，按优先级、同级FIFO。普通通知排队；人工录音、回答和手动表情优先。事件入队TTL到期不补播。
- 同来源同task的新sequence取消尚未开始的旧通知语音，并替代旧显示。不同来源互不取消。新state和priority≥4的提醒可立即更新桌面视觉；正在Watch音频中时，设备视觉须等现有设备操作结束。
- 新阶段及重要失败默认不会停止已开始的旧语音；下一段仍排队。显式取消本条/本轮、用户停止全部、手动语音或撤销权限则会停止对应输出。
- state只在租约内有效，心跳只续显示，不播声音；失效、手动清理或新阶段替换后，心跳409。notice按duration失效。恢复后回到仍有效的其他状态或待机。
- 来源disable/权限修改取消其在途输出；重新enable仅处理新事件。Gork重启保留回执和sequence水位，但把在途标interrupted，绝不补播。
- 同一Astra来源不能同时启用直接推送和兼容轮询，否则409 SOURCE_MODE_CONFLICT。原版知识查询和业务查询保留独立边界。
- 全局最多32个在途，每来源8个；回执最多1000条/24小时。调用端不要因每次轮询新造event_id；任务序列水位持久保存。

心跳体：`{"event_id":"...","task_id":"task-123","attempt":"match-2"}`。
取消体：`{"task_id":"task-123","attempt":"match-2"}`。

## 回执与错误

202返回包含source/event_id/task_id/attempt/stage/status/accepted_at/receipt_url/request/delivery。status可能queued、dispatching、active（state）、completed、partial、failed、cancelled、superseded、expired、interrupted。`duplicate:true`只说明同一请求已收，不会重新播放。

`delivery`逐端记录：desktop displayed；Watch accepted/offline/failed/suppressed；speech completed_by_os/device_playback_completed或VOICE_SESSION_REQUIRED等小写原因。部分失败不会阻断已成功显示的一端。显示已提交、操作系统播放结束、Watch播放回执均不是人耳验收。state部分成功可继续心跳保留成功端。

| HTTP | 常见错误code | 调用端处理 |
| --- | --- | --- |
| 401 | EXTERNAL_AUTH_REQUIRED | 检查私有令牌；不自动登记/接管 |
| 403 | EXTERNAL_CLIENT_DISABLED / EXTERNAL_SOURCE_MISMATCH / EXTERNAL_OUTPUT_DENIED / EXTERNAL_PRIORITY_DENIED | 请求用户在Gork配置；不绕过 |
| 409 | EXTERNAL_EVENT_CONFLICT / EXTERNAL_EVENT_SUPERSEDED / EXTERNAL_PAUSED / SOURCE_MODE_CONFLICT / EXTERNAL_STATE_NOT_ACTIVE | 保留精确错误码；旧事件不重造后补播 |
| 410 | EXTERNAL_EVENT_EXPIRED / EXTERNAL_TASK_CANCELLED | 终止本事件重试 |
| 422 | INVALID_INPUT / EXTERNAL_EXPRESSION_MISSING | 修正映射或Schema |
| 429 | EXTERNAL_QUEUE_FULL / EXTERNAL_RECEIPTS_FULL | 在原TTL内有限退避，保留相同完整请求；过期丢弃 |

网络超时可能已经收件，只能重发原请求或查回执；不能换event_id。退出/取消产生真实轮次取消。调用端重启、首次启用、重新启用均以当前业务事件位置建立基线，不发送历史事件。

## Astra 接入职责

智算设置保存每阶段启用、表情ID/播放方式、文字模板、语音模板、显示端、声音位置、优先级、时长和有效期。模板只替换许可变量，映射页面不运行真实任务，不改匹配引擎或金额口径。实际业务事件驱动 outbox，锁定event_id/payload/sequence；worker发送、查询回执，状态每10秒心跳，真实取消移除本轮。

设置中的“调试”页可手动发送全部阶段，复用已保存的映射和同一发送通道。使用独立 `debug-*` task_id/attempt，文字和声音明确标记调试，展示请求摘要、接收状态和 desktop/watch/speech 逐端回执，可报活持续状态及取消本次调试。手动调试不发布真实业务事件、不运行匹配/风险检查/报告，也不改变真实金额。模拟金额必须注明模拟数据与公式未确认。调试仍受 Gork 来源启用、端点权限、优先级和当前声音设置限制；仅关闭自动业务推送不妨碍用户手动调试。

成功金额沿用既有attempt绑定的精确十进制口径；公式重算未确认须明确“表内金额/未确认”，失败或未知不报金额。报告阶段仅在真实成果成功生成后发，复核发送仅真实投递后发，不把模拟点击当业务成功。

令牌只在调用端后端读取。Stage映射可导出，令牌不可导出。正式Astra和Gork初次配置保持关闭，由用户核对权限后启用；隔离联调用独立临时令牌和替身输出，报告须区分接口验证与真实任务/声音验收。
