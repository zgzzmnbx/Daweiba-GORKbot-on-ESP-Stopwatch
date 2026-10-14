# Astra 完成金额播报与手动验收

PC v0.20.27-dev，2026-10-08。用户授权 Astra 与 Gork 联动，批量匹配完成后播报金额；最新要求由用户手动测试，不由助手发起新匹配或模拟播放。Watch 固件、绑定、网络配置与声音偏好保持。

## 实现及金额边界

- 复用原任务哨兵及 Astra 只读 monitor，身份严格为 `zhisuan-astra`。首次读取建立历史基线，不补播旧完成任务；后续按 event_id / attempt 去重。
- 只有成功 `match_result` 接受 `amount_summary`，且金额 attempt 必须等于该事件 attempt。缺失 / 非法金额沿用原固定提示，失败节点不播金额。
- 契约：`value` 为元的非负十进制字符串，`currency=CNY`、`unit=yuan`，`basis=tax_included|tax_excluded`、`calculation_status=recalculated|unconfirmed`。最多 6 位小数且不超过 1 万亿元；不接受指数、NaN、布尔值或额外私有字段。精确 Decimal 格式化，不由模型推算或补价。
- Astra 侧从本次费用汇总的万元金额转换为元，在真实完成节点固化；Gork 不跨 attempt 追补当前可变汇总。源数据口径及其精度仍由 Astra 负责。
- 示例：`匹配完成，含税总额123456.78元。`；未确认重算时为 `匹配完成，表内含税总额123456.78元。公式重算未确认。`；需复核时追加 `请复核。`。这不等于确认最终造价。

## 声音与控制权

常规里程碑继续读取固定短句缓存。金额动态合成复用当前用户的语音会话、合成路径和已选音色；云端路径核验已有文字上传许可，不自动打开许可。生成期间登记正常取消请求，人工语音、会话 / 所有权变更、许可撤销和来源切换优先，迟到结果不播放。

电脑动态 WAV 以内存同步播放，不持久化业务金额语音；`completed_by_os` 表示系统播放函数返回。Watch 复用现有 Opus / PCM 音频链路，保留设备时长与回执限制。显示目标 `both` 与声音位置 `pc|watch` 独立，两端显示不代表两端同时出声。

## 当前交付状态

- [x] 41 专项（金额 / Astra 来源 / 任务哨兵）回归，全部后端 212 项、前端 96 项通过；UI 构建及生成一致性通过。
- [x] 正式 8766 正常重开加载 v0.20.27-dev。之前只读确认语音服务就绪、保留 cloud / Cherry，不改变用户音色选择。
- [x] 用户接手前只读设置：enabled=false、source=legacy、mode=auto、target=both、sound=true、sound_kind=speech、sound_target=pc；history=[]。
- [ ] 用户在正式窗口应用 Astra 来源及启用，建立历史基线。
- [ ] 用户运行新匹配，核对本次金额、事件 attempt 与 Gork 最近提醒及实际听感；桌面 / Watch 显示和设备播放分别确认。

此前用户按物理 Esc 终止 UI 操作，未应用新的哨兵设置。助手不再操作窗口、不发起模拟事件、不自动请求云合成或播放，也不修改用户测试期间的设置。源码修复不等于真实播报验收。

## 用户手动测试

1. Gork → 造价助手 → Gork 任务哨兵：开启，任务来源选“智算 Astra · 5189”，自动跟随，显示两端。
2. 勾选声音，方式选“语音播报”（未刷新旧页面显示“本机固定短句播报”），声音位置选电脑，点击应用设置。
3. 等状态成功且最近读取时间更新，再在 Astra 新对话按完整流程确认结构、开始批量匹配。历史完成任务不补播。
4. 完成后把播报与本次费用汇总核对，注意元 / 万元与含税 / 不含税口径，以及公式重算未确认提示。
5. 看同页“最近提醒”的金额及声音状态；`completed_by_os` 不证明实际扬声器可闻。Watch 输出需单独选择并完成耳听确认。

只读诊断 `GET /api/cost/sentinel` 的 `history[].amount_summary`、`speech`、`delivery.sound` 可核对播报内容和返回状态。不要取新 UUID 或替换工作台控制权来操作真实窗口。

## 关联源码

`companion/cost.py` 校验金额，`control.py` 管理动态合成 / 取消，`task_monitor.py` 构造文案与逐端返回结果；`tests/test_amount_sentinel.py` 覆盖金额、许可 / 迟到结果、会话 / 音色与两种声音位置。界面源 `ui/console.html`，产物使用 `npm run build:ui`，不手改 `static/index.html`。

保留原工作树改动，未提交 / 推送。不改 Watch，不恢复已延期的性能或长稳测试。
