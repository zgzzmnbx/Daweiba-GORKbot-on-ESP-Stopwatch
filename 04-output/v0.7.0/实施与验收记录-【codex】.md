# v0.7.0-P0 纯 BLE 设备音频探针实施与验收

日期：2026-09-21。结论：源码、电脑测试工具、自动测试与固件构建完成；**当次授权后应用区写入与独立读回通过，未验证真机声音、BLE 吞吐或完整语音交互**。

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

## 当次烧录与读回（2026-09-21）

- 授权：大尾巴明确回复“烧录测试版”。当次重新枚举 COM5 为 VID/PID 303A:1001，esptool 4.9.0 确认目标 MAC 与既有备份设备一致、ESP32-S3 QFN56 rev0.2、8 MB PSRAM、16 MB Flash。详细设备标识见本地烧录日志，不公开完整 Flash。
- 既有两个完整备份文件均在，每个 16,777,216 bytes；本轮没有重复全片读取或例行文件哈希验证。读取设备 `0x8000` 的 4096 bytes 分区表确认 app0=`0x10000`、容量=`0x640000`，新应用镜像可容纳。
- 执行 `esptool.py --chip esp32s3 --port COM5 --baud 460800 --before default_reset --after hard_reset write_flash --verify 0x10000 04-output/v0.7.0/firmware/firmware-v0.7.0-P0-ble-audio-probe.bin`；写入 1,574,960 bytes，工具报告覆盖扇区 `0x00010000–0x00190fff` 并通过内建写入校验。
- 随后同参数独立执行 `verify_flash 0x10000`，返回 `verify OK (digest matched)`，并硬复位；这是工具自身设备校验，不是额外文件 SHA-256 验证。
- 未执行整片擦除、bootloader/分区表/NVS 写入、eFuse 修改或蓝牙重配。仅应用区替换为测试版，现有 v0.5.0 应用可由本地归档恢复（恢复仍需授权）。
- 写后只读 BLE 扫描 5 秒，发现 0 个 GorkBot 广播；不能据此判断启动失败或音频不可用，也不能声称启动/BLE 已验收。请正常开机确认 BLE ON，在 Settings → Audio test 保持页面后测试。没有打开可能改变启动状态的串口监视器。
- 本地证据：`烧录记录-20260921-【codex】.txt`、`读回校验-20260921-【codex】.txt`；这些包含设备标识，本轮不提交或推送。

## 未完成与下一阶段

- G1 已完成：当次授权、应用区写入与独立读回通过；设备运行效果仍未知。保留既有完整备份，不重复读取整片、不计算例行哈希。
- P1 必须真机低音量 tone、短 echo、录音电平、采样连续性、过短/10 秒上限、A/B/退出、录放切换与截尾听验。PLAYING 表示驱动接受队列，不证明已出声；结束事件含 100 ms DMA 排空余量仍须听验。
- P2 必须实际 BLE 双向吞吐/丢包、20 次取消、20 bytes 回退、陌生端通知负测、PSRAM 与设备状态观测。当前单包窗口可能慢；单方向 180 秒超时显式失败，不静默截音。
- P3 未实施：8766 设备音频模式、8765 的 ASR/TTS 接入、语音会话租约与上传许可、实际播放状态联动、可调音量、打断重录。既有 8766 页面仍使用电脑收音和播放。
- P4 未验收：原表情/气泡实屏、输入、FPS、功耗与长时间稳定性。

README、项目 AGENTS、PRD/当前计划和 CHANGELOG 已同步开发版/设备版边界。按项目版本规则仅作本地 Git 阶段存档，不推送 GitHub，不写 Obsidian或改其他仓库。
