# PC v0.20.0-dev / Watch v0.11.0-dev 实施与验收

结论：软件候选已构建，当前Watch app0写入并独立读回通过；正式PC已从0.19.4正常退出重开到0.20.0。设备启动输出/ BLE广播未观察到，未配热点，完整任务未达稳定交付。

| 任务 | 进度及证据 |
|---|---|
| T00 | 基线与定点恢复完成，根/嵌套dirty保留 |
| T01 | 协议/成熟TLS宿主握手/mbedTLS编译/静态预算完成；运行峰值待设备 |
| T02 | 共享音频状态判断和两适配器生产代码、兼容回归通过；全固件硬件生命周期未验 |
| T03–T09 | 配网/发现/控制/完整WAV/PTT/会话/策略/电源/UI源码接线；实机分项待测 |
| T10 | Python、Node、C++自动验证与真实隔离Electron通过，候选已构建；所有故障注入项尚未覆盖，见A矩阵 |
| T11 | ROM检查、旧镜像匹配、仅app0写入/独立verify_flash通过；新启动与BLE/配网/听感未通过门槛 |
| T12 | BLOCKED：同热点/安全配网未确认，真实控制1000条、上下行各30次、Wi-Fi100对话/BLE20/100恢复未执行 |
| T13 | NOT_RUN：8小时、500次资源循环、帧率对照和电池未执行 |
| T14 | 源码/候选/协议/基线/使用恢复/矩阵和根上下文已落盘；阶段交付，不称完整目标完成 |

自动验证：最终全Python144项（原119+网络20+Watch管线5），旧BLE音频24项，控制台58项，桌面32项；C++真实生产帧/CRC/最近状态与音频任务判断宿主编译通过。Mock HTTP和控制设备只验证生产业务管线，不证明真实麦克风、云服务、听感或Wi-Fi速度。隔离Electron使用8885和独立profile，无设备/云请求；双主题、密码不回显、422秘密隐藏、窄窗、对话入口实际显示通过。截图与electron-network.json在tests/。

Python用Codex-Temp/.venv-companion/Scripts/python.exe -m pytest 03-Src/stopwatch-voice-companion/tests -q；音频工具为tools/test_stopwatch_audio.py。控制台与桌面各自npm test。固件用Codex-Temp/.venv-platformio/Scripts/python.exe -m platformio run -d 03-Src/stopwatch-grok-avatar -e m5stack-stopwatch；本机全局已锁定PIO包工作正常，切到旧临时pio-home出现GCC CreateProcess失败，未改工具链。应用镜像2227328字节，静态RAM118120、Flash程序2226961，分区容量6553600。

烧录记录只保留本地：Codex-Temp/wifi-ble-v020/flash-v011.log、verify-v011.log、final-build.log。当前授权下核对COM5/MAC后write_flash 0x10000，写入工具Hash verified；独立verify_flash digest matched，再hard_reset。之后受控串口和一次BLE扫描均未取得启动/广播证据，不以空白日志判定应用损坏，也不清NVS/绑定试错。现场问询已发出，需用户屏幕确认/必要正常重启。

本轮没有修改电脑/手机网络、路由、防火墙、热点密码、全局配置、Android或芯片安全状态，没有真实AI/云音频测试或推送。隔离服务随后关闭；正式8766及原8765维持loopback。Git范围存档记录另存；原索引、HEAD及其他工作不改。

Git候选恢复引用 refs/codex/backups/v020-fw011-20261004-025339，提交6319e027b27e4a3d8de59ac09db7682eca0ac1b9；原HEAD和原索引逐字节保持，未推送。早期Electron验证失败日志保留：原因为等待版本读取不足；修复等待后最新electron-network.json为PASS。性能采样工具只完成CLI/语法检查。隔离8885进程已停止。

收尾正常重开后8766运行PID35980、版本0.20.0-dev；8766/8765均仅127.0.0.1监听，8885已关闭。仍无用户屏幕/同热点答复，不完成T11–T13或声称整体稳定。

2026-10-04 现场追加：用户确认 Watch 实屏显示 v0.11.0-dev，启动/版本子项 PASS_DEVICE；随后照片显示眼睛重影，视觉 FAIL_DEVICE。已开发 v0.11.1-dev 修复候选，用户追加授权后仅app0写入并独立校验通过，新实屏/消影待验，见 ../v0.11.1/重影修复与验收记录-【codex】.md。此前空白串口/广播扫描是当次观察，不再作为“启动尚未证实”的当前结论。PC 本次8766未监听，原PID/运行状态为历史快照。

本次后续用户追加授权：v0.11.1-dev已只写app0且独立校验通过，新启动/版本/消影待实屏；详细写入日志保留本机，见v0.11.1修复记录。T11视觉不因软件回归或校验自动转PASS。

现场反馈追加：2026-10-04 大尾巴反馈：“我已经重启watch，版本正确。目前看没有重影”。v0.11.1-dev 正常启动/实屏版本 PASS_DEVICE，当前观察消影 PASS_DEVICE 子项；尚未覆盖全部表情循环、长稳或设备帧率。
BLE自动连接仍报WinError -2147024874“设备不识别此命令”，未配网；不把消影子项通过扩展为T11或整体任务通过。

2026-10-04 后续：用户确认v0.11.1当前无重影；Bluetooth实屏显示ON/Connected/Saved/SC+encrypted，但PC服务发现失败。v0.11.2保留旧服务范围候选已构建并经本次授权仅app0写入、独立verify_flash通过；新实屏/BLE恢复/配网未验，T11–T13未完成，详见 ../v0.11.2/BLE服务顺序修复与验收记录-【codex】.md。

随后用户确认v0.11.2启动/实屏版本；WinRT旧音频服务/特征/描述符查询恢复，表情可查询，短音/配网与完整服务枚举仍失败。BLE完整恢复/配网/PTT/听验未通过，未将子项扩展为整组PASS。
