# Gork v0.18.0-dev Codex 哨兵实施与验收

日期：2026-09-29。范围依据：`00-docs/00-PRD/30-v0.18.0-Codex哨兵PRD-【codex】.md` 与任务书 31。结论限定为本地源码、自动回归和隔离 UI；正式 8766、正式 Electron、Watch 和 hook 信任均未验收。固件、Android、全局 Codex 配置、既有 Codex 任务均未修改。

## 实施 T00–T11

| 任务 | 结果与落点 |
| --- | --- |
| T00 | 核对本机 CLI 0.153.4 schema 和官方 app-server/hooks；脱敏基线保存在 `Codex-Temp/codex-sentinel-research/`。新 app-server 仅用于读取额度，不代表现有桌面任务实例。 |
| T01 | `codex_source.py` 建立 JSONL/hook 白名单规范化事件，丢弃正文、工具参数及账户内容；`codex_monitor.py` 给出来源能力、时间和状态。 |
| T02 | `QuotaRPC` 短生命期握手、`account/read` 账号类型判断、`account/rateLimits/read` 只读额度；按实际桶/窗口呈现，2 分钟自动刷新、5 秒合并手刷、超时与取消。 |
| T03 | `tools/codex_sentinel_hook.py` 有时效租约和队列预算，空 stdout 退出；`tools/codex_sentinel_hooks_config.py` dry-run 合并/移除自有条目。未执行 `--apply`，未修改全局 hooks/trust。 |
| T04 | `JsonlSource` 有界尾读、部分行、旧日期目录低频发现；首次基线及每次启用/恢复的事件时间门槛防旧终态补播。 |
| T05 | `CodexMonitor` 跟踪多个线程/轮次、来源能力、去重、旧轮乱序、120 秒 stale；等待审批仅由已核实的 hook 产生，JSONL 不假称具备此能力。 |
| T06 | `NotificationCoordinator` 统一造价/Codex 排队和有效展示，人工 15 秒优先，失效提醒取消，单音目标；停止取消队列和自身在途音频。 |
| T07 | FastAPI `/api/codex/sentinel` 只读 GET、owner 保护 PUT、额度手刷、启动默认关闭及全局停止；新标签页取得/明确接管工作台。 |
| T08 | Mantine/经典共用控制器：来源/任务/额度状态、线程选择、阈值、提示目标、开关、失败说明；`npm run build:ui` 生成静态文件。 |
| T09 | Electron 主进程白名单传递额度摘要，小人单/双细环、未知/过期状态、键盘详情；环层级高于 canvas。 |
| T10 | 自动回归、实际只读额度/会话日志采样及隔离浏览器记录见下表。 |
| T11 | 控制服务、UI 包与 Electron 同步 v0.18.0-dev；README、AGENTS、当前计划、CHANGELOG 与本记录更新。本地 Git 恢复快照见文末。 |

## 本机真实来源与边界

- 本机 Codex CLI 0.153.4 的 app-server 只读额度调用返回 `rateLimitsByLimitId`，隔离服务实际观测到 **1 个桶、1 个窗口**，状态为 available。页面显示当前监测账号，不读取或保存 `auth.json`；额度环数据不是任务进度，也不是项目配额。具体剩余百分比随时间变化，本记录不固定数值。
- 本机实际 `sessions/YYYY/MM/DD/*.jsonl` 含 `event_msg.payload.type=task_started/task_complete` 和 `turn_id`；读取器只留会话 UUID、轮次、事件类型与时间。只读 JSONL 能识别“运行/本轮结束”，不能可靠提供审批、补充输入、整轮失败或子代理终止语义；控制台按来源列出能力。开启前缺少开始事件的长轮次，可能直到下一轮才可信识别。发现上限为最近修改的 40 个文件，每秒只扫今天/昨天，旧日期目录每 60 秒低频发现；迟发现历史事件按 `occurred_at` 门槛抑制提醒。来源时间戳缺失的终态不提醒。
- Hook 官方接口可提供 `PermissionRequest`、`PreToolUse`、`PostToolUse`、`Stop` 等信号；桥仅接收白名单字段。`Stop` 是一次轮次停止，其他 hook 可使其继续，不能称整个目标完成。尚未安装或获信任，因此真实待审批提醒和正式 hook 路径为 **UNSUPPORTED/待人工启用**；单测只证明桥到 spool 的功能链路。
- Hook 桥输入预算为 1 MiB；如 `Stop` 附带的 `last_assistant_message` 使整包超出预算，桥会安全空输出，该次结束事件可能遗漏。JSONL 后备仍可提供本轮结束，但不能承诺每个 Stop 事件均由 hook 收到。桥从不保留该正文。
- 隔离服务端口与假数据预览均不属于正式客户端。A36 环的 `?case=` 预览使用标注示例数据，不是实时额度；正式 Electron 听验保留。

## 自动验证

| 命令 | 结果 |
| --- | --- |
| `python -m pytest -q`（companion 目录） | 105 passed；含 Codex 19 项、造价哨兵及原有控制服务回归。 |
| `npm test`（companion 目录） | 56 passed。 |
| `npm test`（gork-desktop 目录） | 30 passed。 |
| `npm run build:ui` / `npm run check:ui` | Mantine 9.6.2 静态生成及锁定依赖一致。 |
| `git diff --check` | 无补丁空白错误。 |

隔离网页 A35：主线程实屏检查 Mantine/经典在 1180×820、800×540、390×540 下均无全页水平溢出；版本、开关可见，切换主题保留输入值。隔离小人 A36：双环层级修复后，在示例 double/single/stale/unknown 情况下均复核可见，键盘详情可读；证据 `Codex-Temp/codex-sentinel-research/avatar-double-verified.png`。这两项为 **PASS-UI**，不代替正式 Electron。历史误报修复后，主线程重新启动隔离服务并观察超过 70 秒，最近提醒仍为空；此项是 A20 的额外 **PASS-UI** 证据。隔离额度实际返回一个 7 天窗口。新页面在后端重启后实屏完成“默认关闭→启用→关闭→再次启用→停止全部→开关与两通道关闭”。旧标签页的明确接管入口会调用原生确认，内置浏览器无法完成该弹窗；接管后端由双 client API 回归覆盖，实际手动交互仍待正式环境。

## A01–A40 逐项结论

标记含义同任务书：PASS-AUTO 为程序化回归，PASS-LOCAL 为实际本机只读取样，PASS-UI 为隔离浏览器；PARTIAL 表示相应测试覆盖不完整，不能记为 PASS。

| 项 | 结论 | 证据与限制 |
| --- | --- | --- |
| A01 | PASS-AUTO | API 测试每次启动默认关闭，偏好不触发自动监测。 |
| A02 | PASS-AUTO | Codex/造价独立配置及生命周期。 |
| A03 | PASS-AUTO | 双 client 共用单个后端 monitor，额度读合并；接管 API 与过期租约恢复均覆盖，原生确认弹窗实屏待正式环境。 |
| A04 | PASS-AUTO | CLI 不存在返回明确状态，服务保持可用。 |
| A05 | PASS-AUTO + PASS-LOCAL | 实际 RPC 读取成功；注入提前返回的 ID、未知通知/ID，验证按 ID 匹配及只读请求序列。 |
| A06 | PARTIAL | API Key/未登录分类和认证错误分支实现，未用真实异常账号试验。 |
| A07 | PASS-AUTO | 0/25/100、null、越界/非有限数单测。 |
| A08 | PASS-AUTO | 0/1/2 窗口及未知单测/桌面渲染测试。 |
| A09 | PASS-AUTO | 多桶按单桶选取测试。 |
| A10 | PASS-AUTO | reset 已过期只标 stale，不推算恢复。 |
| A11 | PARTIAL | 退避/TTL 源码与单元覆盖，真实断网恢复未验证。 |
| A12 | PARTIAL | 合并/取消机制，未做并发压力和真实进程长稳。 |
| A13 | PASS-AUTO | 30→19→18→24→25→19 时序仅两次低额提醒。 |
| A14 | PASS-AUTO | JSONL 新轮开始/结束和桌面 working 路径。 |
| A15 | PARTIAL | PermissionRequest 桥链路测试；waiting_input 无本机可信信号，正式审批待 hook 信任。 |
| A16 | UNSUPPORTED | 现有真实来源不区分工具失败继续与整轮失败，不显示伪状态。 |
| A17 | UNSUPPORTED | idle/notLoaded/SessionEnd 不映射为完成；无可信事件。 |
| A18 | UNSUPPORTED | 子代理结束不映射父轮完成；无可信父子关系。 |
| A19 | PASS-AUTO | 重复、旧轮乱序与同轮恢复回归。 |
| A20 | PASS-AUTO + PASS-UI | >40 历史文件延迟发现、旧文件 mtime 更新及恢复时间门槛单测；隔离重启后观察 >70 秒无历史提醒。 |
| A21 | PASS-AUTO | 两次轮询间新文件同时开始/结束只报一次。 |
| A22 | PASS-AUTO | 无新证据过期及再更新测试。 |
| A23 | PARTIAL | 多任务/固定任务状态代码已接线，完整消失/恢复交互未单独实屏。 |
| A24 | PASS-AUTO | 残行、坏 JSON、截断建基线、追加、重命名及旧目录增量回归。 |
| A25 | PASS-AUTO | hook/JSONL 敏感字段注入，状态和历史只留白名单。 |
| A26 | PASS-AUTO | 关闭无租约 no-op、桥空 stdout、spool 消费测试；正式 hook 未安装。 |
| A27 | PASS-AUTO | dry-run 合并/撤销自有项与他人项不变；`--apply` 未执行。 |
| A28 | PASS-AUTO | 白名单与 Host/Origin/owner 校验、超过 1 MiB hook 输入安全空输出且不落盘。 |
| A29 | PARTIAL | 人工窗口、排队取消及共享协调测试；真实 Watch 音频占用待设备。 |
| A30 | PASS-AUTO | 两个生产 monitor 同时 Watch 提醒，断言无重叠。 |
| A31 | PASS-AUTO | 排队旧状态失效即取消。 |
| A32 | PASS-AUTO + PASS-UI | 全局停止关闭监测、清队列/额度进程；隔离页刷新确认开关和两通道关闭，正式音频听验待人工。 |
| A33 | PARTIAL | 离线/失败分栏源码；真实 Watch 待人工。 |
| A34 | PASS-AUTO | 当前固定短句均在 24 字/72 UTF-8 字节内。 |
| A35 | PASS-UI | 两主题×三尺寸实屏，主题切换保留输入。 |
| A36 | PASS-UI | 隔离示例小人单/双/过期/未知与键盘详情；正式 Electron 待人工。 |
| A37 | PASS-LOCAL | 真实官方 RPC 额度 1 桶/1 窗口，隔离页面显示。 |
| A38 | PASS-LOCAL | 本机会话真实 JSONL 结构/增量核对，无正文保留。 |
| A39 | PENDING-MANUAL | 正式 Electron、hook 安装/信任后的新任务链路待用户。 |
| A40 | PENDING-MANUAL | Watch 实屏、短音可闻与长稳待用户。 |

## 人工门禁与恢复

正式启用前确认正式 `/api/health` 已显示 `0.18.0-dev`，再由用户在控制台 Codex 页显式开启。若需要审批提醒，先审查配置工具 dry-run 与目标 hooks.json，再由用户决定安装/信任；信任前 JSONL 仅有运行和本轮结束。正式 Electron 的双环、通知占用及 Watch 显示/短音需按新任务现场记录，不能由模拟/回执替代。出现误报可关闭 Codex 页滑块；“停止全部”无需 owner 也关闭当前后端监测。下一次服务启动仍默认关闭。Git 恢复快照只供本地回退，不代表正式实例已加载。

本地快照引用：`refs/codex/v0.18.0-local-snapshot`。通过临时 index 写入 `commit-tree` 和该 ref，原 `HEAD`、用户 index、dirty 工作区均保持原状；`git show --stat refs/codex/v0.18.0-local-snapshot` 可审查范围，`git diff HEAD refs/codex/v0.18.0-local-snapshot -- <路径>` 可按文件检查/恢复。快照包括 v0.17.1/0.17.2 尚未提交的直接基线依赖，排除本机缓存、密钥、隔离临时文件和无关快捷方式。
