# v0.5.0 应用区烧录与读回记录

> 日期：2026-09-17；当次指令：“执行烧录”。

## 写前识别

- 当前枚举：`COM5 = USB\VID_303A&PID_1001&MI_00`；COM3/COM4 为蓝牙串口。
- esptool 4.9.0 `flash_id`：ESP32-S3 QFN56 revision v0.2，USB-Serial/JTAG，MAC `28:84:85:44:6c:00`，8 MB PSRAM，Flash manufacturer `20` / device `4018`，16 MB。
- `image_info`：v0.5.0 应用镜像 1,545,040 字节、5 segments、镜像校验有效。
- 已有 v0.3.0 正式应用镜像和首次完整 Flash 备份可用于回退；本轮未整片读取或重复计算 SHA-256。

## 写入与校验

从项目根目录以既有隔离 Python 与 esptool 执行（`<esptool.py>` 为 `Codex-Temp/pio-home-20260916/packages/tool-esptoolpy/esptool.py`）：

```text
python <esptool.py> --chip esp32s3 --port COM5 --baud 460800 --before default_reset --after hard_reset write_flash --verify 0x10000 04-output/v0.5.0/firmware/firmware-v0.5.0-ble-chat-bubble.bin
python <esptool.py> --chip esp32s3 --port COM5 --baud 460800 --before default_reset --after hard_reset verify_flash 0x10000 04-output/v0.5.0/firmware/firmware-v0.5.0-ble-chat-bubble.bin
```

- 写入：esptool 报告覆盖扇区擦除 `0x00010000–0x00189fff`，写入 1,545,040 字节，`Hash of data verified`，退出码 0。
- 独立读回：`verify OK (digest matched)`，退出码 0；结束后 hard reset。
- 未写 bootloader、分区表、NVS、eFuse，未执行整片擦除；电脑蓝牙配对未改。

## 验收边界

写入与读回成功只证明应用区字节匹配，不证明应用成功启动或聊天气泡显示正确。实屏、中文、BLE `:say`/`:clear`、自动清除、`happy-work`、帧率和安全负向测试仍待真机验收。
