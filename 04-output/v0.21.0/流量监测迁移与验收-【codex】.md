# 流量监测模块 v0.21.0-dev

## 范围与模块边界

来源为 Clash 项目 `desktop-monitor` 于 2026-10-15 的源码快照（原工具 README 标示 v0.1.0，Windows 历史模块当时正在继续开发）。移入命名管道客户端、连接增量账本、Windows 应用历史读取器；新建物理网卡读取、生命周期服务、控制台界面和桌面只读转发。Gork 不依赖来源项目目录、8769 服务或启动器，不改来源项目。

- `companion/traffic/`：单独封装采集、日累计 SQLite、开关持久化、异常/旧值与采集生命周期；无语音、Watch、业务模块依赖。
- `app.py`：仅挂载生命周期及 `/api/traffic` GET/PUT，PUT 沿用工作台 owner 校验。
- `static/traffic-ui.js` / `.css`：独立控制台模块；标题栏开关与数据来源切换。
- `traffic-relay.js` / `traffic-badge.js` / `.css`：Electron 主进程只读摘要转发、隔离 preload 订阅与悬浮显示，未修改共享角色 renderer。

## 使用和数据

正常托盘退出 Gork 后从原入口重开，确认版本 v0.21.0-dev。点击标题栏 `⇅` 开关开启；在「流量监测」标签查看数据。首次默认关闭，后续保留开关偏好。开启时每秒读取物理网卡和 Clash；Windows 应用历史每 15 分钟读取一次。关开关停止采集、等待在途有限超时读取结束、关闭账本，隐藏悬浮速度条；已采集记录保留。用户目录 `LOCALAPPDATA/GorkRobot/traffic` 保存 settings.json、traffic.sqlite3 及 windows-history.json，与原工具账本分开，不导入原账本。配置项 `traffic_data_dir` 可指定隔离数据目录。

悬浮窗隐藏/最小化停止自身摘要轮询；控制台页面隐藏停止页面读取。开启监测期间后端继续记录，控制台不在流量页时每 5 秒读取、流量页每秒读取。关闭整个 Gork 时清理后台任务、句柄与 SQLite。数据库以单采集进程文件锁保护，不自动清理累计历史；Windows 历史快照展示最近两日，后续快照覆盖旧快照。原工具日志不会迁入或删除。

| 展示 | 口径 |
| --- | --- |
| 整机实时网速 | 活跃物理 Ethernet/Wi-Fi 网卡 64 位计数差，包含代理、直连和局域网；排除虚拟/TUN/环回及过滤接口，不能当作纯互联网用量 |
| 实时代理速度 | Clash 采样连接中 PROXY 的上传/下载增量除以采样时间；不包含 DIRECT；短连接/尾部可能漏采 |
| 今日代理 / DIRECT | 北京时间当天 Gork 开启采集期间的已归属增量；停止期间不补计；启动首帧、断线恢复与内核重置建立基线 |
| 未归属差额 | 同一观察窗口的内核增量与已归属连接增量之差，允许暂时负值；不擅自归给某软件 |
| Windows 应用历史 | 系统按日记账，补充可被系统记录、但未经过 Clash 的应用；有更新延迟，无法单独判定是否全程绕过代理，不是实时 PID 统计 |

Windows 与 Clash 来自不同层次，禁止相加或相减推出“纯直连”。未知显示 `—`，不能显示成 0；停机/休眠长间隔和计数下降不显示速度尖峰。Clash 断线不阻断整机网速，Windows 失败保留旧值并标记。桌面 K/M/G 分别表示 KiB/MiB/GiB，↑↓速度均为每秒字节。

## 隐私与资源

全部读取仅发生在本机；不改变代理、节点、TUN、系统网络、语音许可或 Watch。命名管道只允许 GET，凭据仅用于内存认证；API 不回显配置路径、密钥、Windows 应用完整路径/网络名称。网页以 textContent 渲染进程名和域名。Clash 读取有 3 秒总截止及 16 MiB 限制，Windows 历史进程隐藏运行、30 秒超时。开关关闭时不再开始新读取，若 Windows 历史查询正在进行可能等待至超时完成。

Win32 GetIfTable2 直接取计数，避免每秒启动 PowerShell。历史查询低频使用 Windows PowerShell；采样约 1 秒，不承担全量抓包或服务商计费准确性。SQLite 在本机非同步目录，每次采样事务保存，以保留意外退出前已提交数据。

## 验证

- 完整后端回归 275 项通过；最后追加互斥采集和休眠保护后，流量专项 17 项通过。
- 控制台完整 122 项、桌面完整 49 项通过；最后修订后的流量前端/桌面专项 4 项通过。
- UI 生成一致性检查通过。生产生成 DOM、实际 Electron、严格 CSP：Mantine 深浅色和经典主题 × 1180/800 桌面宽度，共 6 组；真实 avatar.html/preload IPC 的 240×280、144×168、60×70 三档窗口通过。无页面脚本错误；标题栏开关、Windows 视图、普通状态刷新保留速度条、关闭隐藏已检查。截图是隔离样例，不是实际用量。
- 真实本机三路读取通过；7 秒隔离采集时 1 块物理网卡、47 条 Clash 连接、105 条合并后的 Windows 应用历史记录可读，速度均取实际计数。关闭后 0 个任务、SQLite 已关闭。计数随现场流量改变。
- 该 7 秒短测中 Python CPU 时间约 0.078 秒；不含独立 PowerShell CPU，不能据此宣称整机资源、一天运行或长稳已验收。
- 本轮未重启/接管用户正式 Gork，未改变正式开关；新源码须正常重开加载。没有手机验收、设备烧录、声音播放或云模型调用。

证据：`tests/electron-result.json`、`tests/live-read-result.json`、9 张 Electron 截图及源码 SHA256。README、AGENTS、当前计划及 CHANGELOG 已更新，主 CHANGELOG 保留最近 5 个版本，其余归档。

## 官方资料

- [GetIfTable2](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/getiftable2)：接口表与 FreeMibTable 生命周期。
- [MIB_IF_ROW2](https://learn.microsoft.com/zh-cn/windows-hardware/drivers/network/mib-if-row2)：物理接口、状态与 64 位字节计数。
- [AttributedNetworkUsage](https://learn.microsoft.com/en-us/uwp/api/windows.networking.connectivity.attributednetworkusage?view=winrt-28000)：按应用历史聚合，有记账延迟，不是实时计数器。

## 本地 Git 备份

按第二位版本升级规则，将当前源码、文档及可公开验收材料保存到独立本地分支 `codex/backup-v0.21.0-20261015-traffic`。快照同时保留工作区中先前已存在的 PC/Watch 源码改动；主分支 HEAD、原索引与工作区保持原状，不执行 reset/stash/checkout，不推送。凭据、本机配置、流量数据库、设备恢复资料、依赖和临时文件未新增入库。
