# CHANGELOG

> 仅保留最近 5 个版本；更早记录转入 `CHANGELOG-历史归档.md`。

## 未发布：交接文档 v1.0.0（2026-09-20）

- 确定 StopWatch 主开发、语音独立服务的分工，新增接口冻结副本及首轮任务入口；同步 README、AGENTS、当前计划。仅文档交接，不改变运行/固件版本，不计作实现或真机验收。

## v0.5.0 - 2026-09-17（BLE 文字聊天气泡；已写入并读回校验）

- Windows 蓝牙命令行新增 `:say 文字` 与 `:clear`；中文/英文以 UTF-8 分包发送，最多 24 字符、72 字节，不改变原有 20 字节 GATT 单包上限或服务 UUID。每包等待对应回执，未收齐或校验失败不更新显示。
- 固件主循环重组并校验文字；表情画面上方以 16 px 中文字体绘制两行气泡，10 秒后自动清除，保留原表情和顶部调试标签。BLE 回调仍只做授权检查和有界入队。
- 21 项 Python 测试、来源目录校验及 PlatformIO 正式构建通过；RAM 62,912/327,680（19.2%），Flash 1,544,681/6,553,600（23.6%）。归档 `04-output/v0.5.0/firmware/firmware-v0.5.0-ble-chat-bubble.bin`（1,545,040 字节）。按大尾巴当次指令，仅写设备应用区 `0x10000`，写入校验及独立 `verify_flash` 均通过；中文实屏、气泡残影、帧率和无线真机链路待验收。
- 新增 v0.5.0 PRD/验收记录，更新 README、AGENTS 和当前版本计划。v0.3.0 的安全负向与长期稳定性缺项、原表情命令旧回执误判和自动重连问题仍未关闭。

## v0.4.0 - 2026-09-17（happy-work 派生表情；已构建，未烧录）

- 在 23 条 Grok bot 来源动画之外新增第 24 个可调用表情 `happy-work`：原样复用 `happy` 的 4 帧眼睛时间轴，下半部程序化绘制纸张、笔、握笔小手和逐渐延伸的笔迹；沿用局部擦除，退出时清除书写层。
- 默认播完回待机；`loop happy-work` 与 `pingpong happy-work` 为显式持续模式。USB 串口与 BLE 控制台均可输入带连字符的命令，最长示例为 19 字节，未改变 BLE 20 字节上限。
- 客户端、来源目录及几何测试共 17 项通过；PlatformIO 正式构建成功，RAM 62,672/327,680（19.1%），Flash 1,541,201/6,553,600（23.5%）。版本化应用镜像已归档，设备仍运行 v0.3.0；书写观感、残影和帧率待真机验收。
- 新增 v0.4.0 派生表情 PRD，更新 README、AGENTS、当前版本计划及使用说明。v0.3.0 BLE 安全/稳定性缺项未因此关闭。

## v0.3.0 - 2026-09-17（BLE 配对与核心表情控制通过）

- 在现有 StopWatch 固件内新增 BLE GATT 控制模块和 Bluetooth 设置页：BLE 默认关闭，支持本地 120 秒 Pair 窗口、secure-connections bonding、加密特征权限、单控制端绑定和二次确认清除绑定。
- BLE 回调只做固定长度校验/入队；USB 与 BLE 共用 `AvatarEngine::showFromCommand`，Settings/Hardware/Bluetooth 菜单打开时返回 `ERR:BUSY`，未知输入不改表情、不振动。
- 新增 Windows Bleak 控制台、双击启动脚本、锁定依赖和 mock GATT 测试；5 项客户端测试通过。L1 探针与正式 PlatformIO 构建通过，正式镜像 RAM 19.1%、Flash 23.5%。
- 已完成 G3 预检，并在获得“执行烧录”授权后仅写入 `0x10000` 应用区；写后 `verify_flash` 返回 `verify OK (digest matched)`。未整片擦除、未改 bootloader、分区表、eFuse 或安全配置。
- 设备本地打开 `BLE ON` 并点击 `Pair` 后，Windows `BleakClient(pair=True)` 已发现并连接 `GorkBot-SW`，状态通知、菜单 `ERR:BUSY`、23/23 标准命令、播放前缀和一次断线重连均通过；陌生端拒绝、10 次重连、P95/FPS、功耗和 30 分钟稳定性仍待补测。

## v0.2.7 - 2026-09-17（v0.3.0 BLE PRD 与 Luna Max 交接，历史）

- 新增 `07-v0.3.0-BLE表情操控开发PRD-【codex】.md`：明确本电脑内置蓝牙 + StopWatch BLE GATT、23 表情、Windows Bleak 控制台、配对安全、USB 回退及 L0—L6/G0—G5 门禁。
- 本机确认 Windows 11 build 26200、Intel Wireless Bluetooth 与 Microsoft BLE 枚举器状态 OK、Python 3.14.3 和 Bleak 3.0.2；尚未建立 StopWatch BLE 广播、配对或无线控制。
- 更新 README、项目 AGENTS 与当前版本计划。文档版本 v0.2.7，设备固件仍 v0.2.5；本轮未改固件、未烧录或改变电脑蓝牙配对。

## v0.2.6 - 2026-09-17（Windows 表情串口控制台）

- 新增可双击的 `tools/start-expression-console.cmd` 与 PowerShell 串口控制脚本；自动识别 StopWatch USB 串口，不写死 COM5，使用 115200 波特率。
- 支持 23 个固件表情名、`once/loop/pingpong` 播放前缀、`:list` 和 `:q`；关闭 Settings 后使用，不与其他串口程序同时运行。
- PowerShell 语法、端口识别及真机发送测试通过：`happy` 获得 `Command accepted: HAPPY`。工具窗口已启动；本版未修改或重烧设备固件，设备仍为 v0.2.5。
