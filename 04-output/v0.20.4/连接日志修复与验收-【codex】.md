# PC v0.20.4-dev 连接日志修复与验收

## 修复与根因

用户提供14:29:23–14:30:05的日志，每秒交替报告StopWatch已连接与设备操作异常，期间Opus音频实际完成传输并收到播放结束回执。

日志去重原来仅保存每通道最后一句，DEVICE连接和操作两句在同一轮互相替换，因此下次轮询两句都再次输出。现在同一通道按固定connection/operation键分别保存文本和严重级别；重复状态不输出，变化/恢复和清空后新状态仍输出。

Robot后台BLE扫描、连接和重连错误原来写入全局操作error，导致Wi-Fi成功任务被误报。现在ble_error独立保存，operation_error明确设备操作来源，snapshot旧error字段保留离线BLE错误兼容；UI按来源展示设备操作/BLE/Wi-Fi诊断，日志只记录安全摘要。Wi-Fi成功flush清除旧操作错误；BLE连接恢复只清理BLE错误，不覆盖真实业务错误。

## 验证

- Python完整回归161项通过，新增自动BLE失败/重试不覆盖Wi-Fi操作错误、成功Wi-Fi清理操作错误、BLE恢复不清除其他错误。两个现有依赖弃用警告，零失败。
- 前端71项通过，包含真实paintRobot连续100次相同健康状态只有SYS/连接/回执/BLE异常各一条、真实失败/恢复/离线仍输出；去重严重级别与清空逻辑通过。debug-console回归已纳入npm test。
- 桌面既有32项通过；npm run check:ui通过；git diff --check针对本次源文件通过。

详见tests/backend.log、frontend.log、desktop.log。未改变页面布局，无需重复前版24种布局截图。

## 现场与限制

修复前只读正式/api/health核对PC v0.20.3-dev、route=wifi、Wi-Fi已连接、BLE未连接。旧全局error为BLE连接/服务发现失败WinError -2147024874；network.error为空。Opus4776/4776字节、stage=played、音频无错误，最近文字回执OK:TEXT。测试公开字段快照仅含连接与字节状态，不含凭据、正文或会话token，见tests/public-health.json。

PC新源码/两套元数据v0.20.4-dev；后端须用户正常退出重开，尚未核对新正式版本及现场停止刷屏。Watch仍v0.11.5-dev，用户已确认版本与底部黑条消失。未烧录、清绑定、改变网络、发起云请求、提交或推送。蓝牙实际GATT故障、实际听感/PTT和T12/T13仍待验收，不把日志分类修复算作蓝牙恢复或听验。

## 文件与恢复

修改companion/robot.py、static/app.js、static/debug-console.js及对应回归，README/当前计划/AGENTS/CHANGELOG已同步，CHANGELOG最多5版，超出归档。仅本次变更前的文件备份见Codex-Temp/log-v0204/baseline/；保留此前未提交改动。需要恢复源码时逐文件对比备份，禁止整个dirty worktree重置。
