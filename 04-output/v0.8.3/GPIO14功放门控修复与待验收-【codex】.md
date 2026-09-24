# v0.8.3-dev GPIO14 功放门控修复与待验收记录

> 2026-09-22。候选固件已完成源码修改、自动回归和 PlatformIO 构建，并按大尾巴当次“烧录”授权仅写入设备应用区；工具写入校验和独立读回校验通过。后续人工听验仍显示 `playing` 且无声，GPIO14 不是充分根因。

## 1. 新的真机证据

- v0.8.2 本地 `Settings → Sound → Test` 显示 `playing`，但仍听不到声音。
- 这说明 M5Unified 扬声器驱动启动成功，M5IOE1 G3 codec 电源与 G10 功放锁存均为高，ES8311 可通过 I2C 读取且 `0x00=0x80`，PCM 也已成功入队；`playing` 仍不是实际可闻证据。
- 因此，v0.8.2 的“双 M5IOE1 实例竞争”不是充分修复，故障继续收敛到 codec 输出、功放额外门控或扬声器物理链路。

## 2. 官方实现差异与候选根因

- 复核 M5Stack 官方 `M5StopWatch-UserDemo` 提交 `6b4aa125288b6fe9dca661f10159f6e1e5ee785c` 的 `main/hal/hal_ioe.cpp`：官方初始化并同时控制两路扬声器功放使能——M5IOE1 G10 与 ESP32 GPIO14。
- 当前锁定的 M5Unified StopWatch 回调只控制 G3 与 G10，没有拉高 GPIO14。结合本机 v0.8.2 `playing` 仍无声，缺失 GPIO14 是新的高置信候选根因；烧录听验前不称为已确认根因。

## 3. v0.8.3 候选修复

- 播放前将 ESP32 GPIO14 配置为输出并保持低电平；M5Unified 完成 codec/G10 初始化且分层读回通过后，再拉高 GPIO14并等待 10 ms。
- GPIO14 方向、写入或读回失败时显示 `GPIO14 PA failed`，不进入 `playing`。
- 所有本地声音、BLE 内置声音、长 PCM、录音切换和启动关断路径统一调用扬声器停止函数，先拉低 GPIO14，再停止 M5Unified 扬声器，避免功放残留开启。

## 4. 自动验证与构建

| 范围 | 结果 | 边界 |
| --- | --- | --- |
| Python 回归 | 73 PASS | 包含 GPIO14 双门控及统一关断静态门禁；不代表真机出声 |
| 浏览器测试 | 5 PASS | 电脑端音频/取消逻辑 |
| Electron 测试 | 5 PASS | 桌面进程与窗口逻辑 |
| PlatformIO 构建 | PASS | RAM 63,928/327,680（19.5%）；Flash 1,625,005/6,553,600（24.8%） |

应用镜像：`firmware/firmware-v0.8.3-dev-gpio14-pa-enable.bin`，1,625,376 bytes，SHA-256 `CC13B0112D128EBB1E088262A21B989B4D5ED511D9FB2AE4E29B8CADDAAA543C`。

## 5. 写入记录与当前门禁

- 授权：大尾巴于 2026-09-22 明确回复“烧录”。
- 写入前重新枚举 COM5，识别为 ESP32-S3 QFN56 rev0.2、16 MB Flash、8 MB PSRAM，MAC `28:84:85:44:6C:00`。
- 从设备读取并解析分区表，确认 app0 为 `0x10000`、容量 6400 KiB；1,625,376-byte 镜像符合容量边界。
- 使用 esptool.py 4.9.0、460800 波特率，仅写入 `0x10000` 应用区；写入过程报告 `Hash of data verified`。
- 随后独立执行 `verify_flash 0x10000`，结果 `verify OK (digest matched)`；发送硬复位后 COM5 与目标 USB 设备重新枚举正常。
- 未修改分区表、NVS、bootloader、eFuse 或安全配置，未执行整片擦除。
- 设备应用区现为 v0.8.3-dev；本地 `Settings → Sound → Test` 显示 `playing` 仍无声，A5 继续 FAIL。下一候选版已转向官方 ES8311 完整初始化，见 `../v0.8.4/ES8311官方初始化修复与待验收-【codex】.md`。
