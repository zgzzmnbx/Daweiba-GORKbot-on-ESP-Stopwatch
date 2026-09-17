# v0.2.4 电池电量与调试模式实施验收

> 日期：2026-09-17  
> 状态：本地构建和既有数据测试通过；已写入 StopWatch 应用区并读回校验，真机功能待大尾巴验收。

## 实现

- 长按 A+B 约 1 秒打开 `Settings`。设置首页显示电池估算电量、亮度 `−/+`、调试模式 `ON/OFF` 与 `Hardware Check` 入口；硬件检查页保留原 Display、IMU、Touch、Vibration、Last event 与 A/B 诊断操作，可触屏 `Back` 返回设置首页。
- `Battery` 行调用 M5Unified 的 StopWatch/M5PM1 电池电压与电量估算接口，在设置页每 5 秒刷新。电压或电量读数无效时显示 `--`；显示的百分比是电压估算值，不代表可用容量 mAh，也未经过真机电量校准。
- 调试模式默认关闭，触屏开关后写入 NVS 的 `gorkbot/debug`，重启时恢复。开启后，表情画面底部用白色 1 倍 `Font0` 显示当前动画名；关闭后重新绘制头像，不保留文字残影。
- 延续 v0.2.3 亮度调节和 v0.2.2 反应播放完回待机逻辑。亮度与调试模式共用项目设置命名空间，不修改既有出厂备份。

## 本地验证

- `python tools/generate_grok_bot_catalog.py --check`：27 presets、23 sequences，PASS。
- `python -m unittest discover -s tools -p 'test_*.py' -q`：12 项通过。
- PlatformIO Core 6.1.18 / `m5stack-stopwatch`：构建 SUCCESS；RAM 36640 字节，程序 906833 字节。
- `git diff --check -- src/main.cpp src/avatar_engine.cpp src/avatar_engine.h`：未报差异格式错误；现有工作树未提交，保留其他已有修改。
- 固件 `firmware/firmware-v0.2.4-grok-bot-battery-debug.bin`：907200 字节，SHA-256 `CBCE21D83F01890AB649000EA5FE41806A146357C61F46EC122F48B53830EA4A`；ELF/MAP 见 `SHA256SUMS.txt`。

## 写入与读回（2026-09-17 00:49 +08:00）

- 当次枚举 `COM5` 为 `USB\VID_303A&PID_1001`；esptool.py v4.9.0 检出 ESP32-S3 rev v0.2、8 MB PSRAM、16 MB Flash，MAC `28:84:85:44:6C:00`，均与原恢复备份的 `device-info.json` 一致。端口号只代表本次连接。
- 完整 Flash 恢复备份 `04-output/backups/2026-09-16-StopWatch-current-state-v0.1.1/StopWatch-current-fullflash-16MB-20260916.bin` 的 SHA-256 重新核对为 `ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B`。
- 写前对 `0x10000` 的 v0.2.2 镜像执行 `verify_flash`，结果 `verify OK (digest matched)`；v0.2.4 镜像 `image_info` 为有效 ESP32-S3 应用，校验和与镜像哈希均有效。
- 使用 `--chip esp32s3 --port COM5 --baud 460800 --before no_reset --after no_reset write_flash 0x10000` 仅写入 v0.2.4 应用镜像。工具报告实际擦除范围 `0x00010000–0x000edfff`，写入 907200 字节且 `Hash of data verified.`；未执行整片擦除，也未修改 bootloader、分区表或安全配置。
- 随后对同一偏移执行 `verify_flash 0x10000`，结果 `verify OK (digest matched)`；`--after hard_reset` 发出硬复位。未观察屏幕或应用日志，因此不宣称真机运行验收完成。

## 真机门禁

1. 写入、读回和硬复位已完成；请确认设备正常显示头像。若仍停在下载模式，可重新插拔 USB 或按设备电源键使其正常启动。
2. 设置页显示合理电池百分比/电压，或在无有效读数时显示 `--`；USB 充电时百分比可能偏高，不能当作精密剩余容量。
3. 亮度 `−/+` 即时变化且重启后恢复；`Hardware Check` 页和返回按钮正常。
4. 调试开关开启后头像底部出现小白字，切换表情时名称同步变化；关闭后小白字消失，重启后开关状态保持。
5. 验证表情播放完回 `idle`、正常动画帧率及至少一次按键/触摸操作；仅本地编译不满足以上门禁。
