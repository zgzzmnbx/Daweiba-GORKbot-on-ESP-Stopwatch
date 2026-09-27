# Gork Android

独立 Android 工程，当前为 **v0.1.1-dev 调试候选**。包名 `com.daweiba.gork`，与闪念 `com.dabawei.flashnote` 独立。手机端源码已实现本地四标签角色页、偏好与草稿保存、受限 WebView 桥、原生 BLE 基础控制、手选 WAV 的 Watch PCM 传输实验和无需网络的系统中文 TTS 探测。尚未连接目标手机或迁移 Watch 绑定，所有真机与声音项目均未验收。

## 环境与构建

- JDK 17、Android SDK API 35、Build Tools 35.0.0；minSdk 31、targetSdk/compileSdk 35。Gradle Wrapper 8.13、Android Gradle Plugin 8.13.2、Kotlin 2.2.20、AndroidX WebKit 1.17.1 固定版本。参见 Android 官方 [AGP 8.13 兼容表](https://developer.android.com/build/releases/agp-8-13-0-release-notes)和 [WebKit 版本](https://developer.android.com/jetpack/androidx/releases/webkit)。
- 设置 `ANDROID_HOME` 或在被忽略的 `local.properties` 中写 `sdk.dir`。在本目录运行 `./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug`。如本机 Gradle Wrapper 需经代理下载，代理仅配置于个人环境或 Gradle 用户目录，不写进项目文件。
- 调试 APK 为 `app/build/outputs/apk/debug/app-debug.apk`；当前候选副本位于项目 `04-output/android/v0.1.1/`，上一版保存在 `v0.1.0/`。调试签名只供开发。要承诺覆盖升级，须固定正式签名并在目标手机执行 A01/A19。
- 构建前自动运行 `tools/export_shared_assets.py` 从桌面权威资源同步角色资产；交付前运行 `python tools/export_shared_assets.py --check`，不要手改 `app/src/main/assets/shared/`。如 Python 命令不在系统路径，可设置个人环境变量 `PYTHON`。来源为固定 Avatar Lab 快照，见项目第三方来源记录。

## 当前能力和边界

- 打开 APK 只加载内置页面，不自动扫描、配对、录音、联网或发送旧任务。角色可在手机内选择 10 种形象并预览 23 条来源表情；Watch 形象固定 Gork，`happy-work` 是设备专属表情。
- Watch 页面由用户点击扫描并授权附近设备权限；只允许连接本次扫描候选。系统配对成功后发现表情、短音、音频三个 GATT 服务、协商 MTU 并订阅通知，完成后才显示 READY。基础命令包括表情、文字、清屏、六种短音、音量和停止。v0.1.1 增加手工 WAV→Watch PCM 实验：只在设备确认字节偏移后推进；可中止并断开。尚无 Opus、TTS→Watch 或 COMMIT 后文字时序。
- 当前固件只保存一个可信控制端。手机首次接管前，需先明确允许当前 Watch 暂离电脑，并在设备设置中清绑定、打开 Pair。恢复电脑也需要反向迁移。APK 不提供隐式清绑定或放宽身份校验。
- 手机朗读只选择系统报告为不需要网络的中文音色，需用户点击后才播放；这不代表目标 vivo 已安装可用音色。AI、云 ASR/TTS、自动 Watch PCM/Opus 朗读、后台前台服务和悬浮伴侣仍按任务书后续阶段实施。手选 WAV 的设备 `PLAYED` 回执不能替代实际听验。
- 页面桥固定 APK 本地 origin 和主 frame，阻止外部网页与任意网络加载；偏好保存在应用私有目录且排除备份。桥接口和 BLE 字节契约见 `docs/协议与桥契约-v0.1.1-【codex】.md`。

## 测试状态

本机 Gradle 构建、8 项桥/协议/WAV 单测、资产一致性及浏览器离线布局检查已执行；v0.1.1 结果见项目 `04-output/android/v0.1.1/PCM实验实施与验收记录-【codex】.md`。浏览器检查不能替代 Android WebView、vivo 蓝牙、设备回执、用户听验或覆盖升级验收。
