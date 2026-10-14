# PC v0.20.8-dev 启动残留检查与验收

用户明确授权给原启动脚本增加清理兜底。start-gork-console.cmd在启动Electron前调用tools/gork-startup-preflight.ps1，快捷方式保持原目标。仅对监听应用端口、健康app/instance/PID匹配、精确项目venv argv和可执行路径匹配、具有Electron启动标记且祖先已退出的后台回收。兼容Windows venv包装进程；祖先PID被复用时按创建时间判断旧祖先已退出。具有仍存活启动进程的后台保留。缺健康响应、非项目进程、独立启动后台均不自动终止；活跃旧版Gork提示托盘退出，同版本活跃实例正常唤起。

通过Windows原生CommandLineToArgvW解析参数，避免空格/中文或路径子串误判；清理前重新计算归属计划及核对PID/创建时间/可执行路径/命令，逐个确认进程身份后停止。等待进程结束和端口释放后才启动；检查、清理或记录失败则停止启动。每项目互斥避免并行回收，默认8766且沿用既有GORK_BACKEND_PORT，自定义端口无效明确失败。PowerShell5.1中文源码带UTF-8 BOM，无固定COM、电脑路径或外部运行依赖。只读InspectOnly不写清理日志、不杀进程、不启动程序。未监听或无法核实的进程不会因名称相同被终止。

验证：37桌面回归全部通过。新增专项包含16个决策/Windows argv场景：空闲、活跃主进程、活跃旧主进程、venv/直连孤立后台、父PID复用、活跃外部父进程、独立当前/旧后台、精确脚本/可执行路径、健康PID、无响应端口、多监听者和中文/空格参数。真实Windows使用隔离含中文/空格路径，模拟HTTP服务与无窗口启动替身运行原cmd：孤立服务被终止且继续启动；独立服务保留且继续启动；其他服务保留、入口非零退出且不启动。另验证自定义端口、无效配置拒绝、InspectOnly保留进程及日志历史不含命令正文/启动标记。fixture端口18868无Watch或云请求，不用正式8766做杀进程试验。最终专项与完整桌面日志、integration-evidence.json见tests/。

运行区分：最近正式health为0.20.7-dev，AI配置接口HTTP200、本机key_saved=true（只读布尔状态，不读取/回显凭据）。本轮只对正式实例执行只读检查，识别活跃旧版本并保留；没有强制结束它、重新启动它或发模型请求。源码/PC元数据为v0.20.8-dev，用户从托盘退出后再点原快捷方式加载；新运行版本和真实问答/PTT/听感仍待现场核对。Watch v0.11.5保持，不改网络/蓝牙/固件，不烧录/提交/推送。

README、两模块README、项目AGENTS、当前计划、工具说明及CHANGELOG已更新，最近5版之外归档。变更前定点备份在Codex-Temp/startup-v0208/baseline/，原有dirty工作保留。启动日志在Codex-Temp/gork-startup/preflight-last.json和preflight-history.jsonl，仅存时间/结论/清理PID，无Key、热点密码、命令正文或健康完整响应。
