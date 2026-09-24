# v0.8.0 Gork 机器人控制台实施与验收记录

> 2026-09-21；开发交付状态：M0–M4 已实现，M5 本机回归与目录包已完成。设备应用区已写入 v0.8.0-dev 并通过独立读回校验；声音、UI、BLE 和稳定性真机验收仍待执行。

## 1. 已交付实现

- `03-Src/gork-desktop/`：Electron 44.4.3 单实例主窗口、托盘、透明五状态桌面角色、共享后端状态、窗口位置恢复、停止全部、最小 preload 和麦克风/导航权限边界。
- `03-Src/stopwatch-voice-companion/`：现有跟读链路升级为统一控制台；可复用外部语音服务或启动明确配置的自有实例，只停止自己启动的进程。
- 可选 OpenAI-compatible 文字回答适配器：凭据仅取独立环境变量；第三项上传许可默认关闭；上下文仅存内存且最多 10 轮，本版默认 4 轮；停止会取消在途回答。未配置时 AI 对话入口禁用。
- `01-assets/audio/`：6 个确定性原创 CC0 提示音，16 kHz/PCM16/单声道，总 PCM 59,264 bytes；manifest 和生成脚本可复现。
- 固件源码：独立加密声音服务、9-byte 帧、request_id 生命周期回执、8 条终态去重、定向通知、BUSY/未知 ID/越界拒绝；Settings 增加 Sound 音量、静音、试听、停止和延迟 NVS 提交。
- 统一 BLE：一条 BleakClient 管理表情、气泡、声音与旧音频协议；延迟模式支持电脑文字→设备、设备录音→电脑、设备录音→识别/可选回答/合成→设备。
- 延迟任务展示真实阶段、累计有效字节、总字节、百分比、耗时与速率；取消不续传、不补播，录音结果下载一次后从后端内存释放。

## 2. 构建与自动验证

| 范围 | 结果 | 边界 |
| --- | --- | --- |
| Python/协议/几何/音频 | 70 PASS | Mock 与静态协议验证，不代替 BLE/音频真机 |
| 浏览器取消与 PCM | 5 PASS | 覆盖 20 次迟到 TTS 和 20 次活动播放器停止 |
| Electron 管理器/窗口 | 5 PASS | 后端身份、自有/外部进程、Windows 启动器 PID、可见区域恢复 |
| Electron 源码烟测 | PASS | `GORK_DESKTOP_READY backend=external`；复用既有后端 |
| Windows x64 目录包烟测 | PASS | 自带后端启动后退出，8877 探针确认后端已停止 |
| 真实浏览器渲染 | PASS | 1180×820 截图；回答禁用、设备离线和会话占用提示可见 |
| PlatformIO 固件构建 | PASS | RAM 64,336/327,680（19.6%）；Flash 1,638,225/6,553,600（25.0%） |
| npm audit | PASS | 52 包，0 个已知漏洞；Electron 44.4.3、@electron/packager 20.3.0 固定 |

测试命令：

```powershell
$env:PYTHONPATH='03-Src/stopwatch-voice-companion'
& 'Codex-Temp/.venv-companion/Scripts/python.exe' -m pytest '03-Src/stopwatch-voice-companion/tests' tools/test_ble_expression_console.py tools/test_grok_bot_catalog.py tools/test_grok_geometry.py tools/test_stopwatch_audio.py tools/test_stopwatch_sound.py -q
node --test '03-Src/stopwatch-voice-companion/tests/test_browser.mjs'
npm test --prefix '03-Src/gork-desktop'
```

浏览器证据：`控制台浏览器渲染-v0.8.0-【codex】.png`。它只证明页面真实渲染，不证明麦克风、托盘、设备或听感。

## 3. A1–A10 验收矩阵

| 项目 | 状态 | 已有证据与剩余门禁 |
| --- | --- | --- |
| A1 单入口/托盘/角色/控制台 | PARTIAL | 源码与目录包真实启动通过；托盘点击、关闭收起、重复启动、多窗口仍需人工完整走查 |
| A2 视觉与角色 | PARTIAL | 浏览器截图和 5 状态桌面角色已实现；拖动/缩放/隐藏/多屏恢复需人工验证；桌面角色仍是程序化 Grok 风格，不等于 Grok bot 全时间轴迁移 |
| A3 电脑语音 | PARTIAL | 既有本地服务在线，跟读链路自动测试通过；本轮未采集真人麦克风、未听 TTS、未配置或调用真实回答服务 |
| A4 服务托管 | PASS（模拟/本机进程） | 外部复用、自有启动、错误路径和只停自有实例均覆盖；独立语音项目的未安装/模型缺失提示仍需目标机验证 |
| A5 设备声音库 | PARTIAL（v0.8.4 真机） | v0.8.4 完整 ES8311 初始化写入后，本地 Sound/Test 已真实出声；控制台遥控和六种声音逐项听验仍未运行 |
| A6 音量/停止 | PARTIAL（真机） | 100% 音量可听但用户确认偏小；0 静音、分档变化、重启保持、B/遥控停止时延仍需实际验证 |
| A7 延迟模式 | PARTIAL | 三路径及真实进度/取消已实现并模拟测试；同一 Windows BLE 三服务发现、三条真机路径和取消后无迟播未测 |
| A8 安全/权限 | PARTIAL | 三类上传许可独立、默认关闭；BLE 命令保持绑定/加密/定向通知；陌生端声音/音频负测未运行 |
| A9 回归 | PARTIAL | 80 项自动测试与固件构建通过；旧表情/气泡/happy-work、设备 Settings/Audio/Sound 实屏未回归 |
| A10 稳定性 | NOT RUN | 30 分钟待机、10 次断连重连、各阶段 20 次取消和资源曲线未运行 |

## 4. 交付与启动

- 根目录开发入口：`start-gork-console.cmd`。
- Windows x64 本机目录包：`Gork-Robot-Console-v0.8.0-win32-x64/Gork-Robot-Console-v0.8.0.exe`。
- 已写入的应用镜像：`firmware/firmware-v0.8.0-dev-gork-sound.bin`（1,638,592 bytes）。写入前确认 COM5、ESP32-S3、16 MB Flash、MAC 尾号 `6C:00` 与 app0 `0x10000`/6400 KiB；工具写入校验及独立 `verify_flash` 均通过并硬复位。未改分区、NVS、bootloader 或 eFuse，未整片擦除。
- 目录包约 401 MiB，包含 Electron 与本机 companion Python venv；不包含独立语音引擎、模型、回答服务或密钥，不承诺换一台电脑即可运行。
- 网页回退入口仍为 `start-voice-companion.cmd`；旧音频 CLI 保留但与统一控制台互斥连接设备。

## 5. 权限与未执行项

本轮已按大尾巴当次“烧录”授权连接 StopWatch，并仅写入 v0.8.0-dev 应用区；未调用云端 ASR/TTS/回答服务，没有读取或复制 Key，没有 GitHub 推送。下一步需进行设备听感、UI/BLE、安全和稳定性真机验收；写入和读回通过不能代替这些结论。

2026-09-22 追记：v0.8.0 的 A5 真机检查已确认本地与遥控均无声；v0.8.1 冷启动修复、v0.8.2 M5IOE1 分层诊断及 v0.8.3 双 PA 门控写入后仍失败。v0.8.4 完整复现官方 ES8311 初始化后，本地 Sound/Test 已真实出声，确认 codec 初始化不完整是根因；但 100% 音量仍偏小，控制台六种声音与完整音量/停止门禁未完成。过程见 `../v0.8.1/声音冷启动修复与验收-【codex】.md`、`../v0.8.2/扬声器供电修复与验收-【codex】.md`、`../v0.8.3/GPIO14功放门控修复与待验收-【codex】.md` 和 `../v0.8.4/ES8311官方初始化修复与待验收-【codex】.md`。
