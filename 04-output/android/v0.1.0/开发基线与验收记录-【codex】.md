# Gork Android v0.1.0-dev 开发基线与验收记录

日期：2026-09-27。状态：**调试候选，未达到 v0.1.0 真机发布门禁**。

## 本次实施

- 新建独立 Gradle Wrapper 工程 `03-Src/gork-android/`，包名 `com.daweiba.gork`（闪念源码包名为 `com.dabawei.flashnote`）。JDK 17.0.19；本机已装 Android SDK API 35、Build Tools 35.0.0、ADB。固定 Gradle 8.13、AGP 8.13.2、Kotlin 2.2.20、WebKit 1.17.1；minSdk 31、targetSdk/compileSdk 35、versionCode 1、versionName `0.1.0-dev`。SDK 路径和代理只在本机忽略配置/环境变量中。
- 手机内置四标签页面、Gork 共用角色资产、10 个手机形象、23 条来源表情预览、本机文字显示与偏好。Watch 页提供扫描、系统配对、连接、表情/文字/清屏、六种短音、音量与停止的**代码候选**。设备 READY 必须等三服务和通知订阅成功；当前固件单绑定，连接前页面说明迁移影响且要求用户勾选。
- 内置受限 WebView 消息桥（精确本地 origin、主 frame、16 KiB、方法白名单）、应用私有偏好与备份排除。手机系统中文 TTS 仅选报告为无需网络的音色，需点击检测/朗读；目标手机音色未探测。无云 Provider、录音、Watch 动态音频发送或后台服务。
- APK：[Gork-Android-v0.1.0-dev-debug-【codex】.apk](Gork-Android-v0.1.0-dev-debug-【codex】.apk)，为调试签名候选，未安装至手机。
- 安装、同签名升级和回退条件见 [安装升级与回退说明](安装升级与回退说明-【codex】.md)；命令未在目标手机执行。

## 本机事实与验证

| 项目 | 结果 |
|---|---|
| 手机 | `adb devices -l` 无已连接设备；vivo 实际型号、Android/OriginOS/WebView、ABI、BLE、语音引擎均未取得，记 BLOCKED。 |
| 构建 | 在 Android 模块运行 `gradlew.bat --no-daemon :app:testDebugUnitTest :app:assembleDebug :app:lintDebug --console=plain`，最终退出码 0。代理仅在调用进程 `JAVA_OPTS` 与忽略的 Gradle 用户目录中配置。 |
| 协议 | 3 项 JVM 测试通过，覆盖 Python 导出的 UTF-8 分包、短音与音频小端金向量和非法边界；不能代替设备回执。 |
| 静态 | `node --check app/src/main/assets/mobile.js` 通过；`python tools/export_shared_assets.py --check` 通过。Android Lint 0 error、10 warning；旧版目标 SDK、必要 JS、本地化等提示不作为设备验收。 |
| APK | `apksigner verify --verbose`：v2 签名验证通过、1 个签名者；`aapt dump badging` 对构建目录的 ASCII 文件确认 applicationId、versionCode/name 与 SDK。Windows `aapt` 无法读取带中文后缀的副本路径，已在同构建原始 APK 核对，副本由 Copy-Item 直接生成。 |
| 浏览器替身 | Playwright 设定 360×640、390×844、412×540、844×390 视口；`documentElement.scrollWidth == innerWidth`，底部导航可见。390×844 实际点击本机文字显示与角色页，确认 10 形象和 23 来源表情清单；Watch 未就绪控制禁用。此为浏览器离线替身，不等于 Android WebView/键盘/系统字体实测。 |

## 任务与验收状态

- T00：工程和环境基线已完成；目标手机信息 BLOCKED。T01：跨语言帧和桥接口候选完成，generation、eventSeq、取消代际及更广负例未收口。T02：APK 页面候选完成，真实 WebView/键盘/旋转及升级未验。T03：原生 BLE 状态机候选完成，真实权限、绑定、三服务发现与回执均 BLOCKED。T04：基础控制候选已构建；A01–A11、A17–A20 的手机/Watch 项均未 PASS。
- T05：仅本机中文 TTS 探测/显式朗读代码候选；真实 ASR、可导出音频 TTS、AI Provider、上传许可、凭据存储 NOT_STARTED。T06–T08 NOT_STARTED。T09：候选 APK、签名核验与记录部分完成；正式签名/安装升级/回退和 G4 发布未完成。
- A01 安装、A02 离线手机蓝牙控制、A03 Android WebView 响应式、A04 全形象×表情自动走完、A05 重建/升级持久化、A06–A11 真机、A17–A20 真实链路，均为 NOT_RUN/BLOCKED；上述浏览器替身不记 PASS。A12–A16、A21–A22 属后续版本，NOT_RUN。A23 桌面回归待共享变更时执行；本轮未修改桌面/固件源码。

## 迁移与恢复清单（未执行）

1. 核实手机和 Watch 在场，记录手机系统版本；电脑手动断开 Watch 并暂停 Gork 自动重连。
2. 在 Watch 本地设置中显式清除旧绑定并打开 Pair；手机在 APK 内扫描、选择候选，人工接受系统配对弹窗。三个 GATT 服务及通知订阅成功才以最小表情/文字指令验链。
3. 恢复电脑时手机手动断开；Watch 再次本地清绑定并打开 Pair，使用现有电脑恢复流程配对；以服务发现和最小命令确认，而非仅看系统配对状态。若手机需要重新接管，再重复人工迁移。

迁移会暂时中断电脑控制，尚待用户明确允许当次换绑范围。未作固件写入、Windows 服务重启、云调用、手机安装或配对修改。目标手机接入后，应先执行 A01/A03/A06，再按迁移清单做 A07–A11，并记录用户对短音/朗读的实际听验。
