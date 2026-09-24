# v0.7.1 电脑音频工具服务发现修复

日期：2026-09-21。范围仅电脑测试工具；设备固件保持 v0.7.0-P0，网页工作台保持 v0.6.0，没有重新烧录或清除配对。

## 复现与证据

1. 用户运行 echo 报“v0.7.0 audio firmware required; current device has no audio service”；同时用户确认设备能够进入 Audio test 页面。
2. 只读 BLE 默认枚举成功连接，但只返回 GAP/GATT 标准服务和旧 `48f1a001` 表情服务，没有音频服务。
3. 单独以 `winrt.use_cached_services=False` 全服务枚举，两次报 Windows `0x8000FFFF` / WinError -2147418113，未启动音频。
4. 使用新扫描对象 + `services=[48f1b001-8a75-4db6-9c18-590f7e9b0a01]` + 无缓存查询，成功返回音频 service，input `48f1b002`（WRITE/WRITE_NR）和 events `48f1b003`（NOTIFY）。这是直接设备服务发现证据，不是 mock，也不是音频运行证据。
5. 8766 只读 health 显示其机器人连接为 disabled/disconnected；未关闭服务或接管会话。随后尝试完整 HELLO/PING 时扫描候选为 0，尚未发出握手请求，已请用户关闭旧测试窗口并保持测试页。

上述证明问题发生于 Windows GATT 发现路径，不能据此把设备判成旧固件。旧缓存参与是依据默认/无缓存差异的判断；未声称查明 Windows 全服务查询内部错误的根因。

## 修改与验证

### 用户回复“可以连接”后的复测

- 5 秒目标服务扫描：0 个候选；再做 12 秒不带服务过滤的扫描，仍未发现名称匹配 GorkBot 的广播。
- 8766 health 中机器人 `connected=false, enabled=false`；未发现仍运行的音频测试或旧 BLE 控制台 Python 进程。只读取相关进程信息，没有终止程序。
- 此次未进入连接阶段，未发送 HELLO/PING/ARM/PLAY，也没有录音或播放。之前定向无缓存发现成功的证据保留，但不能据此宣称本次握手成功。
- 下一步请用户在设备 Bluetooth 页面关闭再开启 BLE，然后返回 Audio test，恢复可发现状态后重试；不清绑定、不重配、不重新烧录。

### 客户端改动

- `tools/stopwatch_audio.py` 统一使用 `audio_connection()`，显式指定音频服务及 UNCACHED，保留现有加密配对策略与独立连接生命周期。终端显示工具版本 v0.7.1。
- 不再用缺少服务推断固件版本；未取得会话 epoch 时退出不会向缺失特征发送 CANCEL。正常会话停止仍走原 CANCEL。
- `tools/test_stopwatch_audio.py` 新增连接工厂参数和缺服务退出测试，18/18 音频模拟测试通过；原录音分包、取消/过期回执、WAV 限制测试继续保留。
- 合并回归 58 项 Python + 5 项 Node，63/63 通过；两条既有 Starlette 弃用警告保留。没有固件源码改动，因此本轮未重新构建固件。
- 未调用 ARM/PLAY，没有录制或播放音频，没有语音服务/云请求，没有变更固件及系统配对。
- 后续必须验证实际按键录音与回放；此修复不提前关闭 P1/P2。

### 用户重开蓝牙后的真机握手

- 用户回复“已重开蓝牙”后，扫描发现 1 个目标；使用修复后的 `audio_connection()` 连续完成两次连接、关闭和再连接。
- 两次均发现音频服务及 input/events 特征，HELLO/CAPS 成功，协商包长 244 bytes；两次 PING 均收到对应 ACK。
- 验证脚本正常退出（exit 0），连接已释放。仅握手、心跳和关闭会话，不发送 ARM/PLAY，没有录音、播放或云请求。
- 结论：本机服务发现修复、音频协议握手及一次重连已实测通过；实际音频双向数据、听感、吞吐、安全负向与长稳仍未验收。

官方参考：[Bleak Windows 后端参数](https://bleak.readthedocs.io/en/latest/backends/windows.html)、[Windows GetGattServicesAsync 缓存模式](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.bluetoothledevice.getgattservicesasync)。本机锁定 Bleak 3.0.2 源码已核对参数透传行为。
