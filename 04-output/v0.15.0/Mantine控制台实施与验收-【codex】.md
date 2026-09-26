# Mantine 控制台实施与验收 v0.15.0-dev

日期：2026-09-26。用户授权：全面使用 Mantine 重绘 Gork 控制台，并保留切回旧主题的按钮。

## 已实现

对话、造价助手、角色、StopWatch、设置、运行日志六页统一视觉；保留左侧常驻机器人、动画和快捷表情。角色形象仍在角色页，操作 ID 与业务控制器保持兼容。主题按钮在右上角，默认 Mantine，可随时回到经典米白/橄榄绿主题并记住选择。切换只启停样式表，不替换 DOM、不刷新页面、不调用设备/语音接口。

采用正式 @mantine/core 9.6.2 的 Button、NativeSelect、Textarea、Switch、Checkbox、Paper、Title、Badge、Input；构建时由 React/ReactDOM 19.2.4 生成静态原生控件，原 app.js 负责交互。两套主题共享一套控件与状态，不再创建 React 状态副本。范围滑块和 details 交互保持原生；CSS 动态状态以原生 checked/disabled 为准。Mantine 行内变量导出到本地 CSS，原严格 CSP 保留，不添加 unsafe-inline、外部 CDN 或新网络服务。

模板 `03-Src/stopwatch-voice-companion/ui/console.html` 是 HTML 权威来源；生成的 `static/index.html`、`static/mantine/*.css` 随项目交付。原 `static/style.css` 本轮没有修改，经典兼容层只处理 Mantine 包装结构。运行 Gork 不要求先启动 Node/Vite。

## 验证结果

- 78/78 Node 测试通过：29 项桌面、45 项原网页/形象、4 项新增真实生成 DOM/主题检查。完整输出在本目录 `Node回归-【codex】.txt`。
- 新测试覆盖业务控件无丢失/重复、原生类型、严格 CSP、本机依赖；主题前置恢复/非法值/存储不可用；连续切换保留节点、草稿、聊天、选项、禁用状态、监听器和展开状态。
- 真实生成 DOM 加载原 app.js，模拟工作台与角色接口：文字发送仅一次，主题切换不重发、不新建头像；开关保存、输出路由、隐私撤销和标签导航通过。
- `npm run build:ui`、`npm run check:ui`、`npm audit` 均通过（0 漏洞）；桌面角色及固定上游形象导出检查通过。
- 隔离网页 8879：Mantine/经典主题分别在 1180×820、800×540、390×540 检查，document 尺寸等于 viewport，提交与主题按钮可见。记录见 `窗口适配检查-【codex】.json`。
- Mantine 六页在窄屏逐项检查，工作区无横向溢出；角色库可展开；新旧主题实测保留输入；刷新恢复已选主题。修复窄屏伙伴区自动网格行压缩导致的重叠。
- 本轮没有修改业务 app.js、后端行为、桌面窗口 IPC、语音服务或 Watch 固件；未进行真实云端请求、BLE 指令或录音。正式客户端/硬件验收不包含在以上结论中。

## 使用与边界

刷新现有控制台即可加载新界面；旧版本运行状态仍以当次 `/api/health` 为准，源码与运行进程版本分开。右上角按钮切换外观，不改变桌面浮窗皮肤或小人形象。主题偏好按当前浏览器 origin 保存：隔离 8879 的选择不会覆盖正式 8766。

已打开 8879 隔离预览供查看，该实例配置关闭自动 BLE/语音连接，未托管真实语音服务。常用语音/设备操作请回正式控制台。

## 文档与本地存档

已更新 README、模块 README、AGENTS、PRD 当前计划、设计规范、PRD 23、CHANGELOG（保留 5 版并归档旧记录）。按次版本更新规则建立本地 Git 界面存档分支 `codex/mantine-ui-v0.15.0`，包含当前电脑界面及其已有前端依赖；保留原工作分支、索引和其他未提交的固件/后端改动，不推送。

## 预览

- `Mantine-对话-【codex】.png`
- `Mantine-角色-【codex】.png`
- `Mantine-设置-【codex】.png`
- `经典-对话-【codex】.png`

## 上游与许可

官方文档：https://mantine.dev/getting-started/ 、https://mantine.dev/core/native-select/ 、https://mantine.dev/styles/styles-api/ 。
固定 npm 依赖见模块 package-lock.json；Mantine MIT 全文随 `static/mantine/LICENSE` 提供。原 Avatar Lab 来源与许可保持不变。
