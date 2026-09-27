# CHANGELOG

> 仅保留最近 5 个版本；更早记录转入 `CHANGELOG-历史归档.md`。

## Android v0.1.3-dev - 2026-09-27（设备端中文 ASR 源码候选）

- Android versionCode 4；按住说话只使用系统设备端 SpeechRecognizer，不回退到可能联网的识别器；显式麦克风权限、松开结束、取消/后台/页面重载销毁及 30 秒超时，结果仅填入草稿。
- 12 项既有单测、构建、Lint 与资源一致性通过；目标手机中文模型、断网转写、权限/来电中断及安装升级未验收。详见 `04-output/android/v0.1.3/设备端ASR源码候选实施记录-【codex】.md`。



## Android v0.1.2-dev - 2026-09-27（本机 TTS 与 Watch 文字时序候选）

- Android versionCode 3；系统声明无需网络的中文音色可异步导出完整音频，应用私有缓存内校验 PCM16 WAV、混声道和采样率转换，超时/停止/重启清理文件；超出 10 秒拒绝，不静默裁剪。
- 本机合成→Watch PCM 的源码路径在同一 BLE 任务中执行 COMMIT→对应文字 F0/F1/F2→PLAY；最多三包音频在途，底层 GATT 写入串行，进度只按设备 ACK 推进；基础指令同时等待写入回调和设备回执。12 项桥/协议/WAV/窗口单测、构建、Lint 和资源检查通过；APK v2 签名验证。ADB 无手机，未安装、换绑或听验；ASR/AI/Opus 与后台服务待实施。详见 `04-output/android/v0.1.2/本机TTS与Watch时序实施记录-【codex】.md`。

## Android v0.1.1-dev - 2026-09-27（Watch PCM 实验候选）

- Android versionCode 2；增加手选 WAV 的严格 PCM16 单声道 16/24 kHz、0.1–10 秒校验和同一 GATT 上的 HELLO/BEGIN/DATA/COMMIT/PLAY/PLAYED 链路；只按设备 ACK 推进，支持限时与中止。
- 8 项桥/协议/WAV 单测、构建、Lint 和资源检查通过；页面重载停止旧 BLE 任务并校验桥代际号；调试 APK v2 签名验证。ADB 无手机，未安装、换绑或听验；Opus、TTS/AI 自动闭环与后台服务仍待实施。记录见 `04-output/android/v0.1.1/PCM实验实施与验收记录-【codex】.md`。

## Android v0.1.0-dev - 2026-09-27（手机基础控制调试候选）

- 新建独立 Gradle Wrapper / Kotlin / WebView 工程；共用 Gork 角色资源，四标签页面、10 形象与 23 来源表情预览、本机文字与偏好保存。
- 原生 BLE 扫描、系统配对、三服务发现与通知订阅、表情/文字/清屏/短音/音量基础指令代码候选；系统本地中文音色探测与显式朗读。现有 Watch 单绑定要求仍保留，不自动迁移或放宽认证。
- 标准 Wrapper 构建、3 项跨语言协议单测、资产一致性、Lint 0 error 和浏览器 360/390/412 dp 及横屏替身检查通过；调试 APK v2 签名验证通过。ADB 无手机，未安装、换绑或验收真实 BLE/声音，版本保持候选。详见 `04-output/android/v0.1.0/开发基线与验收记录-【codex】.md`。

## v0.15.0-dev - 2026-09-26（Mantine 全界面与经典主题）

- 2026-09-27 文档补充：新增 Gork Android 手机端 PRD 24、任务书 25（文档 v1.0.0），规划独立 APK、原生 BLE/音频、分阶段版本及 23 组验收用例；同步 README/当前计划/AGENTS。仅规划，未启动 Android 开发或改变桌面/固件版本；换绑、云调用及实机门禁明确保留。
- Mantine 9.6.2 统一六页按钮、开关、选择器、文本框、状态标记与面板；保留常驻机器人和右侧标签布局，轻量输入区、自适应窗口。
- 顶部按钮即时切换 Mantine / 经典主题，偏好持久化；原 `style.css` 保留，DOM、输入、聊天、连接和动画实例不重建。
- 正式 Mantine 组件构建时预渲染，全部资源本地交付，沿用已有业务控制器；外置生成 CSS 保持严格 CSP，不引入运行期 CDN。
- 78 项 Node 回归、构建一致性与响应式网页检查通过；正式客户端未重启，语音/设备实机待验，固件不变。
