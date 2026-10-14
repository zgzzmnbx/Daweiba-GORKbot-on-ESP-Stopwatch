# Gork 通用输出接口与哨兵实施验收

日期：2026-10-08。Gork 候选 PC v0.20.28-dev，通用输出协议 1.0；Watch 固件不变。

## 交付范围

本轮依据用户确认的输出边界实施本机通用接口与通知哨兵，并授权配合 Astra 指定线程 `01a11685-a05b-7dc1-b41c-684b63835c7c`。外部程序提供阶段、表情、文字、时长和可选语音，Gork 不判断业务阶段。声音沿用当前输出、音色和上传许可。接口不开放录音、业务控制、任意音频路径或全局设置修改。

- `companion/external.py`：来源独立令牌与输出/优先级权限、严格请求、持久序列/回执/取消墓碑、幂等、TTL、阶段替换、状态租约和心跳。各来源共用原自动通知通道；普通排队，已开始语音不会因普通新阶段而截断，人工操作优先。
- `companion/external_setup.py`、`external_client.py`：本机登记与标准库 Python SDK。Gork 仅保存令牌哈希，调用端私有文件保存令牌，GET 列表和日志不回显。
- “通知哨兵”页面：当前双端输出、来源权限、最近通知与逐端回执、取消及恢复；原造价/Astra 兼容轮询折叠保留，禁止同一 Astra 来源推送和轮询并开。
- Astra 设置新增阶段映射与手动调试。调试复用同一映射和发送通道，使用独立 `debug-*` 标识、明确模拟数据，不产生真实业务事件或执行匹配、检查、报告。

接口说明：[中文快速接入文档](../../../00-docs/接口/Gork机器人通用输出接口-v1.0.0-【codex】.md)；[JSON Schema](../../../00-docs/接口/Gork通知请求-schema-v1.0.0-【codex】.json)；[PRD39](../../../00-docs/00-PRD/39-Gork通用输出接口与阶段联动-【codex】.md)。

## Gork 自动验证

| 范围 | 结果 | 证据 |
| --- | --- | --- |
| Python 全量 | 223 passed，2 项依赖弃用提示 | `tests/backend-223.log` |
| 前端 | 99 passed | `tests/frontend-99.log` |
| 桌面 | 38 passed | `tests/desktop-38.log` |
| UI 生成一致性 | build:ui / check:ui 通过 | 模板生成页与组件样式一致 |
| 实际 Electron 布局 | 36 PASS，三主题×四宽度×概览/编辑/兼容轮询 | `tests/external-layout.json` 与同目录截图 |

11 项通用接口测试覆盖严格输入、鉴权/来源边界、输出端与优先级、幂等冲突、取消晚到、阶段并发、取消未启动任务、心跳不复活、普通通知视觉排队、已开始声音保留、人工操作、重启不重播、实际 FastAPI Host/Origin 与推送/轮询互斥。UI 测试覆盖草稿保留、安全文本、令牌一次显示和清理、逐条取消与来源登记默认关闭。

回归使用隔离 NetworkStore 默认路径，防止读到用户真实 Wi-Fi only 偏好改变替身测试前提；明确传入测试路径的 NetworkStore 不受该 fixture 改动。生产网络偏好未写入。

## 双方真实 HTTP 联测

Astra 实际 producer、attempt 金额适配器、持久 outbox 与原 SDK 经 HTTP 接入隔离 Gork `127.0.0.1:8782`，6 项通过：持续状态 active、heartbeat、完成阶段高序列、attempt 绑定金额、同 ID 精确重复、取消后晚到 410。联合证据为 `tests/astra-http-joint-6.json`（金额 9447173.00 元为隔离模拟数据，公式重算未确认，绑定同一 attempt）。心跳仅续期，不重复输出。

隔离服务复用正式 FastAPI 接口与调度逻辑，输出使用 Robot/Voice/操作系统播放替身。真实 HTTP 验证不代表实际业务结果、Watch 屏幕或人耳声音验收。

## 当前正式状态与启用

正式 Gork 8766 保持此前 v0.20.27-dev，Wi-Fi 路由；本轮未重启正在使用的服务。新后端须从托盘退出，再以原快捷方式正常打开加载 v0.20.28-dev。仅刷新不能加载新增后端路由。

Astra 正式来源已经登记为 `astra`、关闭状态，显示权限 desktop/watch、声音权限为空、最高优先级 2。调用端私有文件已配置到实际工作树的 `config/astra-gork-token.local.json`，没有把令牌发到聊天、日志或源码包。用户在新“通知哨兵”中核对需要的显示端、声音端和优先级后启用；若兼容 Astra 轮询启用，先关闭该轮询再启用推送。Astra 调试和自动业务推送均须通过 Gork 的授权。

README、项目 AGENTS、当前版本计划、PRD39、模块 README 和 CHANGELOG 已更新，CHANGELOG 保持最近五个版本。既有未提交改动保留；未提交、推送、烧录、修改设备绑定或热点，未触发真实匹配、云语音或实体播放。性能与长稳继续按用户要求延期。

## Astra 新调试页面交付证据

Astra v0.9.22：入口为“设置 → 机器人联动 → 调试”，可从左侧选择全部 13 阶段，发送已保存映射、读取实际回执、为持续状态报活以及取消调试。匹配完成可附加模拟金额；未保存草稿阻止发送，避免预览和实际请求不一致。

已独立读取 `tests/astra-debug-http-13.json`：13 阶段依次送达隔离 8782，4 项 state 为 active、9 项 notice 为 completed，desktop displayed / Watch accepted；全部独立 debug task/attempt、模拟标识，speech=null。浏览器实际点击发送、报活与取消完成，亮色调试/暗色设置截图已保存为 `tests/astra-debug-light.png` / `tests/astra-settings-dark.png`。这些是隔离组件和输出替身验证，不涉及实体音频。

开发目录 `D:\Codex-Temp\260613-【智算Astra】` 的 158 项 Python、146 项前端、正式构建通过，日志复制到本报告 `tests/astra-backend-158.log`、`astra-frontend-146.log`、`astra-build.log`。Astra 线程最终交接确认：C 活动目录的 48 项 Gork 专项、146 项前端及构建也通过；取消失败保留持久重试，并在调试 UI 区分本地取消和远端确认。

原入口实际使用目录为 `C:\Users\zgzzm\.codex\worktrees\astra-ui-handoff\260613-【智算Astra】`；接口配置/桥接/映射、GorkConsole 页面/样式和 SDK 六个核心文件的 SHA256 与开发目录逐项一致，package 版本均为 0.9.22。该线程仅同步本轮文件并定点调整 App/server/启动身份，不覆盖其他迁移改动或运行数据。源码、构建与文档已同步；正式 5189 UI bundle 为新版，宿主尚需正常重开。Astra 线程尝试“停止当前宿主以重启”被自动审批拒绝，返回“被策略阻止”，未给出更具体原因，保留原服务并交由用户手动重开。Gork 正式 8766 仍为27，也须正常重开加载28；未绕过该拒绝，不把 UI bundle 更新当成后端已加载。

Astra 确认新增隔离联测完成后关闭本线程拥有的 8782 测试服务。没有停止其他正式程序或服务。

Astra 最终补充：原正式 5189 页面已实际打开“设置 → 机器人联动 → 调试”，13 阶段、自动通知关闭/声音关闭、旧27版哨兵入口状态正确，浏览器零 error；截图复制为 `tests/astra-debug-formal-entry.png`。这仅确认正式前端入口，宿主仍需用户正常重开。其启动器 CheckOnly 因旧宿主缺新 hash/capabilities 正确拒绝复用。Astra 已清理私有 5193/5194 测试服务和标签页，未变动 8766/5189 服务；两目录 README/AGENTS/PRD/CHANGELOG 和 `00-docs/handoff/2026-10-08-Gork通用通知接口候选接入.md` 的正式 v1.0.0 实施记录完成。

随后运行状态更新（取代上述 Astra 待加载结论）：另一项操作已正常重开 5189，Astra 线程确认新宿主、Gork capabilities/hash 与 UI v0.9.22 加载，通知关闭/声音关闭/无活动操作。Windows PowerShell 5.1 无 charset JSON 中文身份解码误报已由该线程改为读取 UTF-8 字节并补 Unicode 回归，D/C 同步，真实原入口 CheckOnly Ready。本线程只读复核正式 5189 已具备 `gork-stage-notifications-v1` / `gork-stage-debug-v1`，Gork 正式 8766 仍 v0.20.27-dev。用户不需再次重开 Astra；仅须正常重开 Gork 加载28并启用来源及所需端点权限。此前自动审批拒绝记录为真实历史，未由本线程绕过或执行停进程。
