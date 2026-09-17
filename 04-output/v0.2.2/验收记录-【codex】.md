# v0.2.2 反应播放完返回待机：写入与验收记录

> 日期：2026-09-17  
> 状态：本机构建、写入和设备读回校验通过；运行时自动返回 `idle` 尚待设备退出下载模式后验证。

## 需求与实现

- 大尾巴确认：反应动画播放完应自动返回待机。
- 修复 v0.2.1 生成器把全部 23 条序列都标成 `persistent=true` 的问题：v0.2.2 仅 `idle` 默认持续，其余 22 条默认播放一遍后回 `idle`。
- 串口显式 `loop <名称>` / `pingpong <名称>` 保留持续播放；`once <名称>` 播完也应回 `idle`。
- 未修改 Grok bot 来源数据、几何、渲染器、硬件驱动、bootloader 或分区表。

## 本地验证

- `python tools/generate_grok_bot_catalog.py --check`：27 presets、23 sequences，PASS。
- `python -m unittest discover -s tools -p 'test_*.py' -q`：12 项通过；新增测试先对 v0.2.1 行为失败，修复后通过。
- PlatformIO Core 6.1.18 / `m5stack-stopwatch` 构建：SUCCESS；RAM 36200 字节，程序 889985 字节。
- 应用镜像：`firmware/firmware-v0.2.2-grok-bot-auto-idle.bin`，890352 字节，SHA-256 `5B715113EACE45F0201534EA7B139F5B245017236BAC17AF47D597342AA72C9A`；ELF/MAP 校验见 `SHA256SUMS.txt`。

## 写前检查与写入

- 当次设备枚举：`COM5`，USB VID/PID `303A:1001`，USB 标识/MAC `28:84:85:44:6C:00`；esptool 识别 ESP32-S3 rev v0.2、16 MB Flash、8 MB PSRAM。
- 首次烧录前的完整 Flash 备份仍在 `04-output/backups/2026-09-16-StopWatch-current-state-v0.1.1/`，SHA-256 `ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B`，本次写入前重新核对一致。
- 写前 `verify_flash 0x10000 firmware-v0.2.1-grok-bot.bin`：`verify OK (digest matched)`，证明目标设备上仍是已归档的 v0.2.1 应用。
- 用户已将设备手动置于下载模式。使用 esptool.py v4.9.0，仅写入 `0x10000` 应用区；实际擦除范围 `0x00010000–0x000e9fff`，写入 890352 字节，工具报告 `Hash of data verified.`。
- 写后 `verify_flash 0x10000 firmware-v0.2.2-grok-bot-auto-idle.bin`：`verify OK (digest matched)`。未执行整片擦除、未改 bootloader/分区表/eFuse/安全启动/Flash 加密。

## 运行时验收边界

- 首次串口烟测发送 `happy` 后未收到应用日志；随后 `--before no_reset flash_id` 仍能直接连接 ROM 下载器，说明设备还停在下载模式。不能把本次无日志解读为动画功能失败。
- 已请求大尾巴复位或重新插拔 USB。设备正常启动后需验证：`happy` 入口被接受，约 11.2 秒时间轴结束后出现 `Return to base: IDLE`；`loop happy` 保持循环，不自动返回，随后发送 `idle` 能恢复待机。
- 当前结论仅为固件已构建、已写入、已读回校验；屏幕运行、自动返回、触摸/按键/IMU/振动及长时间稳定性仍待实机确认。
