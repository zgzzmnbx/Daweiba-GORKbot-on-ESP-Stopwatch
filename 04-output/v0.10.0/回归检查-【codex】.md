# v0.10.0-dev 控制台回归检查

日期：2026-09-23。范围：电脑端单页工作台源码的离线自动回归；未启动正式 Electron 或后端服务，未连接 StopWatch，未发起云请求。

## 自动检查

| 检查 | 命令与范围 | 结果 |
| --- | --- | --- |
| 浏览器逻辑与音频客户端 | 在 `03-Src/stopwatch-voice-companion/` 执行 `node --test tests/test_browser.mjs tests/test_audio_client.mjs` | 21/21 通过 |
| Python 项目及工具 | 在项目根目录执行 `python -m pytest 03-Src/stopwatch-voice-companion/tests tools/test_stopwatch_sound.py tools/test_stopwatch_audio.py tools/test_grok_geometry.py tools/test_grok_bot_catalog.py tools/test_ble_expression_console.py -q` | 83/83 通过 |
| 桌面壳 | 在 `03-Src/gork-desktop/` 执行 `npm test` | 9/9 通过 |

浏览器夹具现能检查四个标签实际显隐、单个常驻正式头像挂载、消息区输入与回答分离、默认本地 ASR/云端 TTS、已保存本地偏好、三项独立许可、许可撤销先停止再应用、自动朗读关闭、普通路由草稿不中断已应用路径、重复录音与重复连接、迟到 TTS 不播放。桌面单元测试检查可见性 IPC 只接受控制台发送方和布尔值，并验证 preload 桥接。既有 20 次停止及播放结束迟到回调测试保留。

旧浏览器测试预期默认本地音色，已显式设置 `gork.tts=local`，使其继续检查保存偏好；新默认云端由单独用例验证。直接 `unittest discover` 不适用于这组 pytest 函数，且不会执行 `conftest.py` 的工具路径设置；上述 83 项以 pytest 作为完整范围。

## 仍需实测

正式 Electron 窗口、多屏与托盘；真实麦克风、扬声器、独立语音服务与云端路径；StopWatch 的 BLE、设备声音和延迟音频；窄屏滚动、实际动画观感、键盘与屏幕阅读器体验。这些项目不能由虚拟 DOM 或离线单元测试判定通过。
