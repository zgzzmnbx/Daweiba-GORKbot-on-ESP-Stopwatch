# v0.2.1 Grok bot 写入与验收记录

> 日期：2026-09-16  
> 状态：修正版应用区写入和读回校验 PASS；用户照片确认黑体白眼，23 条序列入口可触发，待进一步逐帧视觉/外设/长期稳定性验收。

## 写前检查

- 目标枚举：`COM5`，USB VID/PID `303A:1001`，USB 序列号/MAC `28:84:85:44:6C:00`，与先前备份和 v0.2.0 写入记录一致。COM5 是本次连接快照，不得写死为长期端口。
- 芯片：ESP32-S3 rev v0.2；Flash ID `20:4018`，16 MB；PSRAM 8 MB。
- 旧应用：`verify_flash 0x10000 firmware-v0.2.0-grok-avatar.bin` 返回 `verify OK (digest matched)`。
- 备份：`StopWatch-current-fullflash-16MB-20260916.bin` SHA-256 `ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B`，与原记录一致；该完整镜像是首次烧录前的恢复点，不是 v0.2.0 的设备快照。
- 首次待写文件：现归档为 `firmware/firmware-v0.2.1-grok-bot-initial.bin`，890016 字节，SHA-256 `217155840E13FED1AE6CD3D2666C59A22720CFA6D3675F92D6B97EB1D074BA51`；esptool `image_info` 识别为有效 ESP32-S3 镜像。
- bootloader 和分区表的新旧构建哈希分别相同；本次不重写它们。

## 写入与读回

- 工具：PlatformIO 隔离环境中 esptool.py v4.9.0；端口和芯片经当次重新识别。
- 首次写入命令：`esptool.py --chip esp32s3 --port COM5 --baud 460800 --before no_reset --after hard_reset write_flash 0x10000 firmware-v0.2.1-grok-bot-initial.bin`。执行当时文件名尚不带 `-initial`，之后为了保留第一版证据而重命名，内容与哈希未变。
- 实际擦除范围：`0x00010000–0x000e9fff`（应用镜像覆盖扇区）；未执行整片 `erase_flash`。
- 写入：890016 字节，进程退出码 0，工具报告 `Hash of data verified.`；完整日志：`G4-write-app-20260916.log`。
- 首次写后校验：`verify_flash 0x10000 firmware-v0.2.1-grok-bot-initial.bin` 返回 `verify OK (digest matched)`，进程退出码 0；完整日志：`G4-verify-app-20260916.log`。
- 未改动：bootloader、分区表、eFuse、安全启动、Flash 加密和原始完整 Flash 备份。

## 60 FPS 修正版与第二次写入

- 首次固件串口实测约 `44.8–46.4 FPS`，平均渲染 `13.57–17.13 ms`，未达 55 FPS / 12 ms 目标。原因定位为将两眼之间的大块黑区也作为一个矩形每帧重刷。
- 源码改为左右眼分别计算并刷新脏矩形。新固件 `firmware/firmware-v0.2.1-grok-bot.bin`，890352 字节，SHA-256 `A6832890B5613A8523456A2AC73972DE3A55E3A8ED249FE690B391A9C7F761D1`。第一版 BIN/ELF/MAP 分别保留为 `-initial` 文件。
- 第二次写入前，USB 序列号仍为 `28:84:85:44:6C:00`，首次应用镜像再次 `verify OK (digest matched)`。第二次同样只写 `0x10000` 应用区，擦除范围 `0x00010000–0x000e9fff`；`G4b-write-app-20260916.log` 退出码 0，`G4b-verify-app-20260916.log` 再次返回 `verify OK (digest matched)`。
- 修正版待机连续 5 秒窗口测得 `60.0 FPS`，平均渲染 `11.07–12.04 ms`，最大帧间隔 `17.82–19.14 ms`，无全屏刷新退化；原始数据见 `G4b-performance-20260916.log`。快速切换表情的一个窗口曾为 `54.1 FPS / 14.75 ms`，不能把待机指标推广为所有过渡场景。
- 获取上述串口数据时以 DTR=true、RTS=false 打开 USB CDC；首次 DTR/RTS 均为 false 的窗口没有输出。因此“首次无日志”已由后续可重复的性能日志澄清，不能再作为当前启动失败的迹象。
- 23 条源序列 ID 经 USB 串口逐项发送并收到对应 `Command accepted`，结尾恢复 `idle`；证据见 `G4b-23-sequence-dispatch-verified-20260916.log`。初次无发送间隔的压力轮测有后半段未确认，原始日志保留为 `G4b-23-sequence-dispatch-20260916.log`；增加 100 ms 发送间隔后 23/23 通过。这是入口触发验证，不是 23 条动画完整时间轴的视觉验收。

## 运行时验收边界

- 写后使用 DTR/RTS 均为 false 的 USB CDC 串口窗口观察 16 秒，串口可打开，但没有捕获到启动或 5 秒性能日志。这 **不等于** 应用失败或成功；需结合用户短按复位后的实物屏幕和后续串口/诊断结果判断。
- 大尾巴报告屏幕呈黑色圆体和白色双眼，并提供一张实物照片，归档于 `evidence/StopWatch-Grok-bot-真机照片-20260916.jpg`，SHA-256 `352C661FC183CAA0F4CE5DAAF04D27D80249505FDF27D0BB4F62644390BE3918`。照片证明方向已从旧白体黑眼切换到目标黑体白眼；因抓拍时表情在变化，单张照片不能验收全部动态和网页逐帧一致性。
- 用户观察到经常在不同表情间切换。源 `idle` 序列自身有两个 preset，每步 `5200 ms` hold、`500 ms` transition；当前引擎还保留 KK 底座的五段待机视线/头部注意力循环、微眼动和自动眨眼，触摸/IMU/按键与此前发送的串口测试命令也可能触发变化。因此可见变化不等同于每次都切换了表情 ID，不能仅凭单张照片判定异常；若继续追求网站级一致性，应单独对比并决定是否关闭 KK 待机附加动作。
- 触摸、按键、IMU、振动、全部过渡场景性能和 30 分钟稳定性仍需进一步实测，不把串口入口通过等同于这些项通过。
