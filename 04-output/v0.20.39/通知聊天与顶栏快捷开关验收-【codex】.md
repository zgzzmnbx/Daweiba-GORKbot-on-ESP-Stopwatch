# PC v0.20.39-dev 通知聊天与顶栏快捷开关验收

日期：2026-10-14。范围：Windows控制台与PC后端；Watch不改不烧录。

## 实施

- 顶栏删除「停止全部」按钮和重复「待机」文字，保留语音、Watch状态。右侧五个36px图标依次是通知哨兵、Codex哨兵、配色、明暗和架构图，窄窗口30px；有悬停说明、键盘焦点与可访问名称，哨兵以颜色/状态点和aria-checked反映已确认状态。
- 使用官方[Phosphor Icons](https://phosphoricons.com/) regular SVG，固定上游提交 `2b75f3ad12b420c9504ef05df8d2564a28f8500e`，保持原始文件及MIT许可。本地加载，原严格CSP不变。来源与许可见[本地说明](../../03-Src/stopwatch-voice-companion/static/icons/phosphor/SOURCE.md)。
- 通知快捷开关调用owner校验的暂停/恢复接口，暂停在途程序通知和租约，保留原来源令牌与权限；显式选择保存到既有本机登记配置。未知或无法保存时不冒充成功，不因不可读配置清掉来源登记。普通关闭应用的临时停止不改保存偏好；旧兼容轮询独立。
- Codex开关读取最新已保存设置后只切换enabled，保留模式/任务/输出/声音/阈值/额度圆环等设置，不提交完整页面的未保存编辑；不强制接管，下次启动默认关闭规则保持。
- 对话页只读复用 `/api/external/overview` 既有最近30条回执，各页面每2.5秒读取，隐藏停止。显示来源、时间、排队/完成/取消等真实状态，相同source/event_id更新原条目，不以「已接收」推导为已播放。
- 通知使用textContent显示，不写入AI上下文，不自动朗读；显式朗读、复制仍可使用。阅读旧消息时新通知不强制滚到底部。新会话清空后，旧回执和晚到旧快照不重现，新通知正常进入。

## 验证

- 后端全量 **254 passed**，覆盖授权、保存开关、重建后恢复、关闭不覆盖偏好、权限/令牌保持、不可读登记不覆盖、暂停拒绝新通知与原协议回归；两条既有Starlette/anyio弃用警告。
- 控制台 **110 passed**，覆盖事件去重、状态单向推进、新会话屏蔽旧回执、失败不误显示成功、Codex已保存设置保持及原语音恢复等回归。
- `npm run check:ui` 通过，生成HTML/CSS与模板及锁定依赖一致；`git diff --check`通过。
- [真实Electron结果](tests/result.json)：加载生产生成页、生产ES模块与严格CSP，HTTP替身隔离；Astra消息在对话页出现，状态更新不重复，HTML按文字显示，清空后旧消息不回流，新消息可见。实际点击通知暂停/恢复、Codex切换、配色与明暗，保持图标。
- 实窗检查经典、Mantine明/暗 × 1180/390两种窗口，共6组：无页面横向溢出，五图标完整不重叠。图片按设备缩放输出，CSS尺寸与实际截图像素不应混用。样例消息/金额不是真实业务结果。
- 首次隔离Electron由隐藏启动继承了隐藏状态，按预期不轮询通知；明确显示测试窗口后通过。原失败日志保留为`initial-hidden-fixture-failure.log`，不作为产品缺陷或通过证据。

![顶栏预览](tests/header-preview.png)

[暗色宽窗](tests/header-mantine-dark-1180.png) · [暗色窄窗](tests/header-mantine-dark-390.png) · [浅色宽窗](tests/header-mantine-light-1180.png) · [浅色窄窗](tests/header-mantine-light-390.png) · [经典宽窗](tests/header-classic-1180.png) · [经典窄窗](tests/header-classic-390.png)

## 运行边界与更新

正式8766只读复核：v0.20.38-dev，voice ready=true，Watch按键对话enabled=true、stage=ready；未刷新、重启或接管该用户窗口。源码/元数据v0.20.39-dev，新后台及完整功能从托盘正常退出、原入口重开后加载。当前真实Astra业务通知到正式新版聊天页的自然使用验收，须用户重开后观察；隔离测试不冒充真实业务事件验收。

未调用真实识别/合成/回答，不录音、不播放、不改代理/音色/许可或Watch；原性能/长稳延期保持。README、AGENTS、当前计划、最近五版CHANGELOG及历史归档、接口owner操作说明已更新；未提交/推送。
