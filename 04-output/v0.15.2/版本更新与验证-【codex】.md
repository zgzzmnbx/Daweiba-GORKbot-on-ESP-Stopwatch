# 电脑端 v0.15.2-dev 版本更新与验证

日期：2026-09-28。范围：Gork 控制服务、Mantine 控制台、Electron 桌面程序。Watch 固件 v0.9.1-dev、Android v0.1.7-dev 与 Watch 绑定未改。

## 变更

- 将控制服务 `companion.__version__`、控制台 UI package/lock 和 Electron package/lock 统一为 `0.15.2-dev`。
- 设置页“Gork 电脑端版本”显示运行实例 `/api/health` 返回值，避免源码已更新而旧实例仍运行时显示错误版本。顶部旧版本文案不再作为判断依据。
- BLE 断电重连逻辑沿用 v0.15.1；本次只同步版本与可见状态，不扩大连接修复结论。

## 验证

- `npm run build:ui` 与 `npm run check:ui` 通过；控制台 Node 回归 50 项通过。
- Python/StopWatch BLE 与声音回归 90 项通过。
- Electron 桌面程序 Node 回归 29 项通过。
- 从 Electron 的 File → Exit 正常退出旧实例，再用项目启动器重新打开。正式 8766 `/api/health` 返回 `version=0.15.2-dev`；设置页实屏显示“Gork 电脑端版本 v0.15.2-dev”。重启后控制台显示 Watch 已连接。此项只确认当前连接，不替代断电后的再次重连和长稳验收。

## 后续门禁

Watch 断电再开机后的 GATT 发现、命令回执与长稳运行须分别记录；版本显示和模拟测试不替代这些真机验收。
