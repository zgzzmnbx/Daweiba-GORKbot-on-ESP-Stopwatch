# v0.8.6-dev 内置声音 codec 高响度实施与验收记录

## 1. 用户实测与结论

- v0.8.5-dev 已将六个内置声音 PCM16 峰值由 10,000 提高到 30,000，用户真机确认 100% 音量仍不够大。
- PCM16 上限为 32,767，不能再将当前波形直接乘 3；否则会产生严重数字削波。
- v0.8.6-dev 采用 ES8311 DAC 增益：仅六个内置短音将 REG32 从 `0xBF`（0 dB）提高到 `0xD2`（+9.5 dB，名义电压约 2.99 倍）。
- 动态语音、BLE PCM 和设备录音回放继续使用 `0xBF`（0 dB），避免全局放大底噪及未知音频。
- 名义电压增益不等于声压或主观听感严格 3 倍；当前 PCM 已接近满幅，高音量可能出现 codec/功放饱和或可闻失真。
- 写入后用户真机确认“声音正常大小了”，据此将最大响度不足问题记为通过；不将该表述扩大解释为六种声音逐项音质、版本文字显示、异常发热或长期稳定性均已通过。

## 2. 实现与保护边界

- 新增 `SpeakerGainProfile::BuiltInLoud`，只由 `SoundControl` 的内置声音路径显式选择。
- Settings 首页显示固件版本 `v0.8.6-dev`，便于直接核对设备实际运行版本。
- `AudioProbe` 及其录音回放调用保持默认 `SpeakerGainProfile::Unity`。
- codec 配置后独立读回 REG32；目标值不符即返回 `codec config failed`，不会开启两路外部功放门控。
- 停止、失败、录音切换和功放关断路径不变。

## 3. 自动验证

- Python：75 项通过。
- 浏览器：5 项通过。
- Electron：5 项通过。
- PlatformIO：构建成功；RAM 63,928 bytes（19.5%），Flash 1,625,497 bytes（24.8%）。
- 候选镜像：`firmware/firmware-v0.8.6-dev-3x-codec-boost.bin`
- 文件大小：1,625,856 bytes。
- SHA-256：`D8D97DD4D0C5F15520812EB168F4BF7FD9434ED9996A08D2B158301C5D3B5D7A`。

## 4. 当前设备状态与烧录边界

- 源码和设备应用区：均为 v0.8.6-dev。
- 按用户当次“做完烧录即可”授权，重新识别 COM5：ESP32-S3 QFN56 rev0.2、16 MB Flash、8 MB PSRAM、MAC `28:84:85:44:6C:00`；从设备实读分区表确认 app0 为 `0x10000`、容量 6400 KiB。
- 使用 esptool.py 4.9.0、460800 波特率，仅将 1,625,856-byte 应用镜像写入 `0x10000`；烧录器返回 `Hash of data verified`，独立 `verify_flash` 返回 `verify OK (digest matched)`，随后硬复位，COM5 重新枚举正常。
- 未改分区、NVS、bootloader、eFuse，未整片擦除。

## 5. 真机听验步骤

1. 烧录后先将设备音量调到 20%–30%，播放本地 Sound/Test。
2. 每次只上调一档；达到够用响度即停止，不默认直接升到 100%。
3. 分别试听六种内置声音，检查破音、爆音、明显底噪和音色塌陷。
4. 短时间重复播放后检查扬声器/机身是否异常发热；出现刺耳失真或异常发热立即停止。
5. 复测 Audio test 录音回放，确认它仍保持原 0 dB 路径、没有被高响度档放大。

## 6. 真机验收结论

- 内置声音可闻：PASS（继承 v0.8.4 已出声结论）。
- 最大响度是否达到正常可用水平：PASS（用户 2026-09-23 真机确认）。
- Settings 版本文字实屏：NOT REPORTED。
- 六种声音逐项失真、爆音、底噪：NOT RUN。
- 异常发热与长期稳定性：NOT RUN。

当前状态：`FLASHED / READBACK VERIFIED / LOUDNESS ACCEPTED`。
