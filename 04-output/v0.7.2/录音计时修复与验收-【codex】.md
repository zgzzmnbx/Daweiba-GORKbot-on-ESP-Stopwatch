# v0.7.2-P0 录音计时修复与验收

## 后续用户听验（2026-09-21）

用户提供电脑输出：设备→电脑48,000 bytes，1,743 B/s；电脑→设备48,000 bytes，1,636 B/s；设备报告开始/结束播放。用户明确“过了几十秒，我确实听到自己声音了”。因此一次短录音、BLE往返与扬声器可听回放已获用户确认。48,000 bytes 在16kHz PCM16单声道下为1.5秒，传输约27.5+29.3秒；不能据此宣称稳定性、音质、安全或实时对话通过。以下“待听验”为此前历史阶段。

日期：2026-09-21。当前状态：v0.7.2-P0 应用区写入与独立读回通过，录音待实测。电脑工具 v0.7.2，网页语音工作台 v0.6.0 不变。下文未烧录为开发时快照。

## 当次授权烧录

用户明确“烧录吧”。重新枚举 COM5 USB 303A:1001，并用 esptool 识别目标 MAC 与既有设备一致、ESP32-S3 rev0.2、16 MB Flash。读取实际分区，app0 为 0x10000/0x640000，镜像符合容量。

- 命令：项目隔离 Python 调用 esptool.py 4.9.0，`--chip esp32s3 --port COM5 --baud 460800 write_flash --verify 0x10000 04-output/v0.7.2/firmware/firmware-v0.7.2-P0-audio-timing-fix.bin`。
- 实际写入 1,575,200 bytes，覆盖扇区 0x10000–0x190fff；输出 Hash of data verified，exit 0。
- 再单独执行相同目标的 `verify_flash 0x10000`，输出 verify OK (digest matched)，exit 0；工具发送硬复位。
- 没有整片擦除、分区/NVS/bootloader 写入，也没有额外文件哈希。没有启动录音、上传云端或 GitHub 推送。
- 仍需用户确认 Audio test 标题 v0.7.2-P0，录音字节增长和回放听感。

## 故障证据与修复

用户在电脑显示已就绪后按住黄色 A，设备显示 Stopped / microphone OFF、0 bytes，电脑报 code 5。
源码存在可确定复现的时间戳缺陷：主循环先取 now，麦克风 begin 初始化延迟后入队取得新的 blockStarted，再用旧 now 作无符号减法。例如 1000-1005 得 4294967291，误判超过 1000 ms。该路径在首块仍待完成时触发；尚不能排除同一旧错误码下的其他实际驱动故障。

修复在采集分支重新取 millis，录音起点取实际入队时刻，同时以半周期范围判定保护旧时间戳并支持回绕。未改官方驱动、GPIO、电源时序、分区或 BLE 安全边界。

错误码新增 E9 麦克风初始化、E10 采集入队、E11 采集块超时、E12 扬声器初始化、E13 播放入队。失败仍关闭音频并释放 PCM；屏幕原因保留到重新进入页面、HELLO 或 ARM/BEGIN，不被退出清理覆盖。旧 code 5 兼容显示。

## 本机验证

- Python 回归：60 passed（含音频客户端 20 项）；两条既有依赖弃用警告，无测试失败。
- Node 浏览器音频回归：5 passed。
- C++ 固件实际使用的计时函数：6 项 static_assert 覆盖旧时钟、刚入队、1000 ms 边界、真实超时、计数回绕与跨回绕超时；实际 Xtensa 构建通过。
- PlatformIO Core 6.1.18，espressif32 6.12.0，锁定依赖未变。命令：`python tools/platformio_safe.py run -d P:\ -e m5stack-stopwatch`，P 为正式源码临时映射，Q 为项目隔离 PIO home。
- 构建 SUCCESS；RAM 64,064 / 327,680 bytes，Flash 1,574,841 / 6,553,600 bytes。
- 产物：`firmware/firmware-v0.7.2-P0-audio-timing-fix.bin`。不计算例行文件哈希，不提交固件二进制。

## 待真机验收

取得新的烧录授权、重新枚举并识别目标后，仅写应用区。进入标题 BLE Audio v0.7.2-P0 页面，运行原 start-ble-audio-test.cmd；就绪后按住 A 说话 2–3 秒，确认字节增长，松开后听回放。继续验证 B 停止、断连停止、10 秒上限；若失败记录屏幕 E 码和电脑完整错误。

当前没有烧录、启动麦克风或请求云端。P1 仍为旧版失败、补丁待复测；P2 安全/吞吐及 P3 语音服务集成不因此关闭。
