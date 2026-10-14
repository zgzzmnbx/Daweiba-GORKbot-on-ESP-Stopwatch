# Watch v0.11.2-dev BLE 服务顺序修复候选

2026-10-04。PC 运行 v0.20.0-dev；当前设备已由用户确认 v0.11.1-dev 正常启动、目前没有重影。用户 Bluetooth 照片显示 ON / Connected / Saved / SC + encrypted GATT，但 PC 尚未完成 GATT 服务发现，报 WinError -2147024874。

## 本机证据与修正

WinRT 只读探针确认 paired=True，表情与短音服务可查询，音频和配网服务查询失败；Cached 列表含表情40、音频55、短音70和重复短音85，Uncached 完整列表查询失败。照片及详细现场记录见 [v0.11.1 记录](../v0.11.1/重影修复与验收记录-【codex】.md)。

旧基线注册顺序为表情、音频、短音；v0.11.0/0.11.1 在音频前插入配网，改变旧服务句柄范围。v0.11.2 将配网追加到旧三服务之后，保留旧服务相对位置；网络服务注册失败时也关闭 BLE，避免部分服务启动。仅修改 `ble_control.cpp` 注册顺序/失败清理与 `main.cpp` 版本号，保留 v0.11.1 重影修复。未改绑定、安全权限、网络协议、音量、分区或 PC 源码。

服务顺序变化是已复现的兼容问题；Windows 当前缓存异常与它的因果关系还须写入后复测。锁定 ESP32-S3 SDK 已启用自动 Service Change，未添加反复全局缓存重置或清绑定措施。参考 [Microsoft GattServicesChanged](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.bluetoothledevice.gattserviceschanged) 和 [Bleak 上游相同 WinRT 错误报告](https://github.com/hbldh/bleak/issues/1123)，外部报告不作为本机根因证明。

## 自动验证

`tools/test_gatt_upgrade.py` 提取并执行真实生产注册分支与三个 attach 函数，对照保留的旧基线和改前版本，使用与锁定 Arduino BLE 默认15句柄预留一致的宿主分配器。旧基线/改前/候选分别得到表情40/40/40、音频55/70/55、短音70/85/70；修复前两个旧范围移动，候选三个旧范围均保持，配网最后追加。四个服务创建失败均返回失败且关闭 BLE。宿主测试不代表 Windows 缓存已刷新或无线链接已恢复。

PlatformIO 锁定工程构建通过，静态 RAM 118120/327680，程序 Flash 2227185/6553600 字节。应用镜像 `firmware/StopWatch-Gork-v0.11.2-dev-app.bin`；构建和服务顺序日志见 `tests/`。旧视觉生产代码未改，v0.11.1 连续7060帧、208次交接回归保留。

## 烧录与现场门禁

用户本轮明确回复“授权烧录”，授权本候选仅写当前 Watch app0。写前重新枚举 USB、核对 ESP32-S3、MAC、Flash16MB、分区及当前 OTA app0，并验证旧 v0.11.1 应用；仅写 `0x10000`，执行工具校验与独立 verify_flash，不清 NVS/绑定，不写 bootloader、分区或永久安全状态。

当前已仅应用区写入并独立校验通过，用户正常重启确认“v0.11.2 没错”，启动/实屏版本子项 PASS_DEVICE。旧BLE表情/短音/音频和新配网服务、热点认证/PTT/听感分别记录；T11–T13仍未完成，不以构建或写入替代真机验收。

改前两份源文件备份在 `Codex-Temp/ble-gatt-v0112/baseline/`，旧 v0.11.1 与 v0.9.1 恢复镜像保留。没有提交或推送。

## 本次授权写入结果

COM5重新枚举，ESP32-S3 QFN56 rev0.2 / PSRAM8MB / Flash16MB / MAC匹配当前授权Watch；app0 0x10000、大小0x640000，OTA有效seq=1选择app0。独立verify旧v0.11.1为digest matched；写入v0.11.2应用2227552字节，Hash of data verified；另起独立verify_flash digest matched，最后hard_reset。实际扇区擦写仅0x10000–0x22ffff，未清NVS/绑定。原始设备日志在本机忽略目录Codex-Temp/ble-gatt-v0112/。

重启前PC仍未完成服务发现；立即只读查询为Unreachable，不能把ROM复位或写入校验算作应用运行。已请求用户正常重启并确认v0.11.2-dev，再检查新旧服务。README/AGENTS/当前计划/CHANGELOG及矩阵已同步。

## 用户重启后的服务实测

用户随后明确确认实屏 v0.11.2。WinRT Uncached 音频服务、两个特征与描述符现在均查询成功；表情仍查询成功。Cached 服务列表依然含两个短音服务记录，短音与配网服务查询仍报 -2147024874，完整 Uncached 列表仍报 -2147418113。正式PC connected=false，未提交配网。

候选恢复了旧音频服务可发现性，但不能称 BLE 已完整恢复。正在请求用户将电脑 Windows 蓝牙关闭后开启，保留现有配对，复测缓存与服务；没有移除电脑配对、清 Watch 绑定或开启云上传。
