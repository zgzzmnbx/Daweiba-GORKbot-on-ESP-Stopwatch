# 用户确认与连接模式说明（记录v1.0.0，2026-10-04）

## 当前用户决定

- v0.11.7录音提示、双端书写、实际听感：用户回复“一斤完成”，按上下文记为“已经完成”。这些用户实机确认关闭，不再重复要求。无新增量化性能结论。
- 真机性能与稳定性：用户明确“先不测了”。T12/T13延期，保留原标准和历史NOT_RUN，不安排压测、长测、电池或故障注入。
- 用户希望菜单选择以后切回原蓝牙方式：当前v0.11.7已经有此功能，复用现有入口，无新固件。

## 操作

1. 按住A+B进入Settings。
2. 点Network，点第一行连接策略，轮换到BLE only。
3. 若蓝牙曾手动关闭，返回Bluetooth，将Control切到ON（点BLE ON）。保留Saved绑定，不点Clear binding或Forget hotspot。
4. 电脑若保存的是“自动，Wi-Fi优先”会在Wi-Fi不可达时尝试蓝牙；若保存的是“仅Wi-Fi”，须在电脑StopWatch连接策略改回自动或仅蓝牙。菜单选择不修改电脑已保存偏好。
5. 恢复热点模式时将Watch第一行切回Auto WiFi first；已保存热点和绑定都保留。

## 源码核对

`src/main.cpp`的drawNetworkFrame显示三模式，handleNetworkInput保存下一档策略。`NetworkControl::options`只修改配置policy/power，其save原子保存整blob；update在policy=1时disconnect(true,false)、关闭mDNS，TLS worker不接收Wi-Fi连接。配置重启读取并校验CRC。Bluetooth开关独立存在，未自动抹除或重配绑定。代码在当前v0.11.7已包含，写入日志与独立校验记录已存在。

这是现有菜单/保存/关闭Wi-Fi路径的源码核对，不宣称Windows BLE完整服务发现已经恢复。旧服务发现异常和当前菜单选择后的基础实机通信分开记录，既有配对不清。边生成/边传/边播放继续标尚未实现。

## 项目记录

README、AGENTS、当前计划、固件双语README、v0.11.7写入/验收记录与PRD35/36追加本次用户决定，保留历史记录。本轮未改代码、版本、服务、网络或固件；无新镜像、无烧录、无云请求、无提交/推送。备份在Codex-Temp/watch-scope-v0117/baseline。此后不再重复把已确认的v0.11.7三项和已延期的性能长稳作为本轮待执行项。
