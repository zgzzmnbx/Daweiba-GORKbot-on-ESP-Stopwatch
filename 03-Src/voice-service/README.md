# Gork 项目内语音服务

集成版本：Gork v0.11.0-dev；HTTP 服务版本：0.3.2；协议：v1。

## 启动与目录

从 StopWatch 根目录 `start-gork-console.cmd` 启动控制台即可。宿主默认调用本目录 `tools/serve_managed.py`，退出时通过 stdin EOF 关闭自有服务及模型进程。

- 服务代码：`03-Src/voice_service/`，保持 FastAPI HTTP 接口和独立测试。
- 配置模板：`03-Src/config/voice.example.toml`，模型目录相对 StopWatch 根目录解析。
- 环境：主项目 `Codex-Temp/voice-runtime/.venv/`，本机 Python 3.14；Python 系统安装仍为基础运行时，不依赖另一个项目。
- 模型：主项目 `Codex-Temp/voice-runtime/models/sensevoice/`、`models/kokoro/`。
- 依赖锁：`03-Src/requirements.lock.txt`。重建时用系统 Python 建立环境，再通过新环境 `python -m pip install -r` 安装锁定依赖。
- 模型与运行环境仅本机保留，由主项目 Codex-Temp 忽略；Git 中不包含模型、私人音频、凭据或虚拟环境。

云端使用已有专用环境变量 `ZHISUAN_VOICE_DASHSCOPE_API_KEY`，托管入口可读取 Windows 用户环境的这一指定变量；不把 Key 写入项目文件。宿主默认显式指定本模块配置，避免误用继承的旧 `VOICE_CONFIG`。

## 验证

在 StopWatch 根目录，用 `Codex-Temp/voice-runtime/.venv/Scripts/python.exe -m pytest 03-Src/voice-service/03-Src/tests -q` 运行服务测试。`tools/check_voice_autostart.py` 默认检查本模块的加载与退出，不再要求外部语音项目路径。

迁入源码测试 46 项通过；新环境依赖检查无冲突。真实本地 TTS → ASR 闭环通过，云请求为零。完整记录见主项目 `04-output/v0.11.0/迁移与验收记录-【codex】.md`。

## 来源与边界

2026-09-23 按用户明确授权导入原“260921-【语音】语音智能体模块”的当前工作树（原 Git HEAD 8697308，包含当时未提交的 0.3.2 更新，不将 HEAD 等同于导入内容）。原目录只读保留，不合并 Git 历史。只迁入服务代码、配置模板、测试、依赖锁及托管入口，模型和依赖副本存于主项目忽略目录。

语音 API 保持可独立复用，无 BLE/机器人渲染依赖；仍为单活会话。上传许可默认关闭，由客户端会话明确应用；云端计费调用、真人麦克风/音质和设备联动没有在迁移测试中执行。
