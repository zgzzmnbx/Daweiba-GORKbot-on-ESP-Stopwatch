# 动效编辑器实施与验收

日期：2026-10-03。电脑端源码 v0.19.0-dev；Watch 源码/编译候选 v0.10.0-dev；设备 app0 仍按上次验收记录为 v0.9.1-dev，本轮未读取或写入设备。

## 1. 交付结论

已把 Windows 交接包的四场景、四笔型动效编辑器接入当前控制台和桌面共享资源链。原始用户 JSON 保留，编辑、预览、撤销、重置、导入导出、版本化正式保存、桌面立即应用及失败重试已实现。Watch 参数转换、四场景/四笔型 C++ 状态机与绘制已完成编译和主机仿真。

Windows Electron 的真实进程、窗口、DOM 操作、IPC 与播放器链路自动验收通过；这不同于 DOM harness，也不替代用户对视觉风格的主观验收。Watch 未刷机、未进行实屏或 BLE 实机验收。运行时 Watch JSON 参数下发未实现；本期选择同一保存配置导出头文件后重新编译的路线。当前电脑 API 对旧 Watch 明确拒绝新场景，原有表情和控制继续保留。

已有未提交改动先完整备份，未 reset/clean/stash、未暂存/提交/推送、未发布、未刷机。隔离测试服务器及 Electron 测试窗口已经退出；最后只读探测正式 8766 不可达，本次没有启动或重启正式服务。

## 2. 使用方法及配置位置

1. 正常启动本项目 Gork 电脑端。若之前的旧进程仍在运行，由用户正常退出并重新启动一次，加载 v0.19.0-dev。
2. 点击控制台“动效编辑器”，选择待机、加载、书写或疑惑。首次正式存储为空时，自动读取用户原始参数；以后读取最新有效保存版本。
3. 修改字段只影响编辑器草稿预览；可撤销、重置、导入和导出。系统启用减少动态效果时显示“静态预览”；“播放循环”只在本页启用动态效果。
4. 点击“保存并应用桌面”。已写入磁盘且小人播放器返回应用 ACK 后显示“已保存 rN，桌面小人已应用”，无需重启小人。桌面应用失败与磁盘保存失败分别显示，可重试应用已保存版本。
5. “读取保存版本”处理旧窗口冲突；localStorage 草稿恢复必须明确选择。两份正式文件都损坏时，先显式导入有效 JSON 再恢复保存；损坏原文件另存保留。
6. “导出 Watch 参数”输出已保存版本的 Watch JSON 和 `motion_config.h`。把头文件放入候选工程 `src/motion_config.h` 后重新编译；本功能不会连接或写入设备。

正式配置：`03-Src/stopwatch-voice-companion/motion.local.json`；有效备份：同目录 `.bak`。均已加入忽略规则。初始原始用户快照：`static/motion/initial-config.gork.json`，1869 字节。保存 schema 为 gork-motion-studio v2，外层带 revision；Watch 导出 schema 为 gork-watch-motion v1/sourceVersion=2。

完整接口、每字段范围、球面投影、坐标缩放、四笔型与时序映射见 [PRD 32](../../00-docs/00-PRD/32-v0.19.0-动效编辑器接入与Watch映射-【codex】.md)。

## 3. 修改清单

| 区域 | 修改与新文件 |
| --- | --- |
| 本机后端 | `companion/motion.py`；app.py 配置保存/恢复/Watch 导出接口与同源嵌入；control.py 新场景桌面白名单及旧 Watch 拒绝 |
| 控制台 | `ui/console.html`、生成的 static/index.html、app.js；两套主题样式；static/motion/ 配置/编辑/场景/笔/播放器/适配器/用户快照/许可 |
| 共享渲染 | gork-avatar.js 的一次表情返回 idle 接缝；tools/export_desktop_avatar.py 同步完整 motion 资源及生成白名单 |
| Electron | motion-bridge.js 保存修订和 ACK；main.js/preload.js/avatar.js/avatar.html；motion/ 生成副本 |
| Watch | src/motion_config.h、motion_config.watch.json、motion_scene.h/cpp、motion_draw.h/cpp；avatar_engine.h/cpp 接口及 dirty-rectangle 路由；main.cpp 候选版本 |
| 验证工具 | convert_gork_motion.py、test_motion_native.py、verify_motion_electron.cjs、run_motion_preview.py、integrate_motion_assets.py、export_motion_source.py；后端/控制台/桌面测试及 motion 测试 |
| 项目上下文 | README、项目 AGENTS、PRD 02/32、CHANGELOG 与历史归档；后端/固件 README、第三方声明 |
| 交付证据 | 本目录真实 Electron 截图/JSON、回归/编译/C++ 日志及明确标注“未刷机候选”的固件文件 |

根仓库与嵌套固件仓库原有改动均保留。导入没有覆盖当前共享 avatar-engine/avatar-presets，没有更改 Android、语音协议、加密绑定、全局 Codex 配置或上游许可证。

## 4. 测试命令与结果

以下命令在项目根执行，npm 命令注明工作目录。Python 使用现有项目环境，不用全局环境替代。

| 测试 | 命令 | 实际结果 |
| --- | --- | --- |
| 原有及新增 Python | `Codex-Temp/.venv-companion/Scripts/python.exe -m pytest 03-Src/stopwatch-voice-companion/tests -q` | 115 passed；两条既有依赖弃用提示 |
| 控制台回归 | 后端目录执行 `npm test` | 57 passed |
| 桌面回归 | gork-desktop 目录执行 `npm test` | 31 passed，包括保存修订、发送窗口验证、ACK/失败 |
| 交接包及生产适配器 | 后端目录执行 `npm run test:motion` | 7 个脚本通过；render.test 是 editor-render 的兼容别名，无需重复执行 |
| UI 生成检查 | 后端目录执行 `npm run check:ui` | 通过，未只改生成 HTML |
| 桌面资源导出 | `Codex-Temp/.venv-companion/Scripts/python.exe tools/export_desktop_avatar.py --check` | 通过；重跑导出仍保留新资源、用户快照与许可 |
| Watch 确定性参数 | `Codex-Temp/.venv-companion/Scripts/python.exe tools/convert_gork_motion.py --check` | 通过；全部字段、笔型与非法版本/数值测试通过 |
| Watch 主机 C++ | `Codex-Temp/.venv-companion/Scripts/python.exe tools/test_motion_native.py` | 640 帧 C++ 栅格通过；全部姿态字段与 JS 误差 <=0.004 |
| Watch 真正编译 | `Codex-Temp/.venv-platformio/Scripts/python.exe -m platformio run --project-dir 03-Src/stopwatch-grok-avatar` | SUCCESS；RAM 64,440/327,680 (19.7%)，Flash 1,727,829/6,553,600 (26.4%) |
| whitespace 与配置审阅 | 根和嵌套仓库 `git diff --check`，本次文件定向敏感信息扫描 | 通过；不暂存或提交已有其他改动 |

Motion 测试覆盖：schema/20 KiB/未知字段/版本/范围/类型/v1 迁移；保存重启、并发冲突、磁盘原子替换失败、备份回退、显式恢复；进入/循环/一次/完成/取消；系统减少动态效果、隐藏/恢复、BFCache；1000 次新旧场景切换、100 次播放器销毁重建，单 RAF 和监听清理；保留其他角色和自选彩色 Gork。

原始用户配置逐字段一致，初始 JSON 与包内文件逐字节一致。原始用户参数 208 帧、默认/最小/最大/混合边界 208 帧、四笔型 172 帧实际原生 Canvas 像素测试通过，clip 被禁用，不依赖头部裁剪隐藏越界。用户配置最大前景半径 184.077，边界 213.008，均在测试半径 233 内。笔尖跟踪笔迹末端、换行抬笔、黑白及四种不同笔型检查通过。

C++ 640 帧覆盖用户/最小/最大/混合参数、四笔型和四场景；非黑像素最大半径 199.449，低于 Watch 可绘头半径 216.8 测试容差，测量包围盒包含全部绘制像素。参数表 304 字节，单姿态 148 字节，没有新增产品全屏帧缓存或逐帧堆分配。原有 60fps 门控保留，主机约 850ms 的 640 帧执行时间不能当作 ESP32 帧率。

本机没有宿主 g++，C++ 运行用已有 Docker 镜像 `weknora-bundle/docreader:v0.8.2-3c36e7e7` 中 g++；临时容器 `--rm --network none`，只挂载显式准备的本次 native 测试文件。未启动或变更 WeKnora 等正式服务，未安装编译器。测试工具允许 `GORK_NATIVE_IMAGE` 显式指定有 g++ 的既有镜像。

## 5. 真实 Windows Electron 验收

工具：`tools/verify_motion_electron.cjs`，实际 Electron 44.4.3、本项目正式 main/preload/renderer。使用隔离 backend/profile/配置路径，设备和语音自动连接及哨兵关闭。执行真实页面事件、HTTP 保存、IPC、播放器读取，并用 capturePage 保存实际窗口。

| 验收项 | 实际证据与结果 |
| --- | --- |
| 四场景保存立即生效 | r2 idle/r3 loading/r4 writing/r5 question，播放器配置逐项等于保存配置，场景和玩家类型一致；通过 |
| 参数变化 | idle 间距/位置，loading.scale，writing.x/penStyle/strokeWidth，question.speed/bob 改动后逐项读取桌面播放器；通过 |
| DPI/布局/缩放 | 强制 150% DPI，1180×820、820×650、390×700 实际窗口；小人 25%/75%/150%；无横向溢出，iframe 正确占满可用区；通过 |
| 桌面应用失败 | 注入播放器 setConfig 拒绝，磁盘 r6 已保存但界面准确报告应用失败；恢复后重试通过 |
| 重载保持 | 真实小人 renderer 重载读取 r6 且参数保留；服务器存储重建在 Python 测试验证；通过 |
| 离开编辑页 | iframe src 移除，播放器页面生命周期清理；通过 |
| 加载顺序/控制台错误 | 实际 Electron consoleErrors=[]；通过 |

截图：[正常控制台](Windows控制台-【codex】.png)、[窄窗口](Windows窄窗口-【codex】.png)、[待机](桌面-idle-【codex】.png)、[加载](桌面-loading-【codex】.png)、[书写](桌面-writing-【codex】.png)、[疑惑](桌面-question-【codex】.png)。结构化结果：[Windows-Electron验收结果](Windows-Electron验收结果-【codex】.json)。

验收为自动真实窗口操作，不把它称为用户本人点击验收；系统动效偏好由程序正常遵守。正式配置和系统偏好未被隔离测试改写。完整 Gork 主进程重启后的真实设备联动、用户视觉认可仍需使用者验证。

复测真实 Electron 时，在两个终端中使用空的新测试目录/隔离端口；不得复用正式 8766 或已有真实用户配置：

```powershell
# 终端一（仅本机隔离服务，自动连接关闭）
& 'Codex-Temp/.venv-companion/Scripts/python.exe' tools/run_motion_preview.py --port 8879 --directory 'Codex-Temp/motion-preview-new'
# 终端二；Electron 测试目录固定在 Codex-Temp/motion-electron/profile
$env:GORK_BACKEND_PORT='8879'
& './03-Src/gork-desktop/node_modules/electron/dist/electron.exe' tools/verify_motion_electron.cjs
```

测试结束退出隔离服务。测试脚本要求首次配置与用户初始值一致，重复测试须选择新目录，不用强制删除正式保存值。

## 6. Watch 真机待验项目

| 项目 | 本轮状态 | 之后的验收口径 |
| --- | --- | --- |
| app0 写入与设备版本 | 未执行 | 当次授权后重新探测设备身份/端口，应用区写入及工具校验；不擦除/改分区 |
| 四场景和四笔型实屏 | 待测 | 检查左右眼、头部角度、圆内边界、笔尖/笔迹、问号和各笔型可辨性 |
| 一次/循环/完成/取消/回退 | 主机通过，实机待测 | 固件命令验证；legacy idle 回旧待机、motion idle 恢复；快速切换无残影 |
| 帧时间/内存/长稳 | 编译预算通过，设备待测 | 观察平均与最大帧耗时、原 dirty-rectangle、屏幕响应、长时间循环和 Watchdog |
| BLE 鉴权/断线/重连/音频并行 | 旧回归通过，新设备待测 | 已绑定合法端命令回执；陌生端拒绝；重连后旧表情/文字/朗读正常 |
| 保存配置下发 | 仅构建时导入 | 保存→导出→替换头文件→重编候选；运行时 JSON 上传接口未交付 |

候选固件文件：[StopWatch-v0.10.0-dev-未刷机候选](StopWatch-v0.10.0-dev-未刷机候选-【codex】.bin)，仅供审阅与后续当次授权，不代表设备已更新。

## 7. 保护与回滚

任务开始前，根仓库与嵌套固件各 30 份已有未提交文件的原始字节已放入 `Codex-Temp/pre-motion-editor-20261003-085814/dirty-files.zip`，含此前哨兵改动、交付记录和快捷方式；两仓工作 diff/暂存 diff、状态清单也已保存。已有改动不以 HEAD 版本替换。

本次准确增量见 `Codex-Temp/motion-integration-review/manifest.json`、`motion-integration.patch` 及 `before-after.zip`。before 为任务开始时已有工作区内容（优先原始备份，其余原先干净文件取本仓 HEAD），after 为本次交付；新增文件单列。保护核对结果在同目录 preservation.json，历史 dirty 文件中不属本次范围的文件按字节保持一致，暂存区保持任务前状态。

需要回滚时先备份后来新增修改，按清单只还原本次的 before 文件或逆向应用对应 hunk；本次新增文件只在确认未产生后续编辑后移入待确认目录。不整仓 reset/clean，不自动还原整个旧备份，不影响先前 Codex 哨兵等工作。正式 motion.local.json 用户保存结果应另行备份保留。

README、项目 AGENTS、PRD、CHANGELOG 已同步版本与验收边界；CHANGELOG 保留最近五版，原 v0.18.0 记录已转入历史归档。遵从本轮明确范围，没有执行版本升级默认的本地提交。
