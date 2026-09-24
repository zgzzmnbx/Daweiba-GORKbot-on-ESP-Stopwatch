# v0.8.2-dev 扬声器供电修复与验收记录

> 2026-09-22。候选固件完成源码修改、自动回归和 PlatformIO 构建后，已按大尾巴当次“烧录吧”授权仅写入设备应用区，并通过工具写入校验及独立读回校验；后续人工复测显示 `playing` 但仍无声，A5 失败。

## 1. 诊断结论

- v0.8.1 本地 `Settings → Sound → Test` 在 100% 音量无声。
- 电脑随后通过 `Audio test` 发送 2 秒、16 kHz、PCM16、幅度 16000 的清晰诊断音，共 64,000 bytes；设备返回播放开始和结束，传输约 1,829 B/s，仍完全无声。
- 因此已排除 BLE 未传完、短 PCM 时长不足和单纯音量过低；问题集中在设备端 codec 电源、功放使能、codec 配置或 I2S 输出链路。
- 代码审查发现应用另建一个 `M5IOE1` 驱动实例控制振动，而 M5Unified 同时通过自己的 M5IOE1 实例控制振动、codec 电源 G3 和功放 G10。两套状态独立的驱动共享同一芯片属于高风险设计，但在真机复测前只能称为候选根因。

## 2. v0.8.2 候选修复

- 删除应用层第二套 M5IOE1 依赖和对象；振动统一改用 M5Unified `M5.Power.setVibration()`，共享扩展芯片只保留一个控制者。
- 每次播放前显式恢复 M5IOE1 G3/G10 为推挽输出并拉低，再由 M5Unified 扬声器回调按顺序开启 codec 电源、写入 ES8311、开启功放。
- 启动后读取 G3/G10 输出锁存及 ES8311 `0x18:0x00`；分别返回 `driver failed`、`power/PA failed`、`codec failed` 或进入 `playing`。
- Sound 页面新增 `Speaker` 状态行；本地 Test 即使仍无声，也能直接显示故障停在哪一层。
- 长 PCM Audio test 与内置短音共用同一扬声器启动函数，避免两条路径继续产生不同诊断结果。

## 3. 自动验证与构建

| 范围 | 结果 | 边界 |
| --- | --- | --- |
| Python 回归 | 72 PASS | 新增“单一 M5IOE1 控制者”静态门禁；不代表真机出声 |
| 浏览器测试 | 5 PASS | 电脑端音频/取消逻辑 |
| Electron 测试 | 5 PASS | 桌面进程与窗口逻辑 |
| PlatformIO 构建 | PASS | RAM 63,928/327,680（19.5%）；Flash 1,624,561/6,553,600（24.8%） |

应用镜像：`firmware/firmware-v0.8.2-dev-speaker-power-diagnostic.bin`，1,624,928 bytes。

## 4. 写入记录

- 授权：大尾巴于 2026-09-22 明确回复“烧录吧”。
- 写入前重新枚举 COM5，识别为 ESP32-S3 rev0.2、16 MB Flash、8 MB PSRAM，MAC `28:84:85:44:6C:00`。
- 从设备读取并解析分区表，确认 app0 为 `0x10000`、容量 6400 KiB；1,624,928-byte 镜像符合容量边界。
- 使用 esptool.py 4.9.0、460800 波特率，仅写入 `0x10000` 应用区；写入过程报告 `Hash of data verified`。
- 随后独立执行 `verify_flash 0x10000`，结果 `verify OK (digest matched)`；发送硬复位后 COM5 与目标 USB 设备重新枚举正常。
- 未修改分区表、NVS、bootloader、eFuse、安全配置，未整片擦除。

## 5. 当前门禁与复测方法

- 设备应用区现为 v0.8.2-dev，写入和独立读回 PASS；本地 Test 显示 `playing` 仍无声，A5 为 FAIL。
- 现在先在设备执行 `Settings → Sound → Test`，记录 `Speaker` 行显示内容及是否听到声音。
- `playing` 证明 G3/G10 锁存、ES8311 I2C 和 PCM 入队通过。复核官方出厂示例后发现其另行拉高 ESP32 GPIO14；v0.8.3 已据此形成双功放门控候选版，见 `../v0.8.3/GPIO14功放门控修复与待验收-【codex】.md`。
