# Watch v0.11.5-dev 底部黑条修复候选

日期：2026-10-04。用户实机v0.11.4-dev报告：下方文字已隐藏，但黑条遮挡元素。

## 原因与修改

`main.cpp` 的空闲音频提示虽然改为空字符串，200ms更新分支仍无条件执行 `fillRect(60,420,346,20,TFT_BLACK)`，覆盖圆体/书写元素。提取 `renderAvatarWithAudioHint` 后，仅真实录音或音频忙态绘制背景/提示。提示结束时在本帧 `avatar.update` 前调用一次 `avatar.invalidate`，由生产渲染重建当前背景和元素，之后继续局部刷新。空闲“Avatar audio ready”保持隐藏，真实录音/发送提示保留。

相对v0.11.4只修改上述主循环显示逻辑、版本和专项验证；保留此前Wi-Fi/BLE共存修复。没有改配网、网络身份、音频协议、驱动、绑定、分区或NVS。

## 验证

- `tools/test_motion_refresh.py` 提取生产motion render、invalidate、底部提示函数，以真实motion/grok绘制实现逐像素对照；Docker离线已安装编译器运行。
- 466/468尺寸共7060帧，208次旧表情→四场景切换，无残留像素。
- 两尺寸共400提示帧，忙态及REC提示绘制正常；每尺寸两次隐藏均于同帧恢复完整参考画面。后续待机没有提示黑条写入，没有多余全屏刷新。
- 锁定PlatformIO构建通过：RAM118504，程序2229585；应用镜像2229952字节。产物 `firmware/StopWatch-Gork-v0.11.5-dev-app.bin`。
- 用户当次授权后v0.11.5已仅app0写入并独立校验通过；实屏黑条消失、录音提示、真机帧率及长稳待验，不能以宿主像素回归代替实屏验收。

## 网络现场

用户更正热点密码后，公共状态和USB STATUS证实Watch已获10.33.72.225，运行固件v0.11.4。PC网络检查为NETCORE-New/192.168.2.4；生产客户端的同Wi-Fi子网校验拒绝跨网目的地。已请用户切回vivo X200 Pro。公共状态中旧设备认证快照不能当作当前持续连接；PC当前offline，完整互联仍待验证。未读取/输出密码。

## 写入边界

项目AGENTS要求“每次新镜像/回退写入遵循当次授权”。构建候选可供审核，本次v0.11.5已获用户“烧录允许”，仅写当前app0并独立校验，保留热点/绑定/设置；不回退到存在共存崩溃的v0.11.3。

README、AGENTS、当前版本计划、CHANGELOG已同步；CHANGELOG保持最近5个版本，旧条目归档。未提交/推送。

## 当次授权后的写入证据

重新枚举唯一ESP USB候选COM5，核对ESP32-S3、MAC 28:84:85:44:6c:00、Flash16MB；读取实际分区和OTA，确认app0 0x10000/0x640000、OTA序列1。先独立verify_flash确认设备旧v0.11.4匹配，再仅写2229952字节v0.11.5应用（擦写扇区0x10000–0x230fff）。工具Hash verified及随后独立verify_flash digest matched通过，执行hard reset。七份工具日志保存于tests/。没有写NVS/分区/bootloader。

写后USB运行握手暂未成功，已请用户不要按烧录键正常重启并核对Settings版本/黑条。不能把写入校验当作启动或视觉验收。PC当前Wi-Fi IP 10.33.72.210/24，已回到Watch所在热点子网；正式PC公共状态仍offline，等待设备正常启动后验证。

## 正常重启与用户实屏验收

用户明确确认“版本正确，黑条消失”，本次黑条修复的实屏子项通过。USB STATUS运行握手证实v0.11.5-dev，配置保留，热点IP 10.33.72.225且authenticated=true。

正式8766 PC v0.20.1-dev在用户切回热点后，20秒内5次公共状态采样均wifi_connected=true、设备authenticated=true、route=wifi、error为空，设备boot/session未变化（tests/wifi-health.json）。这是现有正式网络管理器与Watch持续状态请求/回执证据，不另建TLS客户端抢占连接。先前offline来自电脑离开热点，回同子网后自动连接。

本次显示修复、实屏版本和同热点基础认证/心跳互联已证实；业务表情/文字/音频、真实PTT/听感、BLE后备和长稳门禁仍须分项实测，不以20秒心跳当完整Wi-Fi或原目标验收。项目上下文已同步，无提交/推送。
