# v0.12.7 Watch 朗读失败诊断

日期：2026-09-24。电脑端源码 v0.12.7-dev；本次检查时正式 8766 实例 v0.12.6-dev；Watch 固件源码和应用区 v0.8.7-dev。

## 现场证据

- 用户见到“Watch 朗读：失败 · 0%”及随后“Watch 报告播放完成”，Watch 只显示文字，没有听到语音。
- 正式实例 `/api/health` 的设备音频任务为 `mode=play`、`stage=error`、`bytes=0`、`total=69120`、`error=""`、`running=false`。因此本次 PCM 数据未开始传输；现有状态无法追溯具体超时命令。
- 固件仅在 Settings → Audio test 调用 `AudioProbe::enter()`；离开该页后音频探针停用。文字气泡经独立 BLE 特征传送，显示文字不能证明音频到达。

## 修复

- 前端设备音频任务按期望终态判定：Watch 播放须 `played`，录音须 `received`。`error`、`cancelled` 或任何其他终态不再误报完成。
- 音频请求超时带 HELLO、BEGIN 等命令名和 Audio test 操作提示；后端避免把空异常写成空错误。页面在选择 Watch 朗读时提前提示进入 Audio test。
- 不改固件和设备数据，不触发 BLE 发送、云端请求或烧录。正式进程保留原会话，源码后端修复需重启控制台后生效；前端修复需刷新页面。

## 验证与剩余门禁

- Node 控制台 36 项、Electron 16 项、Python 控制台及音频协议 67 项通过。新增回归覆盖失败且错误为空、意外终态、命令超时说明及后端空异常。
- 现场失败可以确定为 **0 字节 PCM 传输**；是否因未进入 Audio test 造成 HELLO 超时，需下一次带命令名的结果确认。用户进入 Audio test 后重试，检查发送进度、`played` 回执及设备实际听感。自动测试和设备回执都不能代替听验。
