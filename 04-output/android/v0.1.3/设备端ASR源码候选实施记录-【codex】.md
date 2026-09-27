# Gork Android v0.1.3-dev 设备端 ASR 源码候选实施记录

日期：2026-09-27。Android `versionCode=4`、`versionName=0.1.3-dev`。上一版 v0.1.2 APK 保存在独立目录。本轮只改手机应用源码和文档，未安装、换绑、调用云服务或写入 Watch 固件。

## 实施范围

- 显式按住说话入口请求 `RECORD_AUDIO`，只用 API 31+ `SpeechRecognizer.createOnDeviceSpeechRecognizer`，设置 `zh-CN`；系统未报告设备端识别服务时明确失败，不回退到普通识别器。识别结果最多 300 字，只写入手机草稿，由人确认后再发送。当前没有自动 AI/Watch 上传。
- 松开调用 `stopListening` 并等待结果；取消、页面重载、应用进入后台和全局停止时销毁识别器；30 秒超时。拒绝权限、缺少中文模型、无匹配文本等分开给出错误码。麦克风音频由 Android 识别服务处理，本应用未保存录音文件。
- `asr.status` 仅代表系统报告设备端识别服务存在；无法证明中文模型已安装，更不能证明目标 vivo 在断网时能转写。Android 官方 API 语义参见 [SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer) 和 [RecognitionListener](https://developer.android.com/reference/android/speech/RecognitionListener)。

## 本机验证

| 项目 | 结果 |
|---|---|
| Gradle | `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug --offline --no-daemon` 成功；12 项既有桥、协议、WAV 与窗口单测，0 失败；Lint 任务通过。Android 系统 ASR 行为无本机设备测试。 |
| 静态 | `node --check app/src/main/assets/mobile.js`、共享角色资产 `export_shared_assets.py --check`、`git diff --check` 通过。 |
| APK | [Gork Android v0.1.3-dev 调试包](Gork-Android-v0.1.3-dev-debug-【codex】.apk)：APK v2 签名验证通过，1 个调试签名者；`aapt` 确认 `com.daweiba.gork`、versionCode 4、minSdk 31、targetSdk 35、`RECORD_AUDIO`。正式签名尚未建立。 |
| 真机 | `adb devices -l` 无设备；未安装 APK，未做 A01–A23 任一真实手机/Watch PASS。 |

## 尚需验收与后续工作

1. 目标 vivo 接入后先记录 Android/OriginOS 版本、设备端识别服务与中文模型；在断网状态测 A12 的按住说话、松开结果、拒绝权限、后台/来电打断和重新启动。若服务或中文模型缺失，保持文字输入可用并据实记录，不假称离线语音已支持。
2. 取得 Watch 从电脑迁至手机的明确时间窗口后，按任务书执行系统配对、三服务发现、真实命令回执、PCM/TTS 可闻和恢复电脑绑定；单次 `PLAYED` 回执不替代听验。本次未改变固件单可信控制端策略。
3. T05 的云 ASR/TTS、AI Provider、三项上传许可和安全凭据，T06 Opus，T07 后台服务，T08 悬浮伴侣及 T09 正式签名/覆盖升级仍未完成。v0.2.0/v0.3.0 不标完成。
