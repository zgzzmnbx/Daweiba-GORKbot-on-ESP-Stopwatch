# v0.8.4-dev ES8311 官方初始化修复与真机听验记录

> 2026-09-22。固件已完成源码修改、自动回归和 PlatformIO 构建，并按用户当次“授权烧录 v0.8.4”授权仅写入设备应用区；独立读回校验通过。用户随后执行本地 Sound/Test，确认已经听到声音；100% 音量仍偏小。

## 1. 新的真机证据

- v0.8.3 已同时开启 M5IOE1 G10 与 ESP32 GPIO14 两路功放门控，本地 `Settings → Sound → Test` 仍显示 `playing` 且完全无声。
- 因此缺少 GPIO14 不是充分根因；驱动启动、codec 电源、两路 PA 门控、ES8311 I2C 和 PCM 入队均已通过，故障继续集中在 ES8311 数字音频格式、时钟、DAC 参考、静音/输出配置或物理链路。

## 2. 官方实现对照

- M5Stack 官方 `M5StopWatch-UserDemo` 提交 `6b4aa125288b6fe9dca661f10159f6e1e5ee785c` 的 `hal_audio.cpp` 使用 44.1 kHz、16-bit、Philips I2S、MCLK，并锁定 Espressif `esp_codec_dev 1.5.4`。
- 从 Espressif 官方组件注册表下载并核对 `esp_codec_dev 1.5.4`（ZIP SHA-256 `82EF62271565C2A8A9B1945976407500FAB48ECA731AE87D65F1B9A9962EDABF`）。其 ES8311 初始化会完整设置时钟分频、I2S 位宽/格式、DAC 参考、系统电源、解除静音和音量。
- 当前锁定的 M5Unified StopWatch 回调只写 8 个寄存器，缺少官方序列中的关键配置，包括 `0x09=0x0C`（16-bit I2S）、`0x08=0xFF`（44.1 kHz LRCK 分频）、`0x44=0x58`（内部 DAC 参考）以及 `0x31` 解除静音。

## 3. v0.8.4 候选修复

- 保留 M5Unified I2S/DMA 和应用现有播放接口，但在驱动启动后按 `esp_codec_dev 1.5.4` 的官方顺序完整配置 ES8311。
- codec 配置期间先关闭 M5IOE1 G10；配置与关键寄存器读回全部通过后，再依次开启 G10 和 GPIO14，匹配官方“先 codec、后 PA”的顺序。
- 关键寄存器逐项读回；写入、读回或解除静音失败时显示 `codec config failed`，不进入 `playing`。
- codec 硬件音量固定为 0 dB（`0x32=0xBF`），用户音量继续由现有 M5Unified PCM 音量控制，避免原简化配置的过增益。

## 4. 自动验证与构建

| 范围 | 结果 | 边界 |
| --- | --- | --- |
| Python 回归 | 73 PASS | 包含官方关键寄存器和统一关断静态门禁；不代表真机出声 |
| 浏览器测试 | 5 PASS | 电脑端音频/取消逻辑 |
| Electron 测试 | 5 PASS | 桌面进程与窗口逻辑 |
| PlatformIO 构建 | PASS | RAM 63,928/327,680（19.5%）；Flash 1,625,873/6,553,600（24.8%） |

应用镜像：`firmware/firmware-v0.8.4-dev-official-es8311-config.bin`，1,626,240 bytes，SHA-256 `E41F7133EC8FD4A8C1C0280878F321422CED5F86766F3ECFAFB6A0B0C6DD98F7`。

## 5. 当前门禁

- 源码、归档镜像和设备应用区均为 v0.8.4-dev。
- 写入前重新识别 COM5：ESP32-S3 QFN56 rev0.2、16 MB Flash、8 MB PSRAM、MAC `28:84:85:44:6C:00`；从设备读取分区表，确认 app0 为 `0x10000`、容量 6400 KiB。
- 使用 esptool.py 4.9.0、460800 波特率，仅将 1,626,240-byte 应用镜像写入 `0x10000`；烧录器报告 `Hash of data verified`，随后独立 `verify_flash` 返回 `verify OK (digest matched)`，并完成硬复位，COM5 重新枚举正常。
- 未执行整片擦除，未修改分区、NVS、bootloader、eFuse 或安全配置。
- 本地 `Settings → Sound → Test` 真机听验 PASS：设备显示 `playing`，用户确认已经听到声音。由此确认完整 ES8311 初始化是此前无声故障的根因，扬声器物理链路可工作。
- 音量验收仍为 PARTIAL：用户确认 100% 音量也不大。该结果不影响“已出声”结论，但不得宣称最大音量达标；后续需单独核对 PCM 峰值、M5Unified 软件增益、ES8311 DAC/模拟输出增益及失真上限。
- 控制台遥控六种内置声音、0% 静音、分档音量、停止时延和重启保持仍须分别实测。
