# 额度读取失败诊断与有限重试验收

PC v0.20.38-dev，2026-10-14。

## 现场原因与边界

正式v0.20.37的quota-usage接口最初返回unavailable且无历史窗口；直接调用已安装CLI 0.153.4时，account/read返回ChatGPT登录类型，account/rateLimits/read间歇报-32603。安全分类确认错误为failed to fetch / error sending request，目标chatgpt.com；不是未登录，也不是额度已用完。

Codex应用官方只读入口同刻返回已用43%、剩余57%，后续独立CLI及正式Gork接口也重新取得57%。本机代理监听、显式代理、无代理环境/系统代理做了对照，成功和失败均会出现，不能据一次成功断定某条代理/NO_PROXY配置有误；本轮未修改全局、用户或应用代理设置，也未读取/复制凭据。

接口继续使用[官方App Server的account/rateLimits/read](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt)，remaining=100-usedPercent，保留真实窗口与重置时间，不用token总数估算订阅百分比。

## 修复

- QuotaRPC只对-32603中明确的网络传输错误进行最多3次尝试，间隔250/500ms，共享原12秒总预算，不把超时扩大成36秒。
- 每次尝试沿用只读初始化、账号状态、额度读取；失败/成功/取消均清理本次子进程。登录、占用、协议和未知内部错误不盲目重试，不发起任务、登录、额度重置或自动审批。
- 上游原始消息仅用于本地分类，不回显或持久记录。后端区分network_error、timeout，卡片说明「额度网络连接失败，将自动重试」或「额度读取超时，将自动重试」。保留原成功120秒缓存、失败30秒退避、同进程旧值/过期标记、独立今日token读取。

## 验证

| 检查 | 结果 |
| --- | --- |
| Python相关回归 | 65项通过：新网络错误分类/三次上限/单总预算、认证错误不重试、进程清理、不泄漏错误内容、失败退避后恢复，以及原Codex/CC Switch/后端逻辑 |
| 桌面定点回归 | 8项通过，包含网络失败/超时提示与原未知/旧值/卡片生命周期 |
| 新源码真实API | 隔离ASGI生产路由、无lifespan/设备启动，实际访问官方额度：第2次尝试成功，约2.95秒，available/57% |
| 独立真实RPC | 两次读取均成功，分别第2次约3.14秒、第1次约1.54秒；均57%。证明实际遇到的传输失败可在本次读取内恢复 |
| 正式现用接口复核 | 仍v0.20.37，后续实际接口已返回available、57%、stale=false；没有强制重启、接管或伪造缓存，新重试源码仍待正常退出重开 |

真实新路由/RPC证据见live-result.json、live-quota.json，现用接口复核见formal-quota.json；只保存安全聚合字段，不保存账号身份、密钥或重置券。数值是当次快照，不保证后续永远57%或所有网络故障都能在12秒内恢复。

重复验证脚本位于Codex-Temp/quota-recovery-20261014/verify_live.py；定点备份及安全诊断保留在同目录。版本、README、AGENTS经验、当前版本计划和CHANGELOG已更新，CHANGELOG保留5版。Watch固件、网络、语音owner/许可/音色不改，未烧录、未提交推送。
