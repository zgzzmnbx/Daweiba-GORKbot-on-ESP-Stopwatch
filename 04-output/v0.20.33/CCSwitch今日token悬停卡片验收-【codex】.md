# CC Switch 今日 token 悬停卡片验收

版本：PC v0.20.33-dev。日期：2026-10-14。

## 本次行为

鼠标移到桌面悬浮小人时，在旁边显示今日token卡片；移开150ms后收起。卡片不抢焦点、不接管点击，原小人的拖动、点击打开控制台与鼠标跟随保留。键盘聚焦小人也可显示，Esc关闭。独立窗口保证小人大小25%时仍能阅读；卡片随位置与置顶偏好移动，屏幕边缘自动换侧，隐藏/最小化/退出停止查询。

卡片显示今日总token、输入（含缓存）、输出、其中缓存、请求次数、最近计数与读取时间。明确标注「CC Switch · 本机 Codex」与「北京时间」，不当作整个账号、其他电脑、云端或ChatGPT全部用量。

## 计数来源与口径

复用已安装CC Switch v3.20.3的SQLite计数数据，默认当前用户`.cc-switch/cc-switch.db`。后端可用`CC_SWITCH_HOME`或`ccswitch_db_path`指定实际库，读取模式`mode=ro`及`PRAGMA query_only=ON`；保留WAL中的已提交数据，同一只读事务读取明细与日汇总，不复制数据库、不修改表或索引、不扫描原Codex日志、不调用CC Switch重建。

按北京时间00:00至次日00:00筛选`app_type='codex'`，供应商/模型不限。适配CC Switch v3.20.3的`fresh_input_sql`和`effective_usage_log_filter`，明细与`usage_daily_rollups`相加，最终使用Dashboard的`real_total_tokens`口径：

`新鲜输入 + 输出 + 缓存读取 + 缓存创建`

输入语义0/1/2分别处理，缓存包含在输入时先归一再汇总，避免重复相加。继承CC Switch已经计数的结果；不再自行重算会话分叉。session/proxy同请求沿用其成功代理、10分钟匹配窗口、计数指纹及unknown模型匹配规则。未来CC Switch升级需再核对口径，字段缺失或未知输入语义显示不兼容。

已核对的固定版本源码与许可证：

- [输入语义与缓存](https://github.com/farion1231/cc-switch/blob/v3.20.3/src-tauri/src/services/sql_helpers.rs)
- [汇总与跨来源去重](https://github.com/farion1231/cc-switch/blob/v3.20.3/src-tauri/src/services/usage_stats.rs)
- 项目内来源及MIT许可保留在`03-Src/stopwatch-voice-companion/CC_SWITCH_NOTICE.md`。

## 模块与时效

- `companion/ccswitch_usage.py`：只读、线程内查询、2秒查询预算、20秒缓存、并发合并、Schema与数值检查。
- `GET /api/desktop/token-usage`：沿用既有本机Host/来源限制，只返回聚合计数与时间，不返回库路径、供应商身份、请求正文或凭据。
- `token-window.js` / `token-hover.js` / `token-card.html/.css/.js`：独立悬停窗口与渲染，通过受限preload事件连接main；只有小人可请求显示。

仅悬停时每20秒读取，移开停止。CC Switch自身同步决定计数时效；Gork读取成功不能证明CC Switch已经同步最新会话，因此卡片同时显示最近计数和读取时间。读取失败保留同日上次数字并标记「上次统计」；跨日清掉旧值。缺库、不兼容和未取得数据均显示「—」，合法空日才显示0。

## 验证结果

| 验证 | 结果 |
| --- | --- |
| Python新模块＋相关后端回归 | 58项通过（含9项新增），覆盖输入语义、缓存、proxy/session去重、跨午夜、其他工具排除、rollup、空日/缺库/不兼容、WAL只读、缓存/跨日、锁/损坏、实际API聚合输出 |
| 桌面回归 | 47项通过；最终生命周期/IPC/渲染定点7项再次通过 |
| UI生成一致性 | `npm run check:ui`通过，控制台生成资源无改动 |
| 共享角色资产一致性 | `python tools/export_desktop_avatar.py --check`通过 |
| 本机真实CC Switch数据 | 只读生产适配器与独立v3.20.3汇总公式逐值一致，原数据库主文件未因读取改变；证据`live-parity.json` |
| 隔离Electron实际窗口 | v0.20.33-dev的生产main/preload/avatar/card运行，Chromium鼠标移入/移出、独立窗口、不抢焦点、25/100/150%大小、150%显示缩放、错误/缺库、隐藏恢复、Esc/聚焦、无语音/设备请求均通过；证据`electron-result.json` |
| 正式加载 | 结束时确认原Gork已关闭、8766未监听，备份原窗口状态后用原启动入口正常打开；正式health返回v0.20.33-dev，token接口实际读CC Switch返回available及当天真实计数。证据`formal-runtime.json` |
| 截图 | 已核对正常、缺库、旧值状态及三尺寸，卡片无横向溢出、底部完整可见 |

实库对照样本读取于2026-10-14，98条已同步请求，`real_total_tokens=19,291,147`；这是验收快照，生产数字继续随CC Switch更新。实窗使用该真实计数的脱敏聚合快照以及异常替身，不连接正式声音、设备或业务程序；不把截图数字作为当前恒定值。

可复用脚本：`tools/verify_ccswitch_usage.py`（本机只读对照）、`tools/verify_token_hover_electron.cjs`（独立实窗验收）。前者仅写安全聚合证据，不复制CC Switch数据库或凭据。全部过程、现有工作备份和早期失败保留在`Codex-Temp/ccswitch-hover-20261014/`。

## 加载与项目状态

源码/桌面与控制台包元数据/后端版本标识同步v0.20.33-dev。README、项目AGENTS、当前版本计划及CHANGELOG更新；CHANGELOG只保留最近5版，v0.20.28移入历史归档。

结束时只读确认原Gork进程已关闭、8766未监听。备份原`window-state.json`后，用原`start-gork-console.cmd`正常打开；正式health确认v0.20.33-dev，`/api/desktop/token-usage`实读available，2026-10-14的当次快照25,784,794 tokens。无需用户再次重开；该快照继续随CC Switch同步变化。

本轮未接管已有语音owner，未修改许可/网络/音色/输出设置。Watch不改不烧录，原性能与长稳延期保持。未提交/推送。
