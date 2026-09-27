# Gork Android

独立 Android 工程，当前为 **v0.1.5-dev 调试候选**。包名 `com.daweiba.gork`，与闪念 `com.dabawei.flashnote` 独立。手机端源码已有本地四标签角色页、偏好与草稿保存、受限 WebView 桥、原生 BLE 基础控制、手选 WAV 的 Watch PCM 传输实验、本机中文 TTS 文件导出→格式转换→Watch PCM、显式设备端中文 ASR 按住说话，以及用户配置的 HTTPS 文字 AI 与独立上传许可。V2405A（Android 16）已安装并做部分手机实测；用户确认手机朗读“你好”可闻。Watch 未换绑，云端未调用，其他语句和音质未评价。

## 环境与构建

- JDK 17、Android SDK API 35、Build Tools 35.0.0；minSdk 31、targetSdk/compileSdk 35。Gradle Wrapper 8.13、Android Gradle Plugin 8.13.2、Kotlin 2.2.20、AndroidX WebKit 1.17.1 固定版本。参见 Android 官方 [AGP 8.13 兼容表](https://developer.android.com/build/releases/agp-8-13-0-release-notes)和 [WebKit 版本](https://developer.android.com/jetpack/androidx/releases/webkit)。
- 设置 `ANDROID_HOME` 或在被忽略的 `local.properties` 中写 `sdk.dir`。在本目录运行 `./gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:lintDebug`。如本机 Gradle Wrapper 需经代理下载，代理仅配置于个人环境或 Gradle 用户目录，不写进项目文件。
- 调试 APK 为 `app/build/outputs/apk/debug/app-debug.apk`；当前候选副本位于项目 `04-output/android/v0.1.5/`，历史版本保存在各自版本目录。调试签名只供开发。v0.1.4→v0.1.5 同签名覆盖升级已在 V2405A 上保留“你好”草稿；正式签名、完整设置和回退仍待 A19 验收。
- 构建前自动运行 `tools/export_shared_assets.py` 从桌面权威资源同步角色资产；交付前运行 `python tools/export_shared_assets.py --check`，不要手改 `app/src/main/assets/shared/`。如 Python 命令不在系统路径，可设置个人环境变量 `PYTHON`。来源为固定 Avatar Lab 快照，见项目第三方来源记录。

## 当前能力和边界

- 打开 APK 只加载内置页面，不自动扫描、配对、录音、联网或发送旧任务。角色可在手机内选择 10 种形象并预览 23 条来源表情；Watch 形象固定 Gork，`happy-work` 是设备专属表情。
- Watch 页面由用户点击扫描并授权附近设备权限；只允许连接本次扫描候选。系统配对成功后发现表情、短音、音频三个 GATT 服务、协商 MTU 并订阅通知，完成后才显示 READY。基础命令包括表情、文字、清屏、六种短音、音量和停止。v0.1.1 增加手工 WAV→Watch PCM 实验；v0.1.2 增加本机 TTS 完整文件导出、PCM16 格式转换、最多三包在途的 ACK 窗口和同轮 COMMIT→文字→PLAY 候选。Android GATT 写入仍逐次等待回调；设备进度只按 ACK 推进。普通命令也同时等待写入回调和设备回执。尚无 Opus、AI、云服务或真实手机验收。
- 当前固件只保存一个可信控制端。手机首次接管前，需先明确允许当前 Watch 暂离电脑，并在设备设置中清绑定、打开 Pair。恢复电脑也需要反向迁移。APK 不提供隐式清绑定或放宽身份校验。
- 手机朗读和文件导出只选择系统报告为不需要网络的中文音色，需用户点击后才执行；这不代表目标 vivo 已安装可用音色。导出文件仅存应用私有缓存，读取与转换后立即清理，重启时清理残留。本机 TTS→Watch 仍是实验入口，文字限 24 字/72 UTF-8 字节；超过 10 秒明确拒绝，不裁剪。按住说话只调用 Android 设备端识别入口，首次请求麦克风权限，松开结束采集；结果仅填入草稿，不自动发往 Watch 或 AI。识别器存在不代表中文模型可用，须在目标手机断网核查。AI、云 ASR/TTS、Opus、后台前台服务和悬浮伴侣仍按任务书后续阶段实施。设备 `PLAYED` 回执不能替代实际听验。
- 文字 AI 使用用户输入的 HTTPS Chat Completions 地址、模型和个人 Key；新安装四项上传许可均关闭，点击发送且提问许可已开启才允许请求。Key 在 Android Keystore 下加密保存，桥只返回是否配置，不回显 Key；撤销许可或停止取消在途请求。云 ASR/TTS 入口尚未接通，真实云回答未测试。
- 页面桥固定 APK 本地 origin 和主 frame，阻止外部网页与任意网络加载；偏好保存在应用私有目录且排除备份。桥接口和 BLE 字节契约见 `docs/协议与桥契约-v0.1.4-【codex】.md`。

## 测试状态

本机 Gradle 构建、13 项桥/协议/WAV 转换、音频窗口及云地址校验单测、资产一致性检查已执行；v0.1.5 手机结果见项目 `04-output/android/v0.1.5/手机安装与本机语音实测记录-【codex】.md`。该手机设备端 ASR 不可用；本机 TTS 文件导出成功，用户确认手机朗读“你好”可闻。Watch GATT、设备回执、真实云请求和其余验收仍不能由本机检查替代。
