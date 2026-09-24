# BLE 程序内配对与稳定连接验收

日期：2026-09-24
电脑端源码与当前运行实例：v0.12.3-dev
固件源码、构建产物与设备应用区：v0.8.7-dev（仅写入 app0，独立校验通过）

## 本机证据

1. Windows 设置截图显示 `GorkBot-SW` 在“已连接/未连接”间切换；Gork 截图报“已连接，但未发现目标 GATT 服务”。运行中 `/api/health` 同时报 `connected=false`、同一 GATT 错误。
2. 本机 Bleak 扫描到唯一目标 `28:84:85:44:6C:01`，广播服务 UUID 为 `48f1a001-8a75-4db6-9c18-590f7e9b0a01`。旧绑定下，以 `pair=True`、`use_cached_services=False` 查询三个指定服务均返回 `BleakError: Could not get GATT services: Unreachable`；缓存查询显示目标服务 `access denied`。Windows 认为已配对，但加密 GATT 实际不可用。
3. 旧 `260528-ESP-32-S3-codex` 使用开放的 NimBLE GATT 写入；客户端扫描名字后用 `BleakClient(device)` 直接连接。StopWatch 使用 SC bonding、加密特征权限和绑定控制端，旧项目的“无需预先配对”体验可以保留，但安全协议不能直接照搬。
4. StopWatch 固件原逻辑在 `onConnect` 和 `onSecurityRequest` 中以尚未认证的连接地址判断绑定身份；Windows 若以私有地址重连，可能提前断开，随后 WinRT GATT 发现报告不可达。此处是源码可确认的逻辑风险，尚不能单凭本次日志证明它是唯一断连原因。
5. 按本次授权写入 v0.8.7 后，旧绑定仍出现全部 GATT 服务不可达。用户在手表上清除旧绑定并打开 Pair 窗口；电脑端 Bleak `unpair()` 清除旧 Windows 配对，随即 `pair=True` 在程序内重新配对。GATT 服务发现成功，单条 `idle` 命令因手表 Settings 菜单打开而返回预期的 `ERR:BUSY`。随后程序连续 10 次断开再连接均成功，每次重新发现目标 GATT，约 5.8–7.2 秒/次；尚未验证菜单关闭后的 `OK:IDLE` 回执。

## 修改

- 固件允许已绑定场景先完成加密认证，再以认证结果核对已保存身份；新绑定仍须设备本地 Pair 窗口。命令/音频/通知仍要求 `authorized_`，陌生端认证后不匹配即断开。
- 电脑端继续 `pair=True`，首次配对等待从 30 秒延至 60 秒，启动自动连接总等待从 40 秒延至 75 秒；连接/服务发现错误保留底层原因，方便区分超时、不可达和目标服务缺失。
- 首次失败或链路掉线后持续后台扫描重连，采用 5–30 秒退避；有配置地址时严格匹配，未配置时只接受唯一服务候选。手动断开停止后台重连。
- 将本次程序化取消旧配对并重配的步骤收成 `tools/repair_stopwatch_ble_pairing.py`，仅显式 `--apply` 执行；目标选择校验 2 项自动测试通过。正常连接无需运行恢复工具。
- 使用说明明确：首次在设备打开 Pair 窗口，由 Gork 在程序内发起配对，Windows 弹窗由用户确认；后续设备 BLE ON 可自动连接，无须每次进入 Windows 设置。

## 验证及门禁

- BLE 相关 Python 回归：40 passed；控制台完整测试目录：46 passed。
- PlatformIO `run -d 03-Src/stopwatch-grok-avatar`：短盘符环境构建成功；RAM 63,928 bytes / 327,680，Flash 1,625,545 bytes / 6,553,600，应用镜像 1,625,904 bytes。首次在长路径构建遇到已知 Windows `CreateProcess` 错误，短盘符重试成功，临时盘符已移除。
- 写入前重新枚举 `COM5` 为 ESP32-S3 原生 USB `303A:1001`，读取 MAC `28:84:85:44:6c:00`、16 MB Flash 和设备分区表，确认 app0 偏移 `0x10000`、长度 `0x640000`。仅执行 `write_flash 0x10000` 写入 1,625,904 字节应用镜像，esptool 报写入哈希验证通过；随后独立 `verify_flash 0x10000` 报 `verify OK (digest matched)`。未写 NVS、分区表、eFuse 或整片擦除。用户报告手表 BLE ON、Binding saved。
- 已通过：从程序内重新配对并发现 GATT；连续 10 次主动断开/重连并记录结果；旧版正式 Electron 通过 File > Exit 正常退出后，以源码入口重启，`/api/health` 确认为 v0.12.3-dev 且 `robot.connected=true`、`enabled=true`。
- 本机忽略配置 `config.local.toml` 固定 Watch 地址 `28:84:85:44:6C:01`；再次正常重启 Gork 后健康接口回显同一目标且自动连接成功。持续连接原始采样记录位于 `Codex-Temp/ble-pinned-monitor-v0123.log`，验收结束时再统计完整时长和失败次数。
- 本次持续连接记录为 22 分 02 秒、67 次健康采样，全部 `connected=true`、`enabled=true`，未出现掉线采样；因用户通过 Escape 停止 Computer Use，本轮停止进一步界面操作和监测，尚未达到 30 分钟目标。设备仍停留 Settings 时，命令回执是预期的 `ERR:BUSY`，菜单退出后的成功回执待实测。
- 待人工验收：回到机器人画面后确认命令回执；保持 30 分钟连接和周期命令回执；陌生端无法写入；表情/声音基本回归；正式 Gork 的真实掉线自动重连。Windows 蓝牙列表“未连接”只有在程序保持活动 BLE 会话时才需作为异常观察，不把空闲状态当故障。

## 回退

旧 v0.8.6 应用镜像与写入记录保存在 `04-output/v0.8.6/`。发生真机退化时先停用 Gork BLE，按原恢复说明和当次授权仅恢复 app0，不清除配对、NVS 或整片 Flash。
