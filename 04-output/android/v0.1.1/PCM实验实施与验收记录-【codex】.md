# Gork Android v0.1.1-dev PCM 实验实施与验收记录

日期：2026-09-27。状态：**源码与 APK 调试候选；手机和 Watch 未实测**。本版本在 v0.1.0 基础控制候选上增加手选 WAV 的设备 PCM 传输实验，未完成 v0.2.0 语音闭环。

## 变更

- Android `versionCode=2`、`versionName=0.1.1-dev`。v0.1.0 APK 保留在相邻目录；同包名和本机构建调试签名不等于目标手机覆盖升级通过。
- 原生文件选择器只读本次选择的 WAV，不取长期存储权限。严格接受 RIFF/WAVE、PCM16 单声道、16/24 kHz、0.1–10 秒且不截尾；其他格式明确拒绝。页面没有自动选文件、录音或上传。
- 同一 `BluetoothGatt` 请求 MTU、订阅原有三项通知，复用 Watch 音频特征发送 HELLO/CAPS、BEGIN、DATA、COMMIT、PLAY；每个 DATA 等设备 ACK 的下一个字节偏移，不能以 Android 写入回调冒充设备确认。等 `PLAYED` 只标设备回执，实际声音需要人听。失败/中止断开 GATT，不重放旧任务。协商失败时基础控制可按 20 字节包长继续，音频任务按设备回应检验能力。
- 音频总限时 180 秒、单包 5 秒、`PLAYED` 15 秒；中止按钮主动断开，Watch 端以断连停止。发送期间页面显示设备已确认字节数。
- WebView 页面重载会停止旧 BLE/朗读任务；原生桥为每次页面加载分配代际号，新页面先握手获取代际，旧页面请求不能触发新操作。

## 本机验证

| 项目 | 结果 |
|---|---|
| 构建 | Gradle 8.13、AGP 8.13.2 离线运行 `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug`，退出码 0。 |
| 单测 | `BridgePolicyTest` 1 项、`WatchProtocolTest` 4 项、`WavPcm16Test` 3 项，8 项均 0 failure，含桥代际、音频小端帧、WAV 0.1/10 秒边界和不支持格式。 |
| 静态 | `node --check mobile.js` 与共享角色资产 `--check` 通过；Lint 0 error，保留警告见原始报告。 |
| APK | [调试候选包](Gork-Android-v0.1.1-dev-debug-【codex】.apk)；`apksigner verify --verbose` 确认 v2 签名通过、1 个签名者；`aapt dump badging` 确认包名 `com.daweiba.gork`、versionCode 2、versionName 0.1.1-dev、minSdk 31、targetSdk 35。 |
| 目标手机 | `adb devices -l` 无设备；未安装、未执行同签名覆盖升级、未取得 vivo 系统和蓝牙数据。 |
| Watch | 未迁移绑定、未发送任何指令或音频、未听验；固件未改。 |

## 验收边界和下一步

- T06 仅完成 PCM 固定文件源码候选的一部分。Opus 兼容编码、可输出完整音频的 TTS、COMMIT→同轮文字→PLAY、三包应用窗口和实际传输时间对照仍未完成。当前逐包 ACK 是保守实现，不能宣称达到性能目标。A15–A17 均 NOT_RUN。
- 设备真实验链必须先取得目标手机与当次 Watch 换绑条件。现有固件只保存一个可信控制端；迁移会暂时中断电脑控制。不得将 APK 构建、签名或 `PLAYED` 回执计作 A01–A23 的真机 PASS。
- v0.1.0 的真实 A01–A11、A18–A20 仍未执行；安装、迁移与恢复步骤沿用 [上一版说明](../v0.1.0/安装升级与回退说明-【codex】.md)。
