# Gork 任务哨兵 v0.16.1-dev：人工优先修复与验收

日期：2026-09-28

## 用户现场证据

- 大尾巴使用正式 Gork `0.16.0-dev` 与智算 `v5.24.5` 跑出网页批量匹配。哨兵记录完成提醒及后续预警复核提醒，均显示桌面、Watch、电脑声音为 `suppressed`。
- 同时读取 Gork `GET /api/desktop/state`：`phase=idle`、Watch `connected=true`、设备音频 `running=false`、桌面角色 `manual=true`；`GET /api/cost/sentinel`：`enabled=true`、`target=both`、`sound=true`、`sound_target=pc`。因此故障位于 Gork 自动输出条件，不是智算未发现任务或 Watch 掉线。
- v0.16.0 的 `Controller.auto_available()` 将 `manual=true` 当成永久禁止条件；一次手动表情既阻断桌面角色，也连带阻断 Watch 和电脑系统短音。`_notify()` 将繁忙时事件直接记为 `suppressed`，空闲后不再发送。

## 修复

- 保留手动表情作为待机偏好；人工角色操作只在既有 15 秒优先窗口内压制哨兵，语音/设备音频忙时仍优先人工。
- 将有效完成/复核提醒最多暂存 90 秒，空闲后送达；新任务/新 attempt、断线、关闭哨兵时丢弃待发提醒，避免播放过期提示。Watch 的 `working` 表情在繁忙期间不丢失，空闲后重试。
- 页面显示“提醒暂缓”及原因；显式开启哨兵时结束旧的网页本地手动预览。Watch 继续使用同一 BLE 写锁，进入锁后再次核对开关和人工优先状态。

## 自动验证

- `python -m pytest tests -q`：74 项通过，包括“人工优先时暂缓、空闲后只送达一次”和 Watch 写锁等待后的人工抢占。
- 控制台 `npm test`：52 项通过；`npm run check:ui`：Mantine 生成界面与源模板一致。
- Electron `npm test`：29 项通过。
- 静态和模拟测试不能代替正式 Electron 画面、Watch 实屏或提示音实际听感。

## 运行门禁与复测步骤

- 源码版本 `0.16.1-dev`。大尾巴已自行重启；当次正式 `/api/health.version` 确认为 `0.16.1-dev`，Watch `connected=true`，哨兵已开启、两端显示及电脑短音均保留。智算 8000 为 `v5.24.5`，无需改业务代码。
- 哨兵后端重启默认关闭。重开后在“造价助手”开启任务哨兵，选“两端”与电脑提示音，再发起新一次网页批量匹配；既有完成任务不能回放为新提醒。
- 人工复测记录：Watch 保持已连接；新任务运行时观察桌面/Watch `working`，结束或新增预警后观察两端表情与气泡、电脑短音；在手动表情后的 15 秒内完成任务，确认先显示暂缓，空闲后只提醒一次。关闭哨兵后不再自动输出。
- 大尾巴自行重启了正式客户端；本次未烧录固件、未改 Android、未推送。新任务的桌面/Watch 实屏与听感仍待实测。
