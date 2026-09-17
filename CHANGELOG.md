# CHANGELOG

> 仅保留最近 5 个版本；更早记录转入 `CHANGELOG-历史归档.md`。

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

## v0.2.5 - 2026-09-17（调试小字移至顶部，已写入待真机验收）

- 调试模式动画名由头像底部移至黑色圆体顶部，中心 y=42；字体、颜色、开关与表情切换逻辑不变。
- 数据生成检查、12 项现有 Python 测试和 PlatformIO 构建通过；固件 907184 字节。
- 当次重新识别 COM5、MAC `28:84:85:44:6C:00`，仅写 `0x10000` 应用区，读回 `verify OK` 并发出硬复位；顶部文字观感与其他真机功能待大尾巴验收。
- 按大尾巴要求，后续常规迭代不再重复计算或核验文件 SHA-256；仍保留必要的设备识别、写入校验和读回验证。

## v0.2.4 - 2026-09-17（设置页电量与调试模式，已写入待真机验收）

- 设置首页新增电池电量估算百分比和电压，调用 M5Unified 的 StopWatch/M5PM1 接口，每 5 秒刷新；无效读数显示 `--`。该百分比来自电压估算，并非精确 mAh 容量。
- 设置首页新增可持久化的 `Debug mode` 开关；开启后头像底部以小白字显示当前动画英文名，关闭后重新绘制清除。原硬件检查保留在 `Hardware Check` 子页。
- 整合尚未写入的 v0.2.3 亮度调节；v0.2.4 数据生成检查、12 项 Python 测试和 PlatformIO 构建通过。固件 907200 字节，SHA-256 `CBCE21D83F01890AB649000EA5FE41806A146357C61F46EC122F48B53830EA4A`。
- 当次核对 COM5、MAC `28:84:85:44:6C:00`、ESP32-S3/16MB/8MB、完整备份哈希，写前 v0.2.2 应用区 `verify OK`；仅写 `0x10000` 应用区，写后 v0.2.4 `verify OK`，工具已发出硬复位。电量实际读数、调试字样观感、开关持久化、亮度及自动回待机仍待大尾巴真机验收。
