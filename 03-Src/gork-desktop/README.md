# Gork Robot Console v0.15.0-dev

## v0.15.0-dev：Mantine 控制台与经典主题（2026-09-26）

六个功能页使用 Mantine 9.6.2 组件重绘，保留左侧常驻 Gork、右侧标签页和轻量输入区。右上角「经典主题 / Mantine 主题」即时切换并记住；仅切换样式，不刷新页面，不丢失草稿/记录/开关，不新建语音或 BLE 连接。角色形象、表情、桌面大小/气泡、设备控制、语音设置、造价助手和日志沿用现有逻辑。

Mantine 组件在构建时由 React 预渲染为原生控件，现有控制器独占运行时状态；生成 HTML 与样式全部随项目保存，不依赖外部 CDN，启动不需要 npm。旧 `style.css` 保留。开发时在 `03-Src/stopwatch-voice-companion/` 运行 `npm ci`、`npm run build:ui`；修改 `ui/console.html` 后必须重建，不直接修改生成的 `static/index.html`。

78 项 Node 回归通过；六页窄屏检查及新旧主题 1180×820、800×540、390×540 检查通过，页面无整体溢出、提交按钮可见。正式实例未重启，未执行真实语音/BLE/Watch 验收，固件不变。PRD 23 与 `04-output/v0.15.0/Mantine控制台实施与验收-【codex】.md` 记录边界。

## v0.14.8-dev：Gork 待机转头（2026-09-26）

控制台与桌面 Gork 待机时，除眨眼外会间歇左右转头、轻微俯仰，再平滑回到原姿态。共用时间轴保持同一场景的动作一致；播放其他表情时退出待机附加动作，静态缩略图、Watch 目标预览及系统减少动态效果模式不叠加新动作。Gork 接入已有 Avatar Lab 完整几何渲染，修正旧画法过度压小转头角度的问题；来源 23 条表情数据不变。

网页刷新后加载；桌面悬浮窗需退出重开 Gork。74 项 Node 回归与隔离网页转头画面检查通过；正式 Electron 未重启验收，Watch 固件不变。详见 `04-output/v0.14.8/待机转头实施与验收-【codex】.md`。

## v0.14.7-dev：形象设置归入角色页

「小人形象」移至右侧「角色」标签页顶部；左侧保留「表情菜单」。预览、配色、保存与恢复功能保持。3 项形象回归通过，隔离网页核对菜单归属、切换及布局；正式服务未重启。

## v0.14.6-dev：小人形象切换（2026-09-26）

控制台左栏新增可折叠「小人形象」：10 个 Avatar Lab 同源形象预览，支持身体/眼睛配色、恢复 Gork、保存偏好。电脑端表情预览跟随选定形象，Watch 目标预览仍为 Gork。桌面形象通过限定来源 IPC 同步，重启后恢复；需要退出并重开 Electron 加载新接口。

本版完成电脑端；Watch 当前固件仅内置 Gork，尚不支持更换形象，未修改或写入固件。69 项 Node 回归通过，正式桌面重启实屏待验；详细记录见 `04-output/v0.14.6/形象切换实施与验收-【codex】.md`。

## v0.14.5-dev：控制台表情菜单（2026-09-26）

左侧机器人下新增默认收起的表情菜单，23 个同源 Gork 动画缩略图；悬停或键盘聚焦只预览，点击发送。目标可选桌面小人、Watch 小人或两端，支持一次/循环，待机结束循环。Watch 未连接、工作台占用或音频任务进行中会给出提示；两端结果分开显示。菜单收起后停止预览，静态缩略图不运行持续动画。设备专属 happy-work 继续从角色页发送。

自动回归和隔离页面检查见 `04-output/v0.14.5/表情菜单实施与验收-【codex】.md`。正式实例未重启，桌面悬浮窗与 Watch 真机响应仍待验；固件不变。

气泡位置在左侧大小滑块下选择，默认上方，可选下方/左侧/右侧；偏好自动保存，空间不足时自动避让。

桌面聊天气泡：在对话页选择“小人显示 → 桌面小人”，再发送原文或 AI 回答。气泡在独立窗口显示，不缩小头像；关闭仅关闭当前消息，隐藏小人同步隐藏气泡。新消息替换旧消息，最长300字，按长度保留8–36秒；需要重启桌面程序及后端加载完整变化。

The console's “始终置顶” switch controls whether the floating avatar stays above other windows. It is on by default for existing users and saved with the avatar's window state. Restart the Electron shell to load the new IPC bridge; the browser-only page cannot change this setting.

The console now has four pages: Dialogue, Character, StopWatch and Settings.
Workbench ownership is separate from the single active voice session, so a
released voice session does not disable local character preview or Watch control.
Manual character requests and short bubbles are delivered through the existing
restricted backend; the desktop avatar returns one-shot expressions to idle.
The voice project's foreground managed entry handles pipe EOF and cleans up
its inference worker; the voice module now runs from this project; credentials remain outside source files.

Web and desktop use the same Canvas renderer and the Watch's pinned Grok bot
catalog (27 poses, 23 sequences), without the old beige panel/green ring.
Run `python tools/export_desktop_avatar.py --check` from the project root to
check generated copies. Restart from the root launcher to load changed files;
the older packaged v0.8.0 directory is not updated by source changes.

Windows x64 Electron desktop shell for the Gork companion at `http://127.0.0.1:8766`.

From the project root, double-click `start-gork-console.cmd`. The launcher installs the pinned Electron dependency on first use, then starts the GUI without keeping a command window open. Reopening the launcher activates the existing single instance instead of initializing another desktop shell. The shell reuses a verified existing project backend or starts its own instance with the project Python environment; on exit it stops only the instance it owns.

The shell provides one application instance, tray, resizable transparent avatar, shared backend state and a full console window. It reuses a verified external companion or starts the project-owned one with `--no-browser`. The packaged build resolves its companion from `resources/project` and stops only its own child process.

Security defaults: renderer sandbox, context isolation, no Node integration, a small preload IPC allowlist, exact-origin navigation, audio-only media permission for the trusted loopback console, and no credentials in this directory.

Validation:

```powershell
npm test
npm start -- --smoke-test
```

The smoke tests prove both source and packaged Electron processes can start on this Windows machine; the packaged probe also starts and stops its own backend on an isolated port. Tray interaction, actual microphone permission, multiple monitors and long-run behavior still require manual acceptance.
