# v0.3.0 BLE 表情控制实施与验收记录

> 日期：2026-09-17
> 当前结果：v0.3.0 应用区已写入并读回校验通过；BLE 默认关闭，尚未配对，G4 无线门禁进行中。

## 1. 本轮完成内容

- 在现有 `03-Src/stopwatch-grok-avatar/` 工程内增加 `src/ble_control.*`，没有创建平行固件。
- 使用固定 GATT Service、Command、Status UUID；设备名为 `GorkBot-SW`。
- BLE 默认关闭；Bluetooth 设置页支持启停、120 秒 Pair 窗口、绑定状态和二次确认清除绑定。
- 使用 secure-connections bonding、加密特征权限和应用层单控制端绑定；回调只做有界校验/入队，主循环统一处理表情和回执。
- USB 命令与 BLE 命令共用 `AvatarEngine::showFromCommand`，保留原按键、触摸、IMU、亮度、电量、调试和硬件检查流程。
- 增加 Windows Bleak 控制台、双击启动脚本、锁定依赖和 5 项 mock GATT 测试；原 USB 控制台未改动。

## 2. 门禁状态

| 门禁 | 状态 | 依据 |
| --- | --- | --- |
| G0 基线 | PASS（本机范围） | `evidence/L0-baseline-20260917.txt` |
| G1 BLE/API 可行性 | PASS（构建范围） | `evidence/L1-ble-probe-build-20260917.txt`；不等价于无线配对通过 |
| G2 固件与客户端 | PASS（静态/模拟范围） | `evidence/L2-L3-static-tests-20260917.txt` |
| G3 写前报告 | PASS，已放行 | 重新枚举 COM5、核对 MAC/芯片/16MB Flash、读取当前 app0 备份；大尾巴已明确“执行烧录” |
| G4 真机无线验收 | 部分通过，继续收敛 | 已完成加密连接、服务发现、状态通知、`ERR:BUSY`、23/23 标准命令和一次断线重连；陌生端拒绝、10 次重连、P95/FPS/稳定性仍待补测 |
| G5 最终交付 | PARTIAL | 源码、工具、说明和证据已交付；真机证据仍缺 |

## 3. G3 写入边界

- 当前固件版本：v0.3.0；已在目标设备应用区 `0x10000` 写入并读回校验通过。
- 本次仅写应用区 `0x10000`，未写 bootloader、分区表或 `boot_app0`；esptool 报告的应用覆盖擦除范围为 `0x00010000–0x00187fff`。
- 烧录前已重新枚举 COM5、核对目标 MAC `28:84:85:44:6C:00`、ESP32-S3/16MB Flash，并读取当前 app0 作为回退证据。
- 用户已明确授权“执行烧录”；本次没有执行 `--erase-all`，没有修改 eFuse、安全启动、Flash 加密或电脑蓝牙配对状态。
- 写入命令、写后 `verify_flash` 和 USB 串口 DTR/RTS 观察记录在 `evidence/G3-G4-flash-20260917.txt`。
- 正式源码 v0.3.0 BLE 实施已做本地 Git checkpoint `08c98cb`（未推送）；其余既有 dirty 文件未纳入本次 checkpoint。

## 4. G4 待执行清单

1. 设备本地进入 `Settings → Bluetooth`，打开 `BLE ON` 并点击 `Pair`；电脑端已扫描固定 Service UUID 并使用 `BleakClient(pair=True)` 连接。
2. 已记录加密连接、状态通知、23/23 标准命令、`loop/once/pingpong` 和菜单 `ERR:BUSY`，详见 `evidence/G4-live-ble-20260917.txt`。
3. 待使用另一台/未绑定控制端验证写入拒绝；继续验证 Pair 窗口超时、BLE OFF、清除绑定、重启重连和 10 次断线重连。
4. 记录顺序命令 P95、BLE 连接下待机 FPS、30 分钟稳定性及 USB/本地交互回退。
5. 任一安全限制无法实测成立时，不将 v0.3.0 标为无线交付。

## 5. 证据边界

编译通过只证明代码和当前工具链可生成镜像；电脑存在蓝牙适配器只证明客户端侧具备条件；两者都不能替代 StopWatch 真机广播、配对、加密写入和运行时视觉验收。
