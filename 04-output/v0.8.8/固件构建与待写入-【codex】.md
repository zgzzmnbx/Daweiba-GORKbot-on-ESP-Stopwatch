# StopWatch v0.8.8-dev 应用区写入与真机验证

应用镜像：`firmware/StopWatch-Gork-v0.8.8-dev-app.bin`（1,626,688 字节）。PlatformIO 构建成功。2026-09-24 按大尾巴当次授权，仅写入当前 Watch 的 app0 应用区。

- 写前重新枚举到 USB COM5、ESP32-S3 MAC `28:84:85:44:6c:00`，与既有恢复记录匹配；当次读取分区表确认 app0 偏移 `0x10000`、大小 6400 KiB，镜像可放入。16 MB Flash，未更改分区表。
- `esptool write_flash 0x10000` 写入 1,626,688 字节，覆盖应用镜像所在扇区 `0x10000–0x19dfff`；写入工具报告 `Hash of data verified`。独立执行 `verify_flash 0x10000` 返回 `verify OK (digest matched)`，之后硬复位。未整片擦除，未写 bootloader、NVS 或其他分区。
- 手表正常显示，Bluetooth 显示 ON / CONNECTED / SAVED；电脑端重新发现加密 GATT 的表情和音频服务，正式 Gork v0.12.9-dev 恢复连接。普通小人页 64,000 字节测试音频已收到 `played`，三包窗口、244 字节包，发送约 12.5 秒、含设备播放约 14.2 秒。此样本取自长语音的前 2 秒，末尾必然缺字，不能用其听感判断音频完整性。
- 完整短句“你好，测试完成。”本地 TTS 生成约 1.87 秒、约 89.6 KB PCM；普通小人页两次传输均约 17.5 秒，含播放回执约 18.5 秒，`stage=played`、错误为空。用户确认第二次完整清楚。

该版在普通小人页启用 BLE 音频播放，录音仍限 Audio test。代码、自动测试、速度对照和剩余真机门禁见 `04-output/v0.12.9/实施与验收记录-【codex】.md`。
