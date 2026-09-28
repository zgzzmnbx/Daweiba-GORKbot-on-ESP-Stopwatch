# Gork v0.16.3-dev：界面版本号显示修复

日期：2026-09-28

## 现象与原因

用户反馈界面不显示版本。正式 `/api/health.version` 为 `0.16.2-dev`，Watch 已连接；控制器已把运行版本写入页眉和设置页，但 Mantine `modern.css` 把 `.version` 设为 `display:none`，经典主题在较窄窗口也隐藏页眉版本。

## 修复与边界

- 页眉 GORK 标识下常显运行服务返回的 `vX.Y.Z-dev`，Mantine 和经典主题、宽窄窗口均保留。无法读取时显示“版本无法读取”。设置页原有版本号保持。
- 控制服务、控制台包与 Electron 包统一标记 `0.16.3-dev`。当前正式实例仍是 `0.16.2-dev`；刷新现有界面会显示实际运行版本，重启后才会显示 `0.16.3-dev`。
- 固件、Android、智算业务代码、BLE 绑定和哨兵业务逻辑未改。未代用户重启客户端。

## 验证

- 检查正式服务 `/api/health.version=0.16.2-dev`；正式服务 `GET /` 已包含页眉版本及设置页版本节点。
- 控制台 Node 54 项通过，覆盖运行版本从 health 同时写入页眉和设置页、生成界面中页眉位置唯一；`npm run check:ui` 通过。Python 75 项与 Electron Node 29 项通过；正式 Electron 实屏待用户刷新核对。
