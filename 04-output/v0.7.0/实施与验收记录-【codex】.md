# v0.7.0-P0 纯 BLE 设备音频探针实施与验收

日期：2026-09-21。结论：源码、电脑测试工具、自动测试与固件构建完成；**尚未烧录，未验证真机声音、BLE 吞吐或完整语音交互**。

## 交付

- 固件源码 `03-Src/stopwatch-grok-avatar/src/audio_probe.*`；只在 Settings → Audio test 工作，麦克风需电脑 ARM + 新的本地 A 长按；B/退出/超时/失联停止。保留原表情/气泡、触摸、IMU 和按键入口。
- 独立加密音频 GATT 与定向通知；PCM16 mono、录音 16 kHz、播放输入 16/24 kHz、0.1–10 秒、PSRAM 单缓冲 480,000 bytes、固定 4 包队列。单包信用窗口和有限时长，未实现实时流或多包流水线。
- 电脑 `tools/stopwatch_audio.py` 与双击 `start-ble-audio-test.cmd`：tone、echo、record、play。只用蓝牙/本地文件；不使用电脑录音、不访问独立语音服务、不发云请求，不重启当前 8766 服务。
- 协议、权限、完整命令、错误码和阶段边界见 `00-docs/00-PRD/12-v0.7.0-P0音频探针协议与操作-【codex】.md`。
- 应用镜像：`firmware/firmware-v0.7.0-P0-ble-audio-probe.bin`，1,574,960 bytes，本地保留不入 Git。预期 app0 偏移仍 `0x10000`，未改分区；实际写入前仍需核对设备。

## 本机验证

| 检查 | 结果 / 边界 |
| --- | --- |
| 新增 Python 音频测试 | 16/16 PASS：头部编解码、WAV 格式/截断/上限、完整双向 mock echo、20/244 bytes、错偏移回执、旧 epoch/ID、丢回执、20 次取消后迟到事件、B 停止语义、断连不重播、心跳/新事务串行、队列溢出 |
| Python 合并回归 | 56/56 PASS，含原工作台/表情 BLE/几何/目录 40 项；两条既有 Starlette 依赖弃用警告不影响结果 |
| Node 浏览器逻辑回归 | 5/5 PASS，含 20 次迟到请求与 20 次活动播放器停止；不是本次真人浏览器/麦克风实测 |
| Grok 数据生成检查 | PASS，27 presets / 23 sequences；来源数据未改 |
| PlatformIO 6.1.18 / espressif32 6.12.0 | SUCCESS；RAM 64,056 / 327,680 bytes（19.5%），Flash 1,574,589 / 6,553,600 bytes（24.0%） |
| 生成镜像 | 1,574,960 bytes；由构建工具生成，无额外文件 SHA 计算 |
| Git diff 检查 | 无空白错误；既有 kirby 设计资产和快捷方式不纳入本次提交 |

证据：同目录 `自动测试记录-【codex】.txt`、`浏览器逻辑回归-【codex】.txt`、`构建记录-【codex】.txt`。模拟测试用的是假 BLE 设备，不能证明 C++ 运行期、真实加密/配对、ADC/DAC、传输速率或音质；mock 输出速率不是硬件数据。

构建使用现有隔离 Python/PlatformIO，临时 `P:` 映射正式源码、`Q:` 映射已有 Core；这些盘符没有写进源码/config。主要命令：

```powershell
$env:PLATFORMIO_CORE_DIR='Q:\'
& 'Codex-Temp/.venv-platformio/Scripts/python.exe' tools/platformio_safe.py run -d P:\ -e m5stack-stopwatch
& 'Codex-Temp/.venv-companion/Scripts/python.exe' -m pytest '03-Src/stopwatch-voice-companion/tests' tools/test_ble_expression_console.py tools/test_grok_bot_catalog.py tools/test_grok_geometry.py tools/test_stopwatch_audio.py -q
node --test '03-Src/stopwatch-voice-companion/tests/test_browser.mjs'
```

## 未完成与下一阶段

- G1 等当次烧录许可。未打开串口、未写 Flash、未改 eFuse/NVS/配对；设备仍为之前的 v0.5.0。保留既有完整备份，不重复读取整片、不计算例行哈希。
- P1 必须真机低音量 tone、短 echo、录音电平、采样连续性、过短/10 秒上限、A/B/退出、录放切换与截尾听验。PLAYING 表示驱动接受队列，不证明已出声；结束事件含 100 ms DMA 排空余量仍须听验。
- P2 必须实际 BLE 双向吞吐/丢包、20 次取消、20 bytes 回退、陌生端通知负测、PSRAM 与设备状态观测。当前单包窗口可能慢；单方向 180 秒超时显式失败，不静默截音。
- P3 未实施：8766 设备音频模式、8765 的 ASR/TTS 接入、语音会话租约与上传许可、实际播放状态联动、可调音量、打断重录。既有 8766 页面仍使用电脑收音和播放。
- P4 未验收：原表情/气泡实屏、输入、FPS、功耗与长时间稳定性。

README、项目 AGENTS、PRD/当前计划和 CHANGELOG 已同步开发版/设备版边界。按项目版本规则仅作本地 Git 阶段存档，不推送 GitHub，不写 Obsidian或改其他仓库。
