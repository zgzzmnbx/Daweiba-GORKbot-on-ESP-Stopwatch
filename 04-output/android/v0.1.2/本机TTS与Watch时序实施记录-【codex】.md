# Gork Android v0.1.2-dev 本机 TTS 与 Watch 时序实施记录

日期：2026-09-27。状态：**调试 APK 源码候选；未达到手机/Watch 真机门禁**。此轮承接 v0.1.1 的手选 WAV→Watch PCM 实验，不改变电脑端或设备固件。

## 实施范围

- Android `versionCode=3`、`versionName=0.1.2-dev`。v0.1.1 APK 保留在相邻目录。调试签名仍只供开发；同签名覆盖升级要在目标手机验证。
- 本机 TTS 只选系统声明无需网络的中文音色；`synthesizeToFile` 等异步完成回调后读取应用私有临时 WAV。引擎初始化限时 15 秒、合成限时 45 秒，停止/失败/成功后删除文件；下次启动清理意外中断的本模块缓存文件。当前手机是否安装合适音色、是否真的离线及能否输出完整文件均未实测。Android 异步合成和停止语义参见 [TextToSpeech](https://developer.android.com/reference/android/speech/tts/TextToSpeech) 与 [UtteranceProgressListener](https://developer.android.com/reference/android/speech/tts/UtteranceProgressListener)。
- WAV 转换器接受完整非压缩 PCM16、单/双声道、8–48 kHz，混合双声道并按实际长度转换到 16 或 24 kHz 单声道；0.1–10 秒之外明确拒绝，不裁剪、不叠加固定增益。设置页可只测文件导出和转换，不向 Watch 发送。
- 对话页新增显式「本机合成后由 Watch 朗读」实验入口，文字限 24 字/72 UTF-8 字节且不接受 emoji。BLE 在同一任务内完成 HELLO→BEGIN→设备确认的 DATA→COMMIT→F0/F1/F2 对应文字→PLAY→PLAYED；最多 3 包应用层在途，Android GATT 写入仍逐次等待回调，设备已确认字节数只按 ACK 增长，后续 ACK 可覆盖单个丢失回执。普通短命令也同时等待写入回调与设备回执后才允许下一包。停止时先停 TTS，再断开 GATT；合成或传输失败不提前发送文字。`PLAYED` 仅是设备协议回执。

## 验证与证据边界

| 项目 | 当前结果 |
|---|---|
| 构建 | Gradle 8.13、AGP 8.13.2 离线执行 `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug`，退出码 0。 |
| JVM 单测 | 12 项均 0 failure：桥代际 1、BLE 协议 4、严格输入 WAV 3、TTS WAV 降采样/双声道/长度拒绝 3、三包窗口与 ACK 进度 1。仅验证纯逻辑，不验证系统 TTS 引擎或 GATT 回调时序。 |
| 静态 | `node --check mobile.js`、共享角色资源 `--check` 通过；Android Lint 0 error。 |
| APK | [Gork Android v0.1.2-dev 调试包](Gork-Android-v0.1.2-dev-debug-【codex】.apk)：v2 签名验证通过，1 个签名者；`aapt` 确认包名 `com.daweiba.gork`、versionCode 3、versionName 0.1.2-dev、minSdk 31、targetSdk 35。 |
| 目标手机 | `adb devices -l` 无设备；无实际系统音色、TTS 文件、安装升级、权限或 WebView 记录。 |
| Watch | 未迁移绑定，未发送 PCM/文字/PLAY；COMMIT→文字→PLAY 为源码时序，A15–A17 未执行，实际响度、完整性和稳定性不作通过声明。 |

## 后续任务

1. 接入目标 vivo 手机，执行 A01/A03/A12/A14 的真实引擎、文件和界面检查；缺少离线音色时记录能力限制，继续按已确认的云 Provider 方案实现，不伪称已支持。
2. 当次确认 Watch 换绑范围后，先做基础 GATT 验链，再用同一完整 WAV 做 PCM/Opus 对照；手机与电脑迁移/恢复按 [既有清单](../v0.1.0/安装升级与回退说明-【codex】.md) 分开记录。新固件写入仍须单独授权。
3. T05 的 ASR、AI、云 TTS、三项上传许可与安全凭据；T06 的 Opus、真实 A15–A17；T07 后台服务与长稳仍未完成。v0.2.0 和 v0.3.0 不标完成。
