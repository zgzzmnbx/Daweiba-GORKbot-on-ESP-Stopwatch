# Gork Android v0.1.7-dev BLE 配对与基础控制实测

日期：2026-09-27。手机 V2405A / Android 16；Watch 固件 v0.9.1-dev。用户仅要求完成现有功能，不新增云语音、Opus 或后台服务。

## 修复与构建

- v0.1.6 在 Watch Pair 窗口开启、手机距 Watch 约 10–20 cm 时，8 秒内扫描不到设备；同处电脑被动扫描可见 `GorkBot-SW` 与目标服务 UUID。临时诊断构建记录 `results=0`，表明 Android 应用没有收到任何扫描回调，而非仅名称或 UUID 筛选失误。
- 原 AndroidManifest 声明了 `BLUETOOTH_SCAN`，没有 `ACCESS_FINE_LOCATION`，也没有 `neverForLocation`。Gork 扫描不推导物理位置；按 [Android 官方蓝牙权限说明](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions) 给扫描权限添加 `android:usesPermissionFlags="neverForLocation"`。v0.1.6 的本地候选过滤继续保留，仅接受 Gork 名称或目标服务 UUID，本次扫描结果才可用于连接。诊断日志只记录扫描数量，不记录其他设备身份。
- v0.1.7 versionCode 8。本机 Gradle 离线执行 `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug --no-daemon` 成功，13 项单测无失败；共享角色资源检查通过，APK v2 签名校验通过。用户本人确认 vivo 外部来源安装提示后，ADB 同签名覆盖安装成功；包管理器回报 versionCode 8、versionName `0.1.7-dev`。

## 设备实测

- 用户在 Watch 本机清除旧绑定，显示 `Binding none`，并打开 Pair 倒计时；手机 Gork v0.1.7 扫描发现一台 `GorkBot-SW`。选择后手机系统弹出蓝牙配对请求；完成配对后，Gork 页面显示配对、三项 GATT 服务发现、通知订阅就绪。没有使用电脑端连接或放宽 Watch 加密身份校验。
- 系统配对弹窗的“允许访问您的通讯录和通话记录”初始为勾选。配对后立即进入手机蓝牙设备详情，将 `同步通讯录` 关闭，并通过界面确认开关为关；此项不是 Gork 控制所需。回到 Gork 后 Watch 仍显示控制就绪。
- 手机向 Watch 两次发送 `excited` 一次播放命令，页面两次显示设备表情回执；用户确认第二次实际看到了表情变化。是否按预期回到 `idle` 未单独确认。
- 手机发送“你好”文字，页面显示 Watch 文字回执，用户确认 Watch 屏幕显示“你好”；发送“短音 1”，页面显示设备完成回执，用户确认听到短音。这两项是单次真机验收，不扩展到其他文字与五种短音。
- 本机中文 TTS 从“你好”草稿生成完整音频并经 BLE 发送，页面最后返回 `PLAYED`，且提示文字在 COMMIT 后发送。用户确认 Watch 实际读出“你好”，完整、清楚；只覆盖这一句的一次听验。

## 边界

Watch 现绑定手机；电脑端若需重新控制，须按迁移清单断开手机、在 Watch 本机清绑定并重新配对电脑。此轮未写固件、未调用云端。手选 PCM、本机 TTS→Watch、长稳、掉线重连和陌生端拒绝等仍待逐项真机验收。
