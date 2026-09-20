# StopWatch 电脑语音工作台 v0.6.0

电脑麦克风 → 独立语音服务 ASR → 可编辑文字 → TTS 完整 WAV → 电脑扬声器；现有 v0.5.0 StopWatch 通过加密 BLE 同步表情和短气泡。这是跟读测试，不是 AI 对话。设备离线不阻断电脑语音。

## 启动

1. 先按独立语音项目的说明启动服务，默认 `http://127.0.0.1:8765`。本程序不启动/停止那个服务，不读取它的模型、虚拟环境或 Key。
2. 在本项目根目录双击 `start-voice-companion.cmd`，默认浏览器打开 `http://127.0.0.1:8766`。首次启动需要 Python 3.11+ 与联网安装依赖；本机已用独立 Python 3.14 环境安装。关闭终端或 Ctrl+C 仅结束工作台。
3. 点击“连接会话”。如果已有会话占用，不会自动抢占；确认可以结束对方会话时才点击“接管已有会话”。每次连接重置为本地 ASR / 本地 TTS，两个上传许可均关闭。
4. 点击“开始录音”，由你确认浏览器的麦克风权限；说话后点“结束并转写”，最长 30 秒自动结束。浏览器实际采集数据会转换成 PCM16、单声道、16 kHz WAV，不是重命名 WebM。
5. 检查/编辑文字后点“回读文字”，也可以直接输入文字。单次回读最多 300 个 Unicode 字符，超限会提示，不默默截断。完整转写保留在文本框；设备气泡仅发前 23 字加省略号（最多 24 BMP 字符 / 72 UTF-8 字节），过滤 emoji 和控制字符。
6. 点击“停止”立即停止本地麦克风/播放器，再异步取消服务请求；停止或失败不代表云端不计费。

### 蓝牙联动

- StopWatch 正常运行 v0.5.0；在本地 Bluetooth 设置中打开 BLE，首次连接打开 Pair 窗口，随后退出设置页。
- 关闭旧蓝牙控制台，避免多个程序争抢连接。工作台先“扫描设备”，选择当次发现的 `GorkBot-SW`，再“连接”；不硬编码历史 MAC。
- 录音：`loop listening`；处理：`loop thinking`；电脑实际开始播放：`loop happy`；播放结束/停止：`idle` + 清气泡；错误：`confused`。
- 短气泡显示转写或回读文本预览，最多约 10 秒（设备现有固件行为）。不做逐音素嘴型。
- 后端一个串行 BLE 写入者，文字事务不可插入其他包；每包只认匹配回执，不再读取旧状态当成功。未知写入/回执超时断开连接以隔离迟到回执。
- 每次手动连接后自动重连最多 2 次；只恢复最新状态，不重放旧气泡或语音。失败后按页面提示重新扫描/连接。菜单打开会拒绝控制并提示 `ERR:BUSY`。
- 现有表情和清屏协议没有请求编号，同一连接内的重复同名迟到通知不能做到严格逐请求证明；本版通过串行、清空已排队通知、超时断开和连接代号隔离降低风险，没有冒充协议升级。

### 选路和上传许可

建议体验路径是本地 ASR + 云端 TTS，但需要你勾选“允许上传回读文字”并应用。允许文字不等于允许录音上传。许可在当前会话内生效，重新连接后归零；配置有 Key 不会自动开启上传。

切换选项会立即停止当前操作；新路径必须点“应用设置”。取消任一上传勾选会立即停止并向服务撤销该项许可，对应路径退回本地。已有云请求可能只作废结果，不能承诺撤销账单。云端账号/Key 只在独立语音服务配置，不放在本仓库。

## 配置与依赖

将 `config.example.toml` 复制为被 Git 忽略的 `config.local.toml` 后修改：工作台端口、独立语音服务地址、设备预选地址、请求超时。服务地址只允许本机 HTTP；设备地址仅用于本次扫描列表预选，不自动连接。不要填凭据。

`requirements.txt` 锁定直接依赖；`requirements-lock.txt` 记录本机 Windows/Python 3.14 的完整安装集合。启动器使用独立的 `Codex-Temp/.venv-companion`，不复用 PlatformIO 或语音引擎环境。工作台只监听 127.0.0.1，验证 Host/Origin，不放开跨源权限。多个浏览器标签使用独立内存控制标识；语音服务 session_id 不发给网页，不写 URL 或日志。

启动器先独占绑定端口；若已有同一项目工作台，核对接口应用标识、项目实例和 PID 后打开既有页面；若端口被其他程序占用则报错退出，不按端口杀进程。无自动退出其他 Python 服务的代码。

## 生命周期

同一轮 ASR 与编辑后的 TTS 使用相同服务 turn，不同 request_id；每次操作另有递增 generation。新录音或换路创建新 turn。旧 generation 的 HTTP 完成、播放器回调和未发 BLE 状态都被丢弃；已经写进设备的包无法撤回，随后最新 idle/清屏会覆盖。

前台每秒检查会话，服务检查超时 3 秒、浏览器检查上限 4 秒。会话被接管或断开后停止本地播放，不自动抢回。关闭页面尽力释放会话；如果浏览器崩溃未能释放，下次由用户明确接管。

## 验证

在项目根目录运行：

```powershell
& 'Codex-Temp/.venv-companion/Scripts/python.exe' -m pytest '03-Src/stopwatch-voice-companion/tests' -q
node --test '03-Src/stopwatch-voice-companion/tests/test_browser.mjs'
& 'Codex-Temp/.venv-companion/Scripts/python.exe' 'tools/test_ble_expression_console.py'
& 'Codex-Temp/.venv-companion/Scripts/python.exe' 'tools/test_grok_bot_catalog.py'
& 'Codex-Temp/.venv-companion/Scripts/python.exe' 'tools/test_grok_geometry.py'
```

可选本地服务联测（先退出工作台会话，不会抢占）：

```powershell
& 'Codex-Temp/.venv-companion/Scripts/python.exe' -X utf8 '03-Src/stopwatch-voice-companion/tests/live_smoke.py'
```

该脚本用本地 TTS 生成测试 WAV 后送入本地 ASR，不开启麦克风、不上传云端、不存原始音频，不能代替真人录音与听感验收。完整结果与未测项见项目 `04-output/v0.6.0/实施与验收记录-【codex】.md`。
