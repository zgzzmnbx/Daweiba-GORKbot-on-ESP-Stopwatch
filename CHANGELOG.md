# CHANGELOG

> 仅保留最近 5 个版本；更早记录转入 `CHANGELOG-历史归档.md`。

## Android v0.1.7-dev - 2026-09-27（手机 BLE 扫描与真机控制）

- Android versionCode 8；为不用于定位的 `BLUETOOTH_SCAN` 补齐官方 `neverForLocation` 声明。13 项单测、构建与 Lint 通过；用户本人确认 vivo 安全守护后同签名覆盖安装。
- 用户在 Watch 清旧绑定后，手机发现设备并完成系统配对、三服务发现和通知订阅；用户看到表情与“你好”文字、听到短音 1，并确认 Watch 朗读“你好”完整清楚。系统默认勾选的通讯录同步已在手机蓝牙设备详情关闭。详见 `04-output/android/v0.1.7/BLE配对与基础控制实测-【codex】.md`。

## Android v0.1.6-dev - 2026-09-27（BLE 扫描过滤诊断）

- Android versionCode 7；移除扫描器 UUID 过滤，仍只收录 Gork 名称或目标服务 UUID。13 项单测、构建与 Lint 通过，同签名安装；Pair 窗口及近距离复测仍未发现设备。诊断构建显示 8 秒内 0 条 BLE 扫描回调，促成 v0.1.7 权限声明修复。详见 `04-output/android/v0.1.6/BLE扫描修正与手机待验记录-【codex】.md`。

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
