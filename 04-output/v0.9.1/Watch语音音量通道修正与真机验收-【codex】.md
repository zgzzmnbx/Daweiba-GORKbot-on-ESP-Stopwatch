# Watch 固件 v0.9.1-dev：语音音量通道修正与真机验收

日期：2026-09-26。按用户当次授权，仅向当前 Watch 的 app0 写入 v0.9.1-dev；写入及独立校验通过。用户确认设置页显示 v0.9.1-dev，且小人页朗读“响度够用，声音清楚”。

## 原因与改动

- v0.9.0 音频播放固定使用 `startStopWatchSpeaker(192)` 与 ES8311 `Unity` 档位，忽略 StopWatch 页的 90% 音量。六种内置短音则使用已保存的音量值与 `BuiltInLoud` 档位（相对约 +9.5 dB）。
- v0.14.2 运行后端已经将同一句合成语音增强 `+7.8 dB` 并通过 Opus 播放，但用户仍反馈偏小，说明电脑端提高数字电平没有消除设备播放档位差异。
- v0.9.1 将 PCM/Opus 播放、录音回放统一接入现有的音量值和 `BuiltInLoud` 档位；BLE 协议、Opus 编解码、音频传输与内置短音代码均不变。设置页版本文字改为 `v0.9.1-dev`。

## 本机验证

- `tools/test_stopwatch_audio.py` 与 `tools/test_stopwatch_sound.py`：合计 33 项通过；声音相关 10 项检查语音与内置短音使用同一个已保存的音量值，并保留 GPIO14 功放关断条件。
- PlatformIO `m5stack-stopwatch` 短路径构建成功：静态 RAM 63,960 / 327,680（19.5%），Flash 1,715,553 / 6,553,600（26.2%）。镜像 `firmware/StopWatch-Gork-v0.9.1-dev-app.bin`，1,715,920 字节；其中能检出 `v0.9.1-dev` 版本文字。
- 首次长路径构建因本机 Xtensa `CreateProcess` 问题失败；临时映射短路径后构建成功，已解除映射。

## 写入与验证

- 当次重新枚举 USB `COM5`（VID/PID `303A:1001`），esptool 识别为 ESP32-S3 rev 0.2、MAC `28:84:85:44:6c:00`、16 MB Flash。重新读取 `0x8000` 处 4096 字节分区表并解析：app0 `0x10000`、6400 KiB；app1 `0x650000`。镜像 1,715,920 字节处于 app0 容量内。
- esptool 仅执行 `write_flash 0x10000 firmware/StopWatch-Gork-v0.9.1-dev-app.bin`，实际覆盖扇区 `0x10000–0x1b2fff`。工具返回 `Hash of data verified`，独立 `verify_flash 0x10000` 返回 `verify OK (digest matched)`；没有整片擦除，也未写入分区表、NVS 或 app1。
- 写后 COM5 仍重新枚举；用户从 Watch 设置页实屏确认 `v0.9.1-dev`。Gork 运行后端为 `0.14.3-dev`，加密 BLE 自动恢复为 `connected=true`。其后正式 Watch 语音任务走 Opus，设备报告 `played`，Opus 10,991 字节、原始 PCM 119,040 字节、任务耗时约 5.58 秒、电脑端增益 `+4.2 dB`；用户确认实际响度够用、声音清楚。此项可以作为本次朗读响度真机通过，`played` 本身仍不是可闻证据。

## 尚待分项验收

本次用户确认了一次小人页朗读的实际响度和清晰度；设备音量具体百分比未独立读回，不能记录为固定音量阈值。内置短音、停止/取消、多个音量档位、底噪、异常发热和长稳未逐项复测。90% 在新固件下可能明显更响，后续仍从低档逐级调节。
