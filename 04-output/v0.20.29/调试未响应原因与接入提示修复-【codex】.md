# 调试未响应原因与接入提示修复

日期：2026-10-08；Gork 源码/正式运行 v0.20.29-dev，接口协议保持1.0。以下初始排查为历史现场，最新配置见末节。

## 现场原因

用户在智算“机器人联动 → 调试”点击匹配失败，截图底部仅出现 `EXTERNAL_CLIENT_DISABLED`。只读现场确认：Gork 28已加载、Wi-Fi通信正常；Astra来源 enabled=false，显示端desktop/watch、声音权限为空、最高优先级2。同时旧兼容哨兵正跟踪 Astra。智算自动通知、声音均关闭，当前通用通知历史为空。请求被来源启用门禁挡住，未形成Gork接收回执；不是信号已经输出却设备无反应。

按原先用户选择，程序首次登记须启用一次，显示/声音权限由用户选择；本轮不擅自启用来源，不关闭正在使用的旧哨兵、不授予语音权限，不发正式测试输出。

## 修复

- Gork 来源卡明确显示“旧轮询正在使用此来源，先关闭兼容轮询再启用程序”，提供“打开兼容轮询设置”入口；只展开设置，不修改权限。
- 无旧轮询但来源关闭时，显示点击配置、勾选“启用这个程序”并保存的具体路径。
- 协调 Astra 线程修正按钮附近反馈和连接状态中文提示、登记入口及拒绝/接收状态，不再只在页面底部显示原始错误码。

Gork 新提示为静态文件修复，现有28后端已具备所需接口，Ctrl+R刷新可加载；正式显示版本仍28，正常重开后源码版本29。没有以源码版本冒充运行版本。

## 操作路径

1. Gork → 通知哨兵 → 打开“兼容轮询·原版造价/Astra”，关闭旧Astra任务哨兵。
2. 程序接入中的“智算 Astra” → 配置 → 勾选“启用这个程序”并保存。维持两端显示；当前不需要声音权限。
3. 智算 → 机器人联动 → 重新检测 → 调试 → 发送此阶段信号。调试按钮独立于自动业务通知开关；不会启动真实匹配。

启用不会补发此前被拒绝的信号，须重新点击发送。后续需要声音时分别授予Gork允许的声音端并启用智算阶段语音，沿用当前音色和声音位置。

## 验证

100 项前端回归通过，包含旧轮询占用的显式入口、不发API请求或改授权、非冲突来源关闭的提示。build:ui/check:ui生成一致性通过。48个真实Electron布局通过：三主题×四宽度×概览/编辑/兼容轮询/冲突状态；均无控件越界/重叠，冲突提示真实可见。证据 `tests/frontend-100.log`、`tests/external-layout.json` 和同目录截图。

原后端接口未修改，不重复声称正式输出或人耳验收通过。

Astra v0.9.23 已同步原活动 C 目录并正式构建，Ctrl+R可加载，无后端改动/重启。两目录各152前端、48项Gork Python、类型检查/构建通过，原启动CheckOnly Ready。实际正式UI来源关闭中文状态和按钮旁“暂不可发送：Astra来源未启用，先关闭旧轮询再启用来源”已核验，没有正式发送。隔离覆盖点击被拒绝、未知网络结果不确定、本地pending/远端completed、逐端中文回执、取消未确认及亮暗显示；截图复制至 `tests/astra-feedback-disabled-light.png` / `astra-feedback-cancel-dark.png`。用户在Astra线程要求的左下角实际构建版本号随本次一起完成。其 README/DESIGN1.0.7/AGENTS/PRD/CHANGELOG及交接记录已同步。

## 后续授权代配置及正式调试

2026-10-08用户在Astra协同线程明确要求代为设置，随后正常托盘退出Gork。协同线程确认8766离线并备份本机来源、旧轮询及Astra配置后，关闭旧Astra兼容轮询，启用既有Astra推送来源；独立令牌不旋转，显示权限desktop/watch、声音权限pc、最高优先级2。原启动脚本正常重开，未接管原owner或强杀运行程序。Astra正式活动工作区自动阶段提醒、声音开启，显示both、声音pc、配置revision1。

Gork线程再次独立只读核对：正式v0.20.29-dev，robot_connected=true，voice.ready=true，Watch按键enabled=true/stage=ready；cloud/Cherry/speaker_id3/speed1.0保留，旧轮询enabled=false/source=astra，新Astrapolicy enabled=true，状态ready。此次只应用已授权配置，不增加软件版本或修改固件、设备网络。

协同线程发送独立、明确标注模拟数据的金额12345.67元调试；未发起真实匹配或改动业务金额。正式查询最近回执再次确认event `2b36427ab77a40ebba093905d1ff1d26`、stage match_completed、status completed、desktop displayed、watch accepted、speech completed_by_os，error为空。Watch接收不等于实屏已确认；声音目标电脑，系统播放结束不冒充人耳听感。下次真实业务完成事件仍待自然使用确认，历史任务不补播，性能/长稳仍延期。

协同证据：[Astra代配置记录](D:/Codex-Temp/260613-【智算Astra】/00-docs/handoff/2026-10-08-机器人联动代配置.md)，其忽略目录下`Codex-Temp/gork-link-setup/settings-ready.png`、`amount-receipt.json`、`final-state.json`。本项目README/AGENTS/当前计划/PRD39/CHANGELOG已同步最新状态；未提交或推送。
