# 小人形象切换实施与验收

版本：v0.14.6-dev；日期：2026-09-26。

## 使用

控制台左侧机器人下展开「小人形象」，点击缩略图切换。提供 Grok bot、Strobi、Freddy、Citrus、Nova、Sunee、Kirby、Cloudee、Cubee、Onee 共 10 项；支持身体/眼睛颜色、恢复 Gork、自动保存。形象与动作分离，选择新形象后仍可播放原 23 项表情。

电脑端完成：控制台、表情预览及桌面悬浮小人可使用所选形象。网页偏好存 localStorage；桌面客户端以主进程保存的 window-state.json 为准，通过限制为控制台来源的 IPC 保存与广播，重启恢复。需要从托盘退出并重新打开 Gork 加载新 preload/main/渲染资源；正式运行实例未由本轮重启。

Watch 当前固件只内置 Gork，不支持新形象；形象菜单已明确说明。表情目标为 Watch 时缩略预览也使用原 Gork，两端目标的 Watch 仍为 Gork。本版未修改或烧录固件。

## 来源及复现

参考用户指定 https://avatars.bible-strong.app/ ，沿用项目固定上游 smontlouis/bible-strong-avatar-lab@79fe9ba06e4874b11394b8e8a3f2c493c9d197ba。

上游 10 项形象完整几何、眼睛、配色与无依赖渲染引擎已存入 03-Src/avatar-library，保留 TypeScript 源码与 AGPL-3.0-only LICENSE。运行与资源导出均不再依赖 Codex-Temp 中的参考克隆；不执行公开发布。原 Gork 绘制路径保留，其余形象用正式上游 Path2D 几何绘制，非 CSS 轮廓替代。

导出检查：python tools/export_avatar_library.py --check；python tools/export_desktop_avatar.py --check。均通过。

## 验证

- node --test 03-Src/gork-desktop/tests/*.test.js 03-Src/stopwatch-voice-companion/tests/test_browser.mjs 03-Src/stopwatch-voice-companion/tests/test_appearance.mjs：69/69 通过。
- 全部 10×23 形象/动画组合生成有限且有效的路径，静态预览不启动持续帧循环；旧 Gork 几何及播放时间同步测试保留。
- 测试覆盖白名单 ID/颜色校验、限定 IPC 来源、持久化/恢复、保存失败回退、异步读取不覆盖用户新选择、提交互斥，以及原表情菜单/语音/气泡回归。
- 隔离 8879 网页真实检查：Freddy/Kirby 切换、身体配色、刷新恢复、恢复 Gork，未连接 BLE 或语音；浏览器无脚本错误。
- 1180×820、800×540、390×540 下，展开菜单时根 scrollWidth/scrollHeight 与视口一致；长内容在左栏内部滚动。
- 形象切换预览-【codex】.png 为 1180×820 的网页实屏。

正式 Electron 悬浮窗口同步与重启后的实屏尚未验证，自动测试不替代原生验收。控制台源码 v0.14.6-dev，正式运行后端沿用既有 v0.14.4-dev，固件及设备仍 v0.9.1-dev。README / 当前版本计划 / AGENTS / CHANGELOG 已更新；其他任务的未提交改动保留。
