# Watch v0.11.1-dev 重影修复候选

2026-10-04。PC 源码 v0.20.0-dev；Watch 当前实屏版本 v0.11.1-dev；镜像已仅写入 app0 并独立读回通过，用户重启确认版本正确、目前没有重影。完整表情场景、帧率及长稳仍待验证。

大尾巴先确认设备实屏显示 v0.11.0-dev，随后提供眼睛重影照片。启动/版本子项 PASS_DEVICE，视觉 FAIL_DEVICE；不能把烧录校验或启动子项扩展为 T11 整组通过。照片保存为同目录 `用户反馈-v0.11.0重影-【codex】.png`。

## 原因及修复

旧表情使用 GrokRenderer，新四场景/待机使用 MotionDraw。旧表情返回新待机时，MotionDraw 仅擦除自身上一帧/当前帧范围；旧眼睛比新眼睛更宽、位置不同，超出范围的像素遗留。原代码已处理新动效进入旧表情方向，遗漏反向交接。

`src/avatar_engine.cpp` 在实际渲染新动效前检查旧渲染器有效范围，仅交接帧重建背景，并清掉旧范围标记；随后帧沿用原局部刷新。没有重写几何、改变动效参数或改为每帧全屏刷新。`src/main.cpp` 固件版本改为 v0.11.1-dev。PC/网络/语音/绑定/音量产品源码本次不变。

## 验证

- 修复前：提取真实生产 `AvatarEngine::render` 的 MotionDraw 分支、脏矩形合并/清除函数，配合真实 GrokRenderer/MotionScene/MotionDraw 进行连续像素比较，104 次旧表情返回新待机的 1765 帧均存在残留。日志 `Codex-Temp/ghost-v0111/before.log`。
- 修复后：`tools/test_motion_refresh.py` 在 466/468 两尺寸分别验证 3530 帧、104 次旧表情进入四场景；合计 7060 帧、208 次交接，与干净参考帧逐像素完全一致。覆盖长时间待机眨眼和中断切换，并断言仅交接/初始帧清屏，持续帧不清屏。日志 `tests/连续刷新.log`。
- 既有 `tools/test_motion_native.py`：真实 C++ 640 帧、四笔型、原值/上下界/混合参数、1000 次状态切换及取消通过；C++/JS 全姿态字段比较通过。这是宿主栅格替身和生产代码测试，不能代替设备显示驱动/真机帧率。
- PlatformIO 锁定工程构建成功，静态 RAM 118120/327680 字节，程序 Flash 2227185/6553600 字节，应用镜像 2227552 字节。完整日志在 `tests/构建.log`。构建时未连接串口或操作设备。

之前针对 AMOLED 直绘偶数对齐限制做过单独宿主排查，但当前修复的确定复现来自渲染器交接，不将直绘/帧缓冲分配失败当成已确认根因。本机锁定 M5GFX 使用可选 AMOLED 帧缓冲；外部 API 背景可查 [M5Stack StopWatch 显示文档](https://docs.m5stack.com/en/arduino/stopwatch/display)，本次根因依据为本地生产代码和修复前后测试。

## 新镜像及现场验收

候选：`firmware/StopWatch-Gork-v0.11.1-dev-app.bin`。

拟写范围：重新枚举 USB、核对 ESP32-S3 和当次设备 MAC/当前 app0，仅写 app0 `0x10000`，执行写入工具校验及独立 `verify_flash`。保留 NVS、BLE 绑定、分区和 bootloader；不整片擦除，不修改永久安全状态。依据项目 AGENTS“每次新镜像/回退写入遵循当次授权”，用户随后明确回复“授权烧录，我已进入烧录模式”，已在本次授权范围执行。

写后必须由大尾巴观察 Settings 中 v0.11.1-dev，再连续观察待机，切换旧表情后自动返回、A/B/触摸多次切换、进入/退出设置与气泡。当前观察消影子项已由用户确认通过；完整场景、闪屏/帧率仍为 NOT_RUN；听验、配网、PTT 与 T12/T13 保留原任务书范围，未完成。

旧 v0.11.0 镜像及 v0.9.1 恢复应用保留原路径。现有源码 Git 存档 `b11de22c536b67b51e7121b50738b0a6e28db313` 保留；本次改前两份源文件及上下文备份在 `Codex-Temp/ghost-v0111/baseline/`。未提交或推送本次修复。

README、项目 AGENTS、当前版本计划、CHANGELOG（保留五版本）和 A01–A46 矩阵已更新，旧版本移入历史归档。最初读取8766未监听；随后已正常重开，当前运行状态见下方追加。

## 本次授权后的写入结果

重新枚举唯一ESP USB为COM5，ROM实测 ESP32-S3 QFN56 rev0.2 / PSRAM8MB / Flash16MB，MAC与既有Watch匹配。读取分区得到app0 0x10000、大小0x640000，OTA有效seq=1选择app0。先独立verify_flash确认旧应用仍匹配保留的v0.11.0，再write_flash 0x10000写入2227552字节，工具Hash verified；另起独立verify_flash为digest matched，最后hard_reset。仅应用范围擦写，无NVS/绑定、分区、bootloader和永久安全配置写入。完整设备日志留在本机忽略目录Codex-Temp/ghost-v0111/的chip.log、flash-id.log、partition-read.log、ota-read.log、verify-old.log、write.log、verify-new.log。

设备现在应用镜像为v0.11.1-dev；用户已确认实屏版本/启动及当前观察无重影，完整场景与性能仍待验证。未重开串口监视器，以免USB DTR/RTS干扰正常启动或BLE验收。

现场网络与PC追加：本轮随后正常重开Gork，当前8766返回v0.20.0-dev，8766/8765均仅127.0.0.1监听；电脑实际连接vivo X200 Pro的2.4GHz热点，IP 10.33.72.210/24。Watch BLE仍离线，尚未安全配网。
再次启动入口打开控制台的工具调用被自动审批返回blocked by policy；未重试该启动命令。尝试现有小人控制台按钮时，被Windows新通知覆盖，输入工具拒绝点击并未操作遮挡窗口；未修改任何全局设置。手动打开控制台即可继续本机安全配网。

现场反馈追加：2026-10-04 大尾巴反馈：“我已经重启watch，版本正确。目前看没有重影”。v0.11.1-dev 正常启动/实屏版本 PASS_DEVICE，当前观察消影 PASS_DEVICE 子项；尚未覆盖全部表情循环、长稳或设备帧率。
BLE自动连接仍报WinError -2147024874“设备不识别此命令”，未配网；不把消影子项通过扩展为T11或整体任务通过。

## Bluetooth 实屏与只读诊断（2026-10-04）

用户照片显示 Control ON、Link Connected、Pair window closed、Binding Saved、Security SC + encrypted GATT；绑定仍保存，链路显示已连接。照片保存为 `用户反馈-v0.11.1-Bluetooth状态-【codex】.png`。正式 PC /api/health 同时仍为 connected=false，在服务发现时报 WinError -2147024874；两者分别代表设备链路状态与 PC 完成 GATT 发现/订阅状态，不能互相替代。

本机 WinRT 只读探针确认 Windows paired=True，能够获取表情与短音服务/特征/描述符；音频与配网服务查询报上述错误，完整 Uncached 服务查询报 -2147418113。Cached 服务表含表情 handle40、音频55、短音70、重复短音85，未列配网服务。未配对/清绑定、写特征或开启通知，未改 Windows 蓝牙设置。旧服务缓存/新增服务位置是排查方向，尚不能认定唯一根因。

对照当前源码，v0.11 新配网服务在旧音频/短音前注册，改变旧服务句柄位置；旧 v0.9.1 基线先表情、音频、短音。锁定 ESP32-S3 SDK 已启用自动 Service Change。参考 [Microsoft GattServicesChanged](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.bluetoothledevice.gattserviceschanged) 与 [Bleak 上游相同 WinRT 错误报告](https://github.com/hbldh/bleak/issues/1123)，外部报告仅提供排查背景，不是本机根因证明。

已通过浏览器 Skill 在本机 Gork 页面正常取得工作台控制权并重新扫描，仍未发现广播；配网页面热点名称填写为当前电脑实测 `vivo X200 Pro`，密码框留空，没有提交配网、打开云上传或实体 PTT。请求用户仅切换 Watch BLE OFF/ON，保持 Saved 绑定，再观察重连。
