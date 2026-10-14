# Gork 控制台右上角架构图入口实施与验收

日期：2026-10-05。PC 源码/元数据：v0.20.19-dev。Watch 固件未改，实机仍 v0.11.7-dev，v0.11.8-dev 为待当次烧录授权的候选。

## 实施

- `ui/console.html` 顶栏右上角增加「架构图」按钮和原生模态弹窗；`ui/build.mjs` 生成 Mantine 页面，保留经典/Mantine 双主题及既有控件 ID。
- 弹窗使用 `static/architecture-landscape.mp4`，与 `04-output/live-panel-2026-10-05/Gork-Watch横版动态架构-【codex】.mp4` 的 SHA-256 一致。仅点击后加载本机视频，静音循环；可暂停/继续，点关闭或按 Esc 后停止并释放视频，焦点返回入口。画面注明动态日志与计数是模拟，不表示实时遥测。
- `static/architecture-viewer.js/.css` 单独管理展示；视频经现有 `media-src 'self'` 加载，未放宽控制台 CSP，未调用设备、业务接口或云服务。横版 HTML 与原配置仍保留在 `04-output/live-panel-2026-10-05/`，作为可独立打开与编辑的交付物。

## 验证

- `npm run build:ui` 和 `npm run check:ui` 通过；生成页保留 `controls` 以外的原生视频布尔属性 `loop`、`muted`、`playsinline`。前端 86 项与桌面 38 项回归通过。
- 隔离 Electron 使用与正式页面相同的严格 CSP、仅本机测试服务器，不连接设备/云。Mantine 1180×820 与经典主题 390×844：入口与弹窗均在视口内且顶栏无重叠；视频实际解码宽度 1920、`readyState=4`，播放进度超过 2 秒；暂停/继续、关闭、Esc、焦点返回、草稿保留通过；无 CSP/媒体错误。截图及结果 JSON 同目录。
- 对正式本机 8766 服务仅作只读请求：`/` 返回 200 且含入口、弹窗和脚本；`/static/architecture-landscape.mp4` 的 `Range: bytes=0-31` 返回 206、`video/mp4`，CSP 仍为原 `media-src 'self' blob:`。当次 `/api/health` 后端版本为 v0.20.18-dev，route 为 Wi-Fi；这不等于已经对正式用户窗口执行刷新或重启。

当前窗口刷新可加载新静态入口；正常退出并重开后后端版本显示 v0.20.19-dev。本轮未刷新或重启用户正式窗口，未写 Watch、改连接、访问云、提交或推送。性能与长稳仍按用户此前要求延期。
