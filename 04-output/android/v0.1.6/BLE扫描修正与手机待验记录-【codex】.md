# Gork Android v0.1.6-dev BLE 扫描修正与手机待验记录

日期：2026-09-27。目标手机 V2405A / Android 16，Watch 固件 v0.9.1-dev。

- v0.1.5 在 Watch 显示 `Control ON / Link waiting / Binding saved` 时扫描两次均未发现设备；同一地点的电脑被动扫描能发现 `GorkBot-SW` 和表情服务 UUID。手机蓝牙设置的已配对列表未显示 GorkBot-SW，不能据此认为手机已完成该设备的加密 GATT 绑定。
- 用户按迁移步骤在 Watch 本机清除原绑定，回报 `Binding none`，并曾打开 Pair 窗口。v0.1.5 在该次窗口期间仍未发现 Watch；没有触发系统配对或发送指令。
- v0.1.6 移除 Android 扫描器的服务 UUID 硬件过滤，仍在扫描回调中只收录名称为 `GorkBot-SW` 或含目标服务 UUID 的设备，连接仍限制为本次扫描候选。此修改用于验证手机是否因广播与扫描响应分开发送而漏掉目标；根因尚未经手机实测证实。
- 本机离线执行 Gradle `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug --no-daemon` 成功。用户本人确认 vivo 外部来源安装提示后，ADB 同签名覆盖安装成功；包管理器回报 versionCode 7、versionName `0.1.6-dev`。
- 安装后的一次扫描仍未发现设备，但此时 `Binding none`，电脑也未看到 Watch 广播。用户重新打开 Pair 窗口后再次扫描，手机仍未发现；同一时刻电脑被动扫描再次看到 Watch 名称与目标 UUID。因此移除扫描器 UUID 过滤尚未解决手机发现问题。待近距离复测与进一步诊断。GATT 服务发现、表情命令回执和真实画面均未验收。

本轮未写固件、未调用云端、未操作电脑蓝牙绑定；电脑旧绑定已由用户在 Watch 本机清除。用户原有 v0.1.5 调试包保存在上一版本目录。
