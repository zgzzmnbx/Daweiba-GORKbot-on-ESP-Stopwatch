# Gork Android v0.1.4-dev 文字 AI 与上传许可源码候选实施记录

日期：2026-09-27。Android `versionCode=5`、`versionName=0.1.4-dev`。v0.1.3 APK 保存在相邻目录。本轮未安装 APK、配置或使用任何个人凭据、调用云端、迁移 Watch 绑定或写固件。

## 实施内容

- 增加用户配置的 HTTPS Chat Completions 文字 AI 通道，默认地址参考项目既有阿里云百炼接口；模型名、地址和读取超时可改。按钮只发送当前输入的文字，响应以纯文本显示，不自动发往 Watch、语音或其他模块。请求最多 300 字/1200 UTF-8 字节，返回最多 1000 字；过长回答不会静默裁剪进入 300 字输入框。
- 个人 API Key 仅经原生桥提交，用 Android Keystore AES-GCM 加密写入应用私有首选项。页面只能查询 `hasKey`，不回显密钥；应用已关闭云备份和设备迁移。网络请求在原生层执行，网页 CSP 仍禁止直接联网。无硬编码 Key、无请求/响应正文日志。
- 四项许可分别控制 AI 提问文字、录音、待合成文字、AI 回答文字；默认全部关闭。后三项尚无云 ASR/TTS 入口，不能视为已接通。用户点击 AI 按钮且提问上传许可和 Key 齐备时才发起网络请求；撤销许可、清除 Key、停止、页面卸载或进入后台取消在途请求并丢弃迟到结果。HTTP 非 200 只返回状态码；不回传服务端错误正文。
- 请求使用系统 HTTPS 证书校验、禁止重定向、10 秒连接超时、可配置 10–60 秒读取超时和 64 KiB 响应上限。可配置地址必须为 HTTPS，禁止 URL 用户信息、查询参数与片段。协议依据：[阿里云百炼兼容接口](https://help.aliyun.com/en/model-studio/compatibility-of-openai-with-dashscope)；密钥方案依据：[Android Keystore](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec)。

## 本机验证

| 项目 | 结果 |
|---|---|
| Gradle | `:app:testDebugUnitTest :app:assembleDebug :app:lintDebug --offline --no-daemon` 成功；13 项单测、0 失败；Lint 任务通过。新增单测覆盖 HTTPS 地址与禁止凭据/查询参数。 |
| 静态 | `node --check app/src/main/assets/mobile.js`、共享角色资产 `export_shared_assets.py --check` 通过。 |
| APK | [Gork Android v0.1.4-dev 调试包](Gork-Android-v0.1.4-dev-debug-【codex】.apk)：APK v2 签名验证通过，1 个调试签名者；`aapt` 确认包名 `com.daweiba.gork`、versionCode 5、minSdk 31、targetSdk 35 与 `INTERNET` 权限。 |
| 真机/云端 | `adb devices -l` 无设备；未安装、未填写 Key 或发送真实请求。A13 及其他真实手机/Watch 项目均未 PASS。 |

## 下一步及限制

1. 目标手机接入后，在用户提供个人 Provider 配置并明确同意测试的条件下验证无 Key、关闭许可、真实回答、断网、401/429、超时与撤销；检查系统日志不含 Key、提问和回答。不能用本机构建替代 A13。
2. T05 的云 ASR/TTS、录音/焦点/来电处理和完整音频文件，T06 Opus、T07 后台服务、T08 悬浮伴侣仍未完成。当前本机 TTS/ASR 路径是否在目标 vivo 可用也待实测。
3. Watch 仍只保存一个可信控制端；切换电脑/手机必须按任务书现场迁移并保留恢复路径。A01–A23 尚无真实设备 PASS，v0.2.0 和 v0.3.0 均未达到退出条件。
