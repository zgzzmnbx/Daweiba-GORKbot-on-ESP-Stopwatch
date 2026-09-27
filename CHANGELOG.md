# CHANGELOG

> 仅保留最近 5 个版本；更早记录转入 `CHANGELOG-历史归档.md`。

## Android v0.1.5-dev - 2026-09-27（手机权限修复与首次实测）

- Android versionCode 6；设备端 ASR 服务不可用时先返回错误，不再无谓申请麦克风权限。13 项单测、构建、Lint、资源检查及 APK v2 签名验证通过。
- V2405A / Android 16 首次安装 v0.1.4 并由用户确认 vivo 安全守护后同签名升级 v0.1.5；“你好”草稿保留。本机中文 TTS 完整文件导出成功，设备端 ASR 不可用，撤销权限后无新弹窗且已恢复原授权。Watch 与云端未实测，用户要求暂停新增功能。详见 `04-output/android/v0.1.5/手机安装与本机语音实测记录-【codex】.md`。
- 用户随后补充听验：手机朗读“你好”可闻；清晰度、其他语句及 Watch 朗读不由这次反馈判定。

## Android v0.1.4-dev - 2026-09-27（文字 AI 与上传许可源码候选）

- Android versionCode 5；增加用户配置的 HTTPS Chat Completions 文字 AI、Android Keystore 加密个人 Key 和四项独立许可。AI 需显式开启提问上传并点击发送；撤销、停止或进入后台取消在途任务，回复只作纯文本展示，不自动发 Watch。
- 13 项单测、构建、Lint、资源检查及 APK v2 签名验证通过。ADB 无手机，未安装、配置个人 Key、调用真实云服务或换绑；云 ASR/TTS、Opus、后台服务和正式签名仍待实施。详见 `04-output/android/v0.1.4/文字AI与上传许可源码候选实施记录-【codex】.md`。



## Android v0.1.3-dev - 2026-09-27（设备端中文 ASR 源码候选）

- Android versionCode 4；按住说话只使用系统设备端 SpeechRecognizer，不回退到可能联网的识别器；显式麦克风权限、松开结束、取消/后台/页面重载销毁及 30 秒超时，结果仅填入草稿。
- 12 项既有单测、构建、Lint 与资源一致性通过；目标手机中文模型、断网转写、权限/来电中断及安装升级未验收。详见 `04-output/android/v0.1.3/设备端ASR源码候选实施记录-【codex】.md`。



## Android v0.1.2-dev - 2026-09-27（本机 TTS 与 Watch 文字时序候选）

- Android versionCode 3；系统声明无需网络的中文音色可异步导出完整音频，应用私有缓存内校验 PCM16 WAV、混声道和采样率转换，超时/停止/重启清理文件；超出 10 秒拒绝，不静默裁剪。
- 本机合成→Watch PCM 的源码路径在同一 BLE 任务中执行 COMMIT→对应文字 F0/F1/F2→PLAY；最多三包音频在途，底层 GATT 写入串行，进度只按设备 ACK 推进；基础指令同时等待写入回调和设备回执。12 项桥/协议/WAV/窗口单测、构建、Lint 和资源检查通过；APK v2 签名验证。ADB 无手机，未安装、换绑或听验；ASR/AI/Opus 与后台服务待实施。详见 `04-output/android/v0.1.2/本机TTS与Watch时序实施记录-【codex】.md`。

## Android v0.1.1-dev - 2026-09-27（Watch PCM 实验候选）

- Android versionCode 2；增加手选 WAV 的严格 PCM16 单声道 16/24 kHz、0.1–10 秒校验和同一 GATT 上的 HELLO/BEGIN/DATA/COMMIT/PLAY/PLAYED 链路；只按设备 ACK 推进，支持限时与中止。
- 8 项桥/协议/WAV 单测、构建、Lint 和资源检查通过；页面重载停止旧 BLE 任务并校验桥代际号；调试 APK v2 签名验证。ADB 无手机，未安装、换绑或听验；Opus、TTS/AI 自动闭环与后台服务仍待实施。记录见 `04-output/android/v0.1.1/PCM实验实施与验收记录-【codex】.md`。
