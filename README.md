# M5Stack StopWatch 嵌入式开发项目

> 当前源码版本：v0.5.0；设备应用区：v0.5.0（已写入并读回校验，运行效果待验收）
> 初始化日期：2026-09-16

## 1. 项目概况

- 项目类型：轻量嵌入式软件开发项目
- 目标硬件：M5Stack StopWatch（SKU：C152）
- 当前使用对象：石萌（大尾巴）
- 当前目标：保留 StopWatch 已验证的硬件控制底座，以大尾巴导出的 Bible Strong `Grok bot` 为视觉和动画数据源；v0.3.0 加入受绑定保护的 BLE 表情控制，v0.4.0 增加 `happy-work`，v0.5.0 增加 BLE 文字聊天气泡。源码与设备版本分别记录，不把构建视为设备已更新。
- 最终交付物：可维护源码、可复现构建环境、Grok 风格几何资产、固件构建产物、测试记录、恢复说明和使用文档。

## 2. 当前状态

- 当前源码版本：v0.5.0，新增 BLE 控制台 `:say 文字` 和 `:clear`，在角色上方显示两行、10 秒自动消失的聊天气泡；含 v0.4.0 `happy-work`。21 项 Python 测试与 PlatformIO 构建通过，固件已归档；设备应用区已写入并读回校验。
- 当前阶段：v0.5.0 待真机中文显示、气泡残影、BLE 链路和帧率验收；v0.3.0 BLE 的安全负向、压力和长期稳定性门禁仍未关闭。
- 视觉基准：Bible Strong Avatar Lab 的 **Grok bot**，以大尾巴下载的 Studio 导出为正式数据快照，并与仓库提交 `79fe9ba06e4874b11394b8e8a3f2c493c9d197ba` 比对；27 个表情预设和 23 条动画序列已转为可编译固件表。桌面预览和编译通过不等于真机视觉通过。
- 当前主线任务：按 `00-docs/00-PRD/09-v0.5.0-BLE文字聊天气泡-【codex】.md` 验收文字气泡，连同 v0.4.0 新表情一并完成实物验收，再继续完成 v0.3.0 BLE 的 G4 门禁。
- v0.5.0 固件与记录：`04-output/v0.5.0/firmware/firmware-v0.5.0-ble-chat-bubble.bin`、`04-output/v0.5.0/实施与验收记录-【codex】.md`。
- v0.4.0 固件与记录：`04-output/v0.4.0/firmware/firmware-v0.4.0-happy-work.bin`、`04-output/v0.4.0/实施与验收记录-【codex】.md`。
- 当前进展：v0.2.1 数据、预览、11 项测试及构建已完成；目标设备已重新识别，应用区写入和读回校验通过，详见 `04-output/v0.2.1/G4-写入与验收记录-【codex】.md`。
- 当前最重要的问题：真机照片已证明黑体白眼目标方向，修正版待机已测到 60 FPS，但所有表情的逐帧视觉、外设交互和 30 分钟稳定性仍未完成。
- 下一步优先事项：实测 `:say` 中文气泡及 `happy-work` 的观感、残影和帧率；随后补做 BLE 未绑定端拒绝、重连、延迟、稳定性与 USB 回退验收。

## 3. 项目启动摘要

- 启动澄清日期：2026-09-16
- 已确认的项目类型：开发类——轻量嵌入式软件开发
- 已确认的阶段交付物：标准项目结构、项目上下文、硬件知识基线、可编译 KK/Grok Avatar 原型、当前版本计划
- 已确认的质量标准：资料以官方文档和本机实测为依据；明确区分官方规格、本机观察和推断；烧录前完成设备识别及恢复路径确认，烧录后不把构建结果冒充真机验收
- 已确认的验证方式：目录/文件静态检查、链接检查、Windows USB/串口枚举、芯片/Flash 读写校验；继续补充屏幕、触摸、按键、振动、IMU、串口和稳定性验证
- 已确认的应用与技术路线：Grok 风格表情机器人；PlatformIO/Arduino + M5Unified；以 KK StopWatch Avatar 为底座；个人、非商业、本地使用 Grok 参考资产。
- 仍需确认的问题：实物贴纸硬件版本、真机功能与稳定性结果，以及后续是否加入联网语音能力。

## 4. 当前设备连接快照

2026-09-16 在 Windows 上读取到与 ESP32-S3 原生 USB 接口相符的设备：

| 项目 | 当前结果 |
| --- | --- |
| 串口 | `COM5` |
| USB VID/PID | `303A:1001` |
| 总线描述 | `USB JTAG/serial debug unit` |
| 设备状态 | `Started`，问题码 `0` |
| USB 标识 | `28:84:85:44:6C:00` |
| 芯片级识别 | ESP32-S3 rev `v0.2`；Flash ID `20:4018`；16MB Flash；8MB PSRAM |
| 写后状态 | 四段目标区域 `verify OK (digest matched)`；安全启动和 Flash 加密均关闭 |
| 判断边界 | 芯片命令不能读取 StopWatch 贴纸版本，仍不能区分 v1.0 的 `BAT/5V IN` 标识差异 |

端口号会随电脑、USB口和驱动状态变化，任何脚本都不得把 `COM5` 当作永久配置。

## 5. 当前开发环境

2026-09-16 本机检查结果：

- Python：已安装
- M5Burner：已安装，桌面程序版本 `3.0.0`，在线界面版本 `v202605221800`
- M5Burner 安装目录：`C:\Users\zgzzm\AppData\Local\Programs\M5Burner`
- 开始菜单快捷方式：已创建 `M5Burner`
- Arduino CLI：未发现
- PlatformIO：项目隔离环境已安装 Core `6.1.18`；系统 PATH 未承诺全局安装
- ESP-IDF `idf.py`：未发现
- 独立 esptool：PATH 中未发现；M5Burner 内置烧录工具

M5Burner 已具备图形化烧录准备条件；v0.2.0 使用项目隔离的 PlatformIO/Arduino 工具链，原版和最终 Grok 固件均已在本机完成构建，并通过 PlatformIO 写入目标设备。

### M5Burner 安装核验

| 项目 | 核验结果 |
| --- | --- |
| 官方下载包 | `M5Burner-v3-beta-win-x64.zip`，来自 M5Stack 官方 CDN |
| ZIP SHA-256 | `818A4983C87BF58F1ABAB077DB3F5BB3EC0C279468648300CEF9362FA9D2C69B` |
| 主程序 | `M5Burner.exe`；内部桌面程序 `bin/m5burner.exe` 文件版本 `3.0.0` |
| 签名边界 | M5Burner 主程序未带 Authenticode 签名；内置 `esptool.exe` 的 Espressif 签名有效 |
| 安全扫描 | Windows Defender 自定义扫描完成，未发现该安装包目录相关威胁 |
| 启动验证 | 程序正常启动，在线固件目录加载成功，左侧存在 `STOPWATCH` 分类 |
| 串口验证 | `USB\VID_303A&PID_1001` 当前为 `COM5`，状态 `Started`，驱动 `usbser.inf` |
| 写入状态 | v0.2.0 已通过 PlatformIO 写入；未执行整片擦除、eFuse、安全启动或 Flash 加密 |

## 6. 目录说明

- `AGENTS.md`：本项目专属协作、安全和验证规则。
- `CHANGELOG.md`：最近版本变更记录，最多保留 5 个版本。
- `00-docs/00-PRD/`：产品总览、当前版本计划和验收口径。
- `01-assets/design/`：界面设计稿、图标和视觉资产。
- `01-assets/bug/`：故障截图、复现视频和异常证据。
- `01-assets/reference/`：官方资料、参考设计和资料索引。
- `02-notes/`：硬件知识、开发笔记和问题记录。
- `03-Src/`：源码、配置、测试和业务实现。
- `04-output/`：固件、发布包和阶段交付物。
- `Codex-Temp/`：缓存、编译中间物和临时测试产物。
- `tools/`：项目维护、验证、USB 串口控制台、BLE 控制台和辅助脚本。

## 7. 开发类项目上下文

- 技术栈：PlatformIO Core `6.1.18` + Arduino；依赖锁定为 M5Unified `774d920cd6851a5231748b56ece1b073645f313f`、M5GFX `93b480bb349749202c8a2a953065c8ae95f58320`、M5PM1 `be9a5456c007c333e7ac963f33bfde1ffa5d82ee`、M5IOE1 `846eec7d05e25c09013be2acdb8804487f48a62e`。
- 运行方式：ESP32-S3 固件运行于 M5Stack StopWatch
- 测试方式：静态检查 → 编译 → USB/JTAG/串口识别 → 烧录 → 屏幕/触摸/按键/振动/音频/IMU/RTC/电源分项验证
- 关键模块：显示与触摸、输入、音频、传感器、RTC、电源管理、无线通信、扩展接口
- 依赖说明：官方 Arduino 路线使用 M5Unified、M5GFX、M5PM1、M5IOE1；官方出厂演示使用 ESP-IDF 5.5.4
- 测试输入位置：后续放入 `03-Src/tests/` 或对应固件工程测试目录
- 预期输出位置：`04-output/`
- 实际输出位置：`04-output/v0.2.0/firmware/`，包含 v0.2.0 固件、ELF、MAP、bootloader 和分区镜像

## 8. 关键资料

- [M5Stack StopWatch 产品文档](https://docs.m5stack.com/zh_CN/core/StopWatch)
- [StopWatch Arduino 编译与烧录教程](https://docs.m5stack.com/zh_CN/arduino/stopwatch/program)
- [UIFlow2 Web 使用说明](https://docs.m5stack.com/zh_CN/uiflow2/uiflow_web)
- [StopWatch UIFlow2 编程与烧录说明](https://docs.m5stack.com/zh_CN/uiflow2/stopwatch/program)
- [M5Stack 官方下载页](https://docs.m5stack.com/en/download)
- [M5Unified](https://github.com/m5stack/M5Unified)
- [M5GFX](https://github.com/m5stack/M5GFX)
- [M5StopWatch 官方出厂演示工程](https://github.com/m5stack/M5StopWatch-UserDemo)
- [KK StopWatch Avatar 工程底座](https://github.com/Trentct/m5stack-stopwatch-avatar)，锁定提交 `204963257cb4dc2f3d7501eff900897bac55ef82`
- [Grok Icon Study 几何参考](https://github.com/blessonism/grok-icon-study)，锁定提交 `647e9bd7c60290c42a738fad586589b3f36a4680`
- [Bible Strong Avatar Lab / Grok bot 视觉基准](https://github.com/smontlouis/bible-strong-avatar-lab)，v0.2.1 计划锁定提交 `79fe9ba06e4874b11394b8e8a3f2c493c9d197ba`；v0.2.0 的 Grok Icon Study 仍保留为历史实现来源
- 本项目知识基线：`02-notes/01-M5Stack-StopWatch-硬件与开发知识基线-【codex】.md`
- 本项目资料索引：`01-assets/reference/README.md`
- 产品总览：`00-docs/00-PRD/01-产品总览PRD.md`
- 当前版本计划：`00-docs/00-PRD/02-当前版本计划.md`
- v0.2.0 详细 PRD：`00-docs/00-PRD/03-v0.2.0-KK-Grok-Avatar开发PRD-【codex】.md`
- Luna Max 目标模式任务书：`00-docs/00-PRD/04-Luna-Max目标模式开发任务书-【codex】.md`
- v0.2.0 实施进度与验收记录：`00-docs/00-PRD/05-v0.2.0实施进度与验收记录-【codex】.md`
- v0.2.1 Grok bot 视觉对齐方案：`00-docs/00-PRD/06-v0.2.1-Grok-bot视觉对齐方案-【codex】.md`
- 大尾巴的 Grok bot 导出：`01-assets/design/Gorkbot-avatars.bible-strong.app/`；正式输入快照：`03-Src/stopwatch-grok-avatar/assets/source-grok-bot/avatar-studio-project.json`

## 9. 已完成内容

- 建立轻量软件开发项目目录。
- 建立 README、项目 AGENTS、CHANGELOG 和 PRD。
- 记录官方硬件规格、主要管脚、开发路线和高风险版本差异。
- 记录当前 Windows USB/JTAG/串口枚举结果。
- 安装并启动 M5Burner v3.0，建立开始菜单快捷方式。
- 完成下载包哈希、程序版本、签名边界、Defender 扫描和串口在线核验。
- 完整读取当前设备 16MB SPI Flash，保存原始镜像、设备信息、校验值、恢复说明和受保护恢复脚本。
- 首次写入前使用 esptool `verify_flash` 将完整镜像与设备比较，结果为 `verify OK (digest matched)`。
- v0.2.0 写入后再次对 bootloader、分区表、`boot_app0` 和应用逐段 `verify_flash`，均为 `verify OK (digest matched)`。
- v0.2.0 写入前已完整保存当前 Flash；该镜像现作为 v0.1.1 恢复点保留。
- 按锁定提交导入 KK 工程，建立 `kk-grok-v0.2.0` 分支和上游来源记录。
- 完成 Grok 几何源数据的确定性转换、8 个实现眼组映射、12 状态 SVG/HTML 预览、浏览器视觉检查和负向测试。
- 完成 Grok 固件渲染器接入、dirty rectangle、几何点数/最大 dirty 面积/全屏退化指标，以及清理后的最终构建。
- 已生成 v0.2.0 固件、ELF、MAP、bootloader、分区镜像、SHA-256、测试日志、视觉证据和 G3 报告。

### 当前状态恢复点

- 目录：`04-output/backups/2026-09-16-StopWatch-current-state-v0.1.1/`
- 镜像：`StopWatch-current-fullflash-16MB-20260916.bin`
- 大小：`16777216` 字节
- SHA-256：`ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B`
- 验证：v0.2.0 写入前与设备完整 Flash 摘要匹配；作为回退点保留
- 覆盖范围：完整 SPI Flash；不包含 eFuse、RTC 实时时钟寄存器、运行时 RAM 或外接存储
- 第二副本：`C:\Users\zgzzm\Documents\M5Stack-Backups\2026-09-16-StopWatch-current-state-v0.1.1\`，镜像 SHA-256 与项目副本一致
- 保密提示：完整 Flash 可能包含 Wi-Fi、Access Code 等配置，不上传公共仓库或公开分享

## 10. 下一步

1. 阅读 `04-output/v0.2.0/evidence/G3-device-preflight-20260916.txt`、`G4-flash-and-verify-20260916.txt` 和完整证据。
2. 由大尾巴在设备上确认启动画面、触摸、A/B 键、振动和 IMU；串口性能与 30 分钟稳定性另行记录。
3. 如需恢复，使用 `04-output/backups/2026-09-16-StopWatch-current-state-v0.1.1/` 中的 v0.1.1 完整镜像，并再次执行单独的整片写入确认。
4. v0.2.1 数据转换、桌面首帧预览、构建及应用区写入/读回已完成；下一步是真机视觉和交互验收。

### v0.2.1 执行进度（2026-09-16）

- 已用大尾巴的 Studio 导出生成 23 条固件动画数据，新增 Grok bot 角色渲染，并保留原 StopWatch 硬件输入、供电和局部刷新链路。
- 已生成 23 条动画首帧桌面总览；Python 数据测试 11 项通过；PlatformIO 固件构建成功。首版 890016 字节已归档为 `-initial`；当前设备修正版 890352 字节，SHA-256 `A6832890B5613A8523456A2AC73972DE3A55E3A8ED249FE690B391A9C7F761D1`。
- 新旧 bootloader 和分区表哈希相同，后续只需写入 `0x10000` 应用区；未执行整片擦除。
- 设备进入下载模式后枚举到 COM5、`303A:1001`、MAC `28:84:85:44:6C:00`；旧 v0.2.0 应用区写前校验通过，v0.2.1 修正版应用区写入和读回校验通过；**完整视觉、全部场景性能和外设仍未验收**。
- 真机照片显示黑体白眼；首版 45–46 FPS，修正版待机 60 FPS，23/23 串口表情入口通过。外设和全部动画逐帧观感仍待验收。

### v0.2.2 自动返回待机修复（2026-09-17）

- 修正 v0.2.1 把全部 23 条动画都标为持续状态的问题：现在仅 `idle` 默认循环，其他 22 条触发后各播放一遍，再自动返回 `idle`；显式 `loop`/`pingpong` 不自动返回。
- 生成数据检查与 12 项 Python 测试通过，PlatformIO 构建成功；固件位于 `04-output/v0.2.2/firmware/`，SHA-256 与写入状态见 `04-output/v0.2.2/验收记录-【codex】.md`。
- 已核对 COM5、目标 MAC 与原备份；写前确认 v0.2.1 应用区匹配，v0.2.2 仅写 `0x10000` 应用区并读回通过。串口烟测时设备仍处下载模式，正常启动后的自动返回尚待验证。

### v0.2.3 亮度设置（2026-09-17）

- 原固件没有独立设置菜单，现将 A+B 长按打开的硬件诊断页作为 `Settings`，加入触屏 `−/+` 亮度调节；范围 30–255、步长 15、默认 150，NVS 保存重启恢复。
- 原诊断信息和 A/B 操作保留；数据生成检查、12 项测试和 PlatformIO 构建通过。固件及 SHA-256 见 `04-output/v0.2.3/亮度设置实施与验收记录-【codex】.md`。
- 本版独立固件未写入；其功能已随 v0.2.4 合并写入，真机触控、亮度变化与重启持久化未验收。

### v0.2.4 电量与调试模式（2026-09-17）

- A+B 长按进入的 `Settings` 首页新增电池电量估算显示与 `Debug mode` 开关；原硬件检查移到同入口的 `Hardware Check` 子页，保留原诊断能力。电量无有效读数时显示 `--`。
- 开启调试模式后，头像底部以小白字显示当前动画英文名；开关与亮度同样保存在 NVS。v0.2.3 独立固件未写入，其功能已合并进 v0.2.4。
- 已通过 12 项数据测试和 PlatformIO 构建；2026-09-17 核对设备后仅写入应用区，读回校验通过。固件、哈希与真机门禁见 `04-output/v0.2.4/电池与调试模式实施验收-【codex】.md`；视觉与电池读数未实测。

### v0.2.5 调试字样顶部定位（2026-09-17）

- 仅将调试开关打开时的表情英文名从头像底部移到顶部黑色圆体内；文字尺寸与开关逻辑不变。
- 12 项现有测试、数据生成检查及 PlatformIO 构建通过；当次核对设备 MAC 后只更新应用区，读回校验通过。文件 SHA-256 不再作为项目常规迭代门禁；记录见 `04-output/v0.2.5/写入与待验收记录-【codex】.md`。

### v0.2.6 Windows 表情串口控制台（2026-09-17）

- 双击 `tools/start-expression-console.cmd` 打开命令行窗口；自动识别 StopWatch 的 USB 串口，输入 `happy`、`loop happy`、`idle` 等命令，`:list` 查看全部表情，`:q` 退出。
- 实测 COM5/115200 发送 `happy`，设备返回 `Command accepted: HAPPY`；打开串口时设备曾正常重启，不能将启动日志当作命令失败。本次只新增本机工具，未改动或重烧设备固件。

### v0.2.7 v0.3.0 BLE 需求与 Luna Max 交接（2026-09-17）

- 新 PRD：`00-docs/00-PRD/07-v0.3.0-BLE表情操控开发PRD-【codex】.md`。方案采用 StopWatch BLE GATT 外设 + 本电脑内置 Intel 蓝牙/Bleak 客户端，不使用经典蓝牙虚拟串口或额外蓝牙棒。
- 本机蓝牙适配器、Windows BLE 枚举器、Python 3.14.3 与 Bleak 3.0.2 已检查；这只能证明电脑端具备实施条件，StopWatch 固件尚无 BLE 广播、配对或无线表情验收。
- PRD 固定通信协议、加密绑定、原 USB 回退、L0—L6 阶段与 G0—G5 验收；Luna Max 到 G3 写前报告须停下等待大尾巴当次烧录指令。本次仅写文档，不改固件、电脑配对或蓝牙配置。

### v0.3.0 BLE 表情控制实施并完成应用区写入（2026-09-17）

- 在正式 StopWatch 源码内新增 `src/ble_control.*` 和 Bluetooth 设置页：BLE 默认关闭，设备本地打开 120 秒 Pair 窗口，以 secure-connections bonding、加密 GATT 权限和单控制端绑定限制写入；USB、按键、触摸、IMU 和原表情语义保留。
- 新增 `tools/ble-expression-console.py`、双击启动脚本、锁定依赖和 mock GATT 测试；客户端按 Service UUID 扫描，不写死 BLE 地址或 COM 口。5 项客户端测试通过。
- L1 BLE API 探针和正式 PlatformIO 构建通过；正式镜像 RAM 62,544/327,680（19.1%）、Flash 1,538,485/6,553,600（23.5%）。证据和待验收项见 `04-output/v0.3.0/实施与验收记录-【codex】.md`。
- 已完成 G3 预检，并在用户明确“执行烧录”后仅写入 `0x10000` 应用区；写入 1,538,848 字节，写后 `verify_flash` 返回 `verify OK (digest matched)`。未整片擦除、未改 bootloader/分区表/eFuse/安全配置。
- 设备本地打开 `BLE ON` 并点击 `Pair` 后，电脑发现 `GorkBot-SW`（BLE 地址 `28:84:85:44:6C:01`）；`BleakClient(pair=True)` 连接、状态通知和 23/23 表情命令回执均通过，断开后再次扫描重连也通过。陌生端拒绝、10 次重连、P95/FPS、功耗和 30 分钟稳定性仍未宣称通过。

## 11. 蓝牙使用说明

v0.3.0 使用 BLE GATT 控制表情，不使用经典蓝牙虚拟串口，也不需要占用 USB COM 口。设备只接受完成加密绑定的控制端写入。

### 11.1 设备端准备

1. 长按 `A+B` 进入 `Settings`。
2. 进入 `Bluetooth`，打开 `BLE ON`。
3. 点击 `Pair`，开启约 120 秒的配对窗口。
4. 电脑连接成功后，点击 `Back` 返回表情页面。停留在 Bluetooth 设置页时发送命令会返回 `ERR:BUSY`，这是设备的菜单保护，不是配对失败。

### 11.2 Windows 控制台

在项目根目录双击 `tools/start-ble-expression-console.cmd`。首次运行会创建独立的 `.venv-ble` 环境并安装锁定版本的 Bleak；控制台会按 GATT Service UUID 查找 `GorkBot-SW`，不写死 BLE 地址。

看到“已连接；状态特征通知已订阅”后，在 `ble>` 提示符输入命令并回车：

```text
happy
thinking
sleepy
once celebrate
loop curious
pingpong happy
idle
:say 你好，今天加油！
:clear
```

- 直接输入表情名：播放一次后按默认规则返回 `idle`。
- `once <表情>`：明确播放一次。
- `loop <表情>`：持续循环播放。
- `pingpong <表情>`：往返播放。
- `:say <文字>`：v0.5.0 固件上的两行聊天气泡，10 秒后自动清除；最多 24 个可打印 BMP 字符且 UTF-8 不超过 72 字节，中文/英文可用，emoji 暂不支持。
- `:clear`：提前清除聊天气泡。客户端会自动把文字分包并逐包确认；设备已写入 v0.5.0，但实际显示仍待验收。更新控制台脚本后请重新打开窗口。
- `:list`：查看支持的表情；`:help`：查看帮助；`:q`：退出控制台。

### 11.3 常见问题

- **未发现 `GorkBot-SW`**：确认 Windows 蓝牙已开启，设备已打开 `BLE ON` 并重新点击 `Pair`；同时关闭其他占用该设备的 BLE 客户端。
- **返回 `ERR:BUSY`**：在设备上点击 `Back` 离开 `Settings → Bluetooth`，回到表情页面后再发送命令。
- **连接失败**：重新打开设备 Pair 窗口后再启动控制台；已绑定的控制端应使用同一台电脑。

## 12. 风险与待确认

- v1.0 部分批次贴纸把实际 `5V IN` 错印为 `BAT`，禁止在版本未确认前连接外部锂电池。
- `COM5` 只是本次连接快照，不是稳定设备标识。
- USB 枚举不能单独证明设备当前处于下载模式，也不能证明硬件版本。
- 当前状态完整备份已完成并有两份校验一致的副本；恢复操作仍属于整片写入，必须单独确认。
- M5Burner 主程序无 Authenticode 签名；本次仅以官方 CDN 来源、SHA-256 和 Defender 扫描作为安装证据。
- v0.2.0 不包含云端语音、账号系统、公开发布和量产；联网语音在后续版本另行立项。
- Grok 参考资产按大尾巴确认的个人、非商业、本地使用范围直接复制和转换，不作为开发阻塞项；工程代码按未来可开源维护，v0.2.0 不执行公开发布。

## 13. 线程交接记录

### 2026-09-16

- 线程目标：初始化 M5Stack StopWatch 项目并沉淀首批硬件知识。
- 已完成：项目骨架、上下文文件、知识基线、资料索引和 v0.1.0 计划。
- 修改文件：见 `CHANGELOG.md`。
- 验证方式：文件结构检查、UTF-8 内容检查、USB/串口枚举结果复核。
- 未完成：工具链安装、芯片级探测、固件工程、编译和烧录。
- 下个线程建议：先确认硬件版本和首个应用方向，再选择技术栈。

### 2026-09-16（M5Burner 准备）

- 线程目标：安装 M5Burner，并完成不写入设备的烧录前准备。
- 已完成：官方包下载与哈希、ZIP 路径安全检查、Defender 扫描、用户级安装、开始菜单快捷方式、启动与在线目录检查、`COM5` 复核。
- 验证方式：程序文件版本 `3.0.0`、界面版本 `v202605221800`、`STOPWATCH` 分类可见、USB 串口状态 `Started`。
- 未执行：固件下载、进入烧录对话框、Flash 擦除和固件写入。
- 下个线程建议：人工确认硬件版本和恢复策略；得到首次烧录授权后再继续。

### 2026-09-16（当前状态完整备份）

- 线程目标：在首次烧录前完整保存 StopWatch 当前 Flash 状态，并建立可验证恢复路径。
- 已完成：芯片/Flash 只读识别、16MB 整片读取、SHA-256、设备端 `verify_flash`、恢复说明和受保护恢复脚本。
- 验证结果：镜像长度 `16777216` 字节；SHA-256 为 `ACC86A...6B87B`；设备返回 `verify OK (digest matched)`。
- 未执行：Flash 擦除、固件写入、eFuse 读取或修改。
- 保存结果：项目目录和用户 Documents 目录各有一份，两个镜像 SHA-256 一致；如需防整机硬盘故障，仍建议再复制到离线介质。

### 2026-09-16（KK/Grok Avatar 立项）

- 线程目标：选定 `KK StopWatch Avatar` 作为工程底座，完成 Grok 风格表情机器人 v0.2.0 开发 PRD。
- 已完成：锁定两个上游仓库与提交、确定 PlatformIO/Arduino + M5Unified 路线、定义模块边界、任务拆分、验收指标和 G3 首次烧录门禁。
- 用户边界：个人使用、非商业、未来不闭源；允许直接复制和转换 Grok 参考资产，不把资产限制作为本版本开发阻塞项，同时保留来源记录。
- 未执行：源码导入、工具链安装、编译、烧录或设备写入。
- 下个线程建议：从详细 PRD 的 P0/P1 开始，实现至 G3 后等待首次烧录确认。

### 2026-09-16（Luna Max 目标模式交接包）

- 线程目标：把 v0.2.0 PRD细化为 Luna Max 可逐阶段执行的目标模式任务书。
- 已完成：L0—L7 实施步骤、G0—G3 门禁、几何转换规范、正式文件结构、12状态映射、T01—T12测试、视觉评分、证据目录、失败重试和最终汇报模板。
- 新增：独立实施进度与验收记录，用于持续回填命令、日志、哈希、视觉证据和阻塞。
- 未执行：正式源码导入、PlatformIO安装、本机构建、固件生成或设备写入。
- 下个线程建议：把任务书第0节完整复制给 Luna Max 目标模式，从 L0 开始，不得跳过桌面视觉验收或 G3 烧录门禁。

### 2026-09-16（v0.2.0 构建与首次写入）

- 线程目标：按任务书完成 L0—L7，实现 Grok 几何接入，完成 G3 预检和首次设备写入。
- 已完成：KK 锁定基线导入、项目隔离 PlatformIO 6.1.18、原版基线构建、Grok 确定性转换、12 状态桌面视觉检查、固件渲染器接入、最终干净构建和交付证据。
- 最终固件：`04-output/v0.2.0/firmware/firmware-v0.2.0-grok-avatar.bin`，`906592` bytes，SHA-256 `47C72B834883DE457995B15F024EEA4C8F625AA762E563F1952A350145FAB1CD`。
- G3/G4 结果：重新识别到 `COM5`、ESP32-S3 rev `v0.2`、MAC `28:84:85:44:6C:00`、16MB Flash；写入四段镜像并逐段读回校验通过。
- 当前边界：真机屏幕、触摸、按键、振动、IMU、串口性能和 30 分钟稳定性尚未完成；硬件贴纸版本仍需人工确认。

## 13. 版本规则

- 初始知识与工程骨架：`v0.1.x`
- 可编译原型：`v0.2.x`
- 首次可烧录、通过核心外设验证的原型：`v0.3.x`
- 首次正式交付：`v1.0.0`
- 小修订：更新第三位版本号
- 功能阶段升级：更新第二位版本号
- 第一位版本号：仅由大尾巴明确决定
- 变更记录：`CHANGELOG.md`，最多保留 5 个版本，更早内容转入 `CHANGELOG-历史归档.md`
