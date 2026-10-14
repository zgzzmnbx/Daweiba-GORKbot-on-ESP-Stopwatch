# KK — M5Stack StopWatch Avatar

## 2026-10-05 Watch v0.11.10-dev 千问连接播报候选，待当次烧录授权

按用户本轮要求实际用北京DashScope qwen3-tts-flash/Ethan生成固定“Wi-Fi 已连接。”“蓝牙已连接。”各一次，保存原16k单声道WAV、来源参数及增强PCM头文件（1.600/1.120秒），无每次重连云等待。Wi-Fi获得非零IP/可信BLE连接稳定300ms各播一次，双链串播；不依赖Gork启动，不据此宣称当前选用传输通道。录音准备/录音/音频任务优先，回答PCM/Opus和短音可抢占提示，候选最多等待10秒，失联/静音/取消清旧提示，本地提示不发id=0 BLE终端事件。保留六内置短音/GATT/用户参数及v0.11.9录音开头保护。

生产main集成+SoundControl C++和WAV逐样本、生产头像/录音含回答抢占回归通过，35音频/短音/GATT通过，锁定构建SUCCESS（RAM118568、程序2321973、app2322336bytes）。实际当前应用最后写入并独立验证v0.11.9，v0.11.10未烧录，待当次新镜像授权；实机可闻/抢占和首字确认仍需用户，性能/长稳仍延期。PC源码v0.20.25/正式最近v0.20.24不变，本轮不重启正式Gork、不改网络或许可、不提交推送。见04-output/v0.11.10/千问连接播报实施与验收-【codex】.md。以下为历史快照。

## 2026-10-05 Watch v0.11.9-dev 已授权烧录并独立校验，正常启动/首字待确认

用户本次回复“授权”后，于2026-10-05T20:14:04+08:00重新枚举COM5并核对唯一USB序列/物理MAC、ESP32-S3/PSRAM8MB/Flash16MB、app0 0x10000/0x640000及OTA有效序列1。旧v0.11.7独立verify_flash通过；仅写2234400bytes新v0.11.9 app，写入Hash及另进程verify_flash均通过，执行hard reset。热点、蓝牙绑定、设置与其他分区保留；包含v0.11.8 BLE自定义回执修复。

已写入校验不当作正常启动/实屏/首字录入通过，须用户核对Settings v0.11.9-dev并在红色REC出现后立即说完整短句；500ms启动采集保留后才亮REC，总10秒含准备期。性能/长稳仍延期。PC源码v0.20.25-dev，正式最近读取v0.20.24-dev、云端识别/合成已应用、Ethan；未重启Gork或由助手调用云。见04-output/v0.11.9/烧录与校验记录-【codex】.md。以下为历史快照。

## 2026-10-05 PC v0.20.25-dev / Watch v0.11.9-dev候选：默认云端与录音开头保护

Gork语音识别/合成默认云端，一次迁移旧本地路由偏好，以后手动选择、既有音色及独立上传撤销保留；默认设置不录音/不调用云。正式当次0.20.24-dev已确认cloud/cloud、Ethan，未刷新或重启用户窗口；新默认源码下次加载，版本显示正常重开后更新。

Watch旧REC在异步录音请求入队后立即显示，且单块20ms采完再排队存在采集空档风险。v0.11.9改为两块提前入队、按完成槽数计数、独立连续offset，保留500ms启动采集前缀后才亮REC/发送RECORDING；结束排好的最多40ms尾部后停，取消立即停。500ms是基于本次“前半秒漏录”症状的保护值，未测定硬件启动时长；总10秒含准备期，REC后约9.5秒。包含v0.11.8 BLE自定义回执修复，原版待机/用户参数/热点和绑定保留。

94前端、24音频协议/GATT及生产C++头像/录音回归通过，生成一致性及锁定构建成功（RAM118528、程序2234029、app2234400bytes）。新v0.11.9未烧录、待当次授权，实际最后已确认v0.11.7；首字录入改善须实机确认，性能/长稳仍延期。README/AGENTS/计划/CHANGELOG更新；见04-output/v0.20.25/默认云端与录音开头保护验收-【codex】.md。以下为历史快照。

## 2026-10-05 Watch v0.11.8-dev 回执修复候选（待本次烧录授权）

Windows服务缓存已定向重配恢复；用户确认BLE短按红色REC和直接Watch朗读可用。按键问答在“我的书写”阶段断开，定位为固件返回中文显示名而PC要求ASCII精确token回执。v0.11.8新增协议名称并用对应大写token回复，保留中文名称和全部动画参数。生产C++回归、14项协议/GATT检查、锁定构建通过，app2234080字节；实际Watch仍v0.11.7，未烧录。PC正式及源码v0.20.17不变；新镜像仅在获得当次授权后写app0并独立校验，保留热点/绑定。性能及长稳仍按用户要求延期。见04-output/v0.11.8/自定义表情蓝牙回执修复验收-【codex】.md。以下为历史检查记录。

## 2026-10-04 用户确认与本轮验收范围调整

用户针对“最新固件v0.11.7写入校验已通过，录音提示、双端书写和实际听感仍缺完整确认”回复“已经完成”（原消息“一斤完成”）。这三项更新为用户实机确认完成，不再重复列为缺失确认；未提供新的分段延迟、帧率或量化对照数据，不推导为性能验收通过。

用户明确“真机性能与稳定性先不测了”：T12/T13的性能对照、批量对话/故障恢复、8小时长稳、资源循环、电池对照及回退验证延期，不执行、不标PASS，也不再当作本轮必须继续跑的工作。原完整验收标准保留用于以后恢复。

已核对v0.11.7源码，Settings → Network已有三档策略：Auto WiFi first / BLE only / WiFi only。点第一行轮换到BLE only会保存策略、关闭Wi-Fi并停止相关网络入口，热点和蓝牙绑定不清除；选择Auto WiFi first恢复热点尝试。若Bluetooth的Control为OFF，用户须先点BLE ON。首次应用保存约延迟300ms且避开音频忙，重启后恢复策略。菜单功能已存在，本轮不改代码、不构建或再烧录。

“选择蓝牙模式”与“Windows完整服务发现/旧通信已恢复”分开记录：菜单路径有源码依据，旧电脑蓝牙发现异常未因本次记录自动关闭，基础通信仍需实际选择后核对。完整边合成/边传/边播尚未实现，保留PRD36后续路线；不因用户实机确认推导为流式完成。PC当前源码版本保持v0.20.17-dev，正式运行版本另行读取。本轮仅更新记录，不改网络、服务、绑定或设备。

见04-output/v0.11.7/用户确认与连接模式说明-【codex】.md。以下为历史快照。

## 2026-10-04 最新：Watch v0.11.7-dev 已授权烧录并独立校验，正常启动待确认

用户本次“执行烧录”授权后，重新枚举唯一ESP USB设备COM5并核对物理MAC 28:84:85:44:6c:00、ESP32-S3/PSRAM8MB、Flash16MB；读取分区/OTA确认app0 0x10000/0x640000、有效序列1。独立verify_flash确认旧v0.11.6匹配；仅写2234144字节v0.11.7应用，工具写入校验及另进程独立verify_flash均通过，执行hard reset。热点、蓝牙绑定与设置分区未写入。记录时间2026-10-04 21:16:38 +08:00；详见04-output/v0.11.7/烧录与校验记录-【codex】.md。

已请用户正常重启并核对Settings v0.11.7；校验不等于设备启动/实屏/录音/可闻验收。PC源码v0.20.12-dev，运行版以当次health为准，仍须原快捷方式正常重开加载布局/书写联动与默认按键预热；本次不重启电脑程序、无云请求。T12/T13、BLE备用、长稳和提速实测保留。以下为历史快照。

## 2026-10-04 当前：PC v0.20.11-dev 源码 / Watch v0.11.7-dev 编译候选，待当次烧录授权

按键对话首次默认开启；保存手动关闭选择。只在本窗口已有语音会话/控制权、已应用设置及原有上传许可齐全时请求启用，拒绝后不随每次轮询重试。启用只提前协商麦克风关闭的音频会话，新物理短按才允许 PRODUCT_ARM。缓存核对链路/boot/session及失败状态，手动关闭、取消和退出清理；首次按键保留空闲 HELLO，蓝键/准备时再按/中断旧播放仍取消。

移除每轮后固定1秒等待，准备提示及红色REC切换立即进入绘制，不受同状态200毫秒刷新节流；REC仅麦克风真实启动显示。会话耗时补充录音准备、录音到电脑及传输与播放。202项Python（含24协议项）、78前端、生产C++头像/录音及预热/取消、7060局部刷新帧/400提示帧、生成一致性及锁定构建通过；无真实模型请求或当前候选设备验收。

本轮只读现场核对正式8766为v0.20.10-dev、Wi-Fi已认证、按键对话启用且有真实录音上传进度；新PC源码尚需从托盘退出后用原快捷方式正常启动。Watch已写入v0.11.6，v0.11.7尚未写入、须当次授权。Opus现仅回答播放传输，录音回传仍PCM；完整边生成/边传/边播未实现，已列PRD36路线和验收。见04-output/v0.11.7/。README/AGENTS/当前计划/CHANGELOG和模块文档已更新；未提交/推送，原T12/T13、备用BLE、长稳及听感门禁保留。以下为历史快照。

## 2026-10-04 当前：PC v0.20.10-dev / Watch v0.11.6-dev 已写入，实屏待验

Watch 默认待机恢复原版：旧固件启动时启用了动效编辑器的四场景 idle，与桌面原版不同；本次启动和自定义单次播放结束均回到原版，保留眨眼、转头和交互。黄色 G2/A 改为短按开始录音、再按结束并发送，松开不结束；蓝色 G1/B 取消，A+B 进入设置，最长10秒和许可/断线/超时门禁保留。准备期间再次短按取消，诊断 Audio test 的按住/松开逻辑保留。

当前库修订14的“我的加载1”“我的疑惑”“我的书写”已独立编入 Watch，保留名称和全部参数，电脑表情菜单可发到 Watch/两端，设备翻页也能选择。一次后回原版待机，循环可用待机结束；修改参数后需重新导出/编译/授权烧录，参数标识不匹配会拒绝，避免播放旧效果。同步固件书写扩展范围并加圆体裁剪，保留用户参数。

170 Python、76前端、37桌面、生产C++头像/录音状态机、640几何帧和C++/JS姿态比较、7060局部刷新帧/400提示帧、生成一致性及锁定构建通过。用户本次“允许烧录”后重新枚举COM5、核对MAC/16MB/app0/OTA1、独立验证旧v0.11.5，仅写app0 0x10000并独立verify_flash通过，保留热点/绑定。设备最后已验运行仍v0.11.5；v0.11.6正常启动、原版待机实屏、三个表情和真实短按录音/问答/听感待用户确认。正式8766当前健康检查不可用，PC源码v0.20.10须原快捷方式正常启动。见04-output/v0.11.6/原版待机与短按录音及三个表情验收-【codex】.md。未提交/推送；Wi-Fi/BLE长稳门禁未完成。以下为历史快照。

## 2026-10-04 当前：底部黑条修复 v0.11.5-dev 实屏通过；同热点Wi-Fi认证/心跳通过

用户报告空闲文字已消失、底部黑条仍遮挡元素。定位到主循环每200毫秒仍对提示区执行黑色fillRect；源码已改为仅录音/音频忙时绘制提示，提示结束先失效并重绘完整当前画面一次，后续继续局部刷新。生产渲染/提示函数两尺寸7060帧与400提示帧回归通过，待机黑条写入为0，两次结束恢复逐像素一致；锁定构建通过。用户本次“烧录允许”后，已重新枚举COM5/核对MAC、Flash16MB、app0和OTA1，独立验证旧v0.11.4；仅写app0 0x10000，写入Hash及独立verify_flash通过。用户正常重启确认“版本正确，黑条消失”；USB运行握手证实v0.11.5-dev，热点配置保留，Wi-Fi认证成功。

用户已更正本机热点密码，Watch获得IP 10.33.72.225；先前电脑在NETCORE-New/192.168.2.4；本次写入结束后已核对电脑Wi-Fi回到10.33.72.210/24，与Watch同热点子网，正式PC v0.20.1-dev 连续20秒5次状态采样均wifi_connected/设备authenticated为true、route=wifi、无错误，设备boot/session一致。已确认同热点基础认证/心跳互联；业务指令、BLE完整恢复、PTT/听感及T12/T13长稳仍未完成。以下现场段落为历史快照，以本段为当前状态。

## 2026-10-04 最新：USB首次配网，Wi-Fi互联待现场完成

PC源码 v0.20.1-dev；Watch v0.11.3-dev已按用户“允许烧录”仅写app0并独立校验通过，正常重启/实屏与USB配网待验。新增本机USB首次配网，默认Wi-Fi优先，热点密码只由用户在本机掩码框输入；电脑已连接vivo X200 Pro的2.4GHz热点。普通表情页底部空闲“Avatar audio ready”已隐藏，录音工作提示保留。Python158、控制台既有58和新增USB用例、桌面32、生产C++解析/分发和GATT范围回归通过，锁定构建通过。正式8766/8765当前未监听，须正常打开Gork加载新源码。Windows BLE完整恢复仍待修复；Wi-Fi互联/PTT/听感及T12/T13未验收。详见04-output/v0.20.1/USB首次配网与互联记录-【codex】.md。


## v0.11.2-dev GATT upgrade compatibility (2026-10-04)

Append the new network service after the existing expression/audio/sound services so bonded clients retain their old service handle ranges. Production registration/attach regression and locked build pass. The user authorized this candidate; only app0 was written and independently verified. User confirmed restart and v0.11.2 on screen. Old audio discovery recovered; full GATT discovery and provisioning remain pending. Existing bond/NVS and v0.11.1 render fix are preserved. See root `04-output/v0.11.2/`.

## v0.11.1-dev render transition fix (2026-10-04, candidate)

User confirmed v0.11.0-dev on the physical screen, then reported residual eye shapes. The v0.11.1-dev candidate clears the outgoing legacy renderer once before entering MotionDraw; steady animation keeps partial updates. Production refresh regression passes 7060 frames / 208 boundaries at 466 and 468 pixels, plus existing native geometry/pose checks. The user then authorized app0-only flashing; v0.11.1-dev was written and independently verified. The user confirmed normal restart, correct v0.11.1-dev, and no currently visible residual eyes. Full scene coverage, device FPS and soak acceptance remain pending. See root `04-output/v0.11.1/`.

## v0.20.0 PC / v0.11.0 Watch candidate (2026-10-04)

TLS-PSK network and delegated Watch PTT share the existing authenticated BLE/audio/Controller pipeline. The current app0 image was written and independently verified; device boot, BLE, provisioning, hearing and performance are still unverified. PC runtime is v0.20.0-dev. See root `04-output/v0.20.0/` for the protocol decision, evidence matrix and recovery procedure. Historical version notes below retain their original scope.


## v0.10.0-dev motion candidate (source/build only, 2026-10-03)

Four configurable scenes (idle/loading/writing/question) and four distinct pen shapes consume parameters generated from the same validated desktop v2 JSON. `tools/convert_gork_motion.py` extracts the pinned sphere/camera geometry and the current 466×466 screen body inset, then emits `src/motion_config.h` and its Watch JSON. All eye, pose, timing and prop fields remain present; no web JS runtime is used on the MCU.

The encrypted command parser accepts `once loading`, `loop loading` (also writing/question), `motion complete`, `motion cancel`, `motion idle` and `legacy idle`, within the existing 20-byte limit. Legacy expressions and audio remain available. Configured idle is the candidate default; the desktop API currently blocks new Watch scenes because the physical device still runs v0.9.1-dev. This build does not implement live JSON transfer to Watch.

PlatformIO compilation passes: static RAM 64,440/327,680 bytes (19.7%), Flash 1,727,829/6,553,600 bytes (26.4%). Actual host-compiled C++ passes 640 raster frames and JS pose comparison; host timing is not device FPS. No device was flashed or rebound. Screen, frame time, BLE coexistence/reconnect and fallback need separate hardware acceptance. See root `00-docs/00-PRD/32-v0.19.0-动效编辑器接入与Watch映射-【codex】.md` and `04-output/v0.19.0/`.

[English](README.md) | [简体中文](README.zh-CN.md)

[![Build firmware](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml/badge.svg)](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

Meet **KK** — a tiny expressive face living inside the M5Stack StopWatch.

KK is a procedural avatar built for the M5Stack StopWatch's circular AMOLED display. Its eyes, eyelids, brows, keyframes and transitions are drawn in real time with C++, without image-frame animation. The pure-black visual system is optimized for the 466 × 466 circular screen, partial updates and direct interaction.

> Community project. Not affiliated with or endorsed by M5Stack.

## v0.9.0-dev Opus BLE candidate (source/build only)

The audio endpoint accepts length-prefixed Opus packets after an opt-in HELLO capability exchange, decodes to mono PCM in PSRAM, then uses the same avatar-page speaker path. Legacy clients still receive the four-byte PCM capabilities. The encrypted GATT, bounded packet ACKs, cancellation and 10-second playback limit remain. The v0.9.0 image was written only to app0 and independently verified. On one 5.592 s sample, Opus transfer took 3.66 s versus 32.22 s for PCM on the same device. The user confirmed a complete, audible Opus sentence on the avatar page; detailed timbre comparison is still open.

## v0.8.8-dev avatar-page audio

The BLE audio receiver also stays active on the normal avatar page, without drawing the diagnostic audio UI over the avatar. Playback may coexist with avatar animation and text bubbles. Recording remains restricted to Settings → Audio test. Built-in sound playback and dynamic BLE audio are mutually excluded; opening Settings, losing authorization, or cancelling audio stops the active transfer. On 2026-09-24, the v0.8.8 image was written only to app0 and independently verified. A complete short sentence played twice on the avatar page; the user confirmed clear, complete audible speech on the second run. Transfer took about 17.5 seconds for 89.6 KB of PCM; remaining hardware checks are recorded under `04-output/v0.12.9/`.

## v0.8.7-dev BLE bonded-peer reconnect candidate (source/build only)

On an existing bond, a Windows central can reconnect with a resolvable private
address that differs from the stored identity. The BLE server now waits for
encryption/authentication before checking the bound identity. GATT writes still
require authorization; a new bond still requires the local Pair window. The
v0.8.7 image was subsequently flashed and its GATT reconnect path checked on
hardware; v0.8.8 remains a source/build candidate.

## v0.8.6-dev built-in codec loudness boost (flashed, loudness accepted)

The v0.8.5 PCM peak is already 30,000/32,767, so another direct 3x PCM
multiply would clip. For the six short built-in sounds only, v0.8.6 changes
ES8311 REG32 from `0xBF` (0 dB) to `0xD2` (+9.5 dB, nominal 2.99x voltage
gain). Streamed BLE PCM and recorded-audio playback remain at 0 dB.
The Settings landing page also displays `v0.8.6-dev` as the firmware version.

All 75 Python, 5 browser and 5 Electron tests pass. PlatformIO builds at RAM
63,928 bytes (19.5%) and Flash 1,625,497 bytes (24.8%). The 1,625,856-byte
application was flashed app-only at 0x10000 and an independent verify_flash
passed. Because the source tones are already near full scale, high-volume
output may clip or saturate; physical testing must begin at 20–30% and
increase gradually.

The user subsequently confirmed on the physical device that the sound now has
a normal usable loudness. This closes the maximum-loudness issue, but does not
yet cover per-sound distortion/noise, thermal or long-duration testing.

## v0.8.5-dev 3x built-in sound amplitude (flashed; still too quiet)

The six deterministic built-in PCM16 sounds previously peaked at 10,000,
leaving 3.2767x headroom below the signed 16-bit limit. Their generator now
uses a 30,000 peak: exactly 3x digital amplitude, approximately +9.54 dB,
without PCM clipping. The ES8311 remains at 0 dB, so dynamic speech, BLE PCM
and recorded-audio playback are not globally boosted.

All 73 Python, 5 browser and 5 Electron tests pass. PlatformIO builds at RAM
63,928 bytes (19.5%) and Flash 1,625,089 bytes (24.8%). The 1,625,456-byte
application was flashed app-only at 0x10000 and an independent verify_flash
passed. Actual loudness, distortion, noise and thermal behavior require a
staged physical listening test beginning at 30–40% volume.

## v0.8.4-dev official ES8311 setup fix (flashed, audible output confirmed)

The source embeds six deterministic 16 kHz PCM16 mono CC0 tones and adds a
separate encrypted sound-control GATT service. Short 9-byte commands provide
capabilities, catalog version, play, stop, 0–100 volume and status with request
IDs, directed notifications and an eight-entry terminal dedupe cache.
`Settings → Sound` exposes volume, mute, explicit preview and stop; NVS writes
are delayed. Static sounds, microphone and dynamic PCM remain half-duplex and
mutually exclusive. B stops active sound before expression browsing.

The v0.8.3 local test still displayed `playing` without audible output after
both M5IOE1 G10 and ESP32 GPIO14 were enabled. The official factory project
uses esp_codec_dev 1.5.4 to configure 44.1 kHz, 16-bit Philips I2S, the DAC
reference, mute state and output volume. The pinned M5Unified callback writes
only a subset of those ES8311 registers. v0.8.4 applies the complete official
sequence, verifies the critical registers, then enables both PA gates.

PlatformIO builds successfully at RAM 63,928 bytes (19.5%) and Flash 1,625,873
bytes (24.8%). The v0.8.4 application was flashed app-only at 0x10000 and an
independent verify_flash passed. The local Sound/Test is now audibly playing,
confirming that the incomplete codec setup caused the previous silent output.
The reported 100% volume is still low, so gain and full sound-control acceptance
remain pending.

## v0.7.2-P0 BLE audio probe (flashed, runtime acceptance pending)

Update 2026-09-21: authorized app-only flash at 0x10000 and independent
verify_flash succeeded; hardware reset sent. Capture/playback retest pending.
The following not-flashed statement records the earlier development snapshot.

Fixes stale-loop-clock capture timeout underflow; adds distinct driver/queue/
timeout errors E9–E13 and preserves failures across cleanup/disconnect.
The device still runs v0.7.0-P0 and has reported code 5 on capture.
Actual microphone/speaker acceptance remains pending after an authorized update.

An opt-in `Settings → Audio test` page exercises the official StopWatch
microphone/speaker using half-duplex PCM16. The PC bench arms one capture;
hold A to record, release to finish, B to stop. Audio never starts from the
avatar page. The separate encrypted audio GATT service has bounded PSRAM,
connection/session/transfer isolation, physical cancellation, and a heartbeat
lease. `../../tools/stopwatch_audio.py` supports tone, WAV playback, explicit
WAV recording, and BLE round-trip echo. This is a credit-one transport probe,
not a real-time stream. The PC voice workbench has evolved into the v0.8.0-dev
Gork console while retaining this diagnostic protocol. Hardware sound quality, throughput, security,
and product regression acceptance are pending. The v0.7.0-P0 application was
flashed at 0x10000 on 2026-09-21 with independent readback verification; normal
boot and on-device audio still require observation.

## Highlights

- 12 procedural expressions: `idle`, `listening`, `thinking`, `happy`, `excited`, `curious`, `confused`, `angry`, `surprised`, `sad`, `sleepy` and `dizzy`;
- 60 fps target rendering with dynamic dirty rectangles to reduce AMOLED transfer work;
- tap, double tap, long press, continuous touch tracking, and horizontal/vertical swipes;
- accelerometer and gyroscope fusion for tilt tracking, with the eyes leading and the head following;
- four strong alternating horizontal shakes trigger a looping spiral-eyed dizzy reaction;
- A/B buttons browse expressions, with vibration feedback;
- hold A+B to enter `Settings`, then open `Bluetooth` or `Hardware Check`;
- semantic serial commands provide a stable input boundary for future voice recognition or external control.

## v0.2.0 Grok renderer

The v0.2.0 branch keeps KK's input, animation timeline, 60 fps scheduler and
dirty-rectangle flow, while replacing the face drawing layer with a fixed-point
Grok geometry renderer. The source study is retained under
`assets/source-grok-study/`; the firmware consumes generated C++ constants, not
JavaScript at runtime.

- one white blob body and black eye cutouts, transformed from a 1000 × 1000 design space;
- 12 expression states mapped to 8 implemented eye groups and 25 retained source groups;
- fixed-point generated geometry with deterministic ear-clipped triangles;
- no image sequence frames or per-frame heap allocation;
- five-second serial metrics include FPS, render time, geometry point count, maximum dirty area and full-screen fallback status.

## v0.2.1 Grok bot renderer (built, device acceptance pending)

The v0.2.1 branch uses the user's exported Bible Strong Avatar Lab Studio project as the data snapshot. `tools/generate_grok_bot_catalog.py` converts its 27 Grok bot expression presets and 23 animations into deterministic C++ tables. The firmware draws a black circular body with individually sized, positioned and rotated white eyes; the website's React/SVG runtime is not embedded. The StopWatch input, power, vibration, IMU and local-refresh implementation remains from the verified KK hardware base.

The 23 animations can be browsed with A/B or addressed by serial name. The hardware-facing `sleepy`/`dizzy` aliases map to the source `drowsy`/`playful` sequences. Source data: `assets/source-grok-bot/`; contact sheet: project-level `04-output/v0.2.1/previews/`.

In v0.2.2, only `idle` persists by default. Every other sequence plays once and returns to `idle`. Serial `loop <name>` and `pingpong <name>` remain explicit continuous-play overrides; `once <name>` returns to `idle` after completion. The app image has been flashed and verified, but runtime return-to-idle acceptance is pending a normal boot.

In v0.2.3, hold A+B for one second to open `Settings` (the former hardware-check screen). Tap `-` or `+` on the Brightness row to change display brightness in steps of 15 between 30 and 255. The value is stored in ESP32 NVS and restored after restart. The hardware diagnostics remain on the same screen. This version is built but not yet flashed or hardware-accepted.

In v0.2.4, the `Settings` home page also shows an estimated battery percentage/voltage and a persistent `Debug mode` switch. The hardware diagnostics now live on a `Hardware Check` subpage. Debug mode adds a tiny white animation name at the bottom of the avatar screen; when off, no label is drawn. This combined brightness/battery/debug image was flashed and read back, but has not yet been hardware-accepted.

In v0.2.5, the debug animation name moves to the top of the black avatar body. This app-only update has been flashed and read back; on-device visual acceptance is pending.

## v0.3.0 BLE expression control (paired, core G4 path verified)

v0.3.0 adds an optional `GorkBot-SW` BLE GATT peripheral. BLE is OFF by default;
the user enables it in `Settings → Bluetooth` and opens a local 120-second `Pair`
window. Only the controller that completes encrypted binding may write commands
afterwards. The command characteristic accepts encrypted write-with-response only;
the status characteristic provides encrypted reads and notifications. USB serial,
buttons, touch and IMU remain available.

BLE callbacks perform only bounded ASCII validation and queueing. Expression
semantics, menu-busy rejection, vibration and receipts are handled by the main
loop. The Windows client is `tools/ble-expression-console.py`, launched by
`tools/start-ble-expression-console.cmd` in an isolated Bleak environment. The
Arduino BLE security probe, formal firmware build and mock GATT client tests pass;
The v0.3.0 app image has been flashed to the authorized target at 0x10000 and
passed esptool readback verification. After the local Pair action,
`BleakClient(pair=True)` discovered the service, subscribed to status
notifications, received receipts for all 23 standard expressions, and
reconnected once. Unbound-controller rejection, ten-cycle reconnect,
latency/FPS and long-run stability remain G4 follow-up checks.

## v0.4.0 happy-work derivative (included in v0.5.0 upload)

`happy-work` is a firmware-local 24th callable expression. It references the
unchanged four-keyframe `happy` eye sequence and adds a procedural monochrome
paper, pen, gloved hand, and progressing ink stroke in the lower safe area of
the circular screen. The 23 source sequences and generated catalog remain
untouched. Default playback returns to `idle`; explicit `loop happy-work` and
`pingpong happy-work` continue. USB serial and BLE consoles accept the new
hyphenated name (19 bytes in the longest command). Local tests and PlatformIO
build pass. The v0.5.0 app upload includes this expression; visual quality,
residue-free transitions, and FPS still require physical acceptance.

## v0.5.0 BLE chat bubble (uploaded, readback verified)

The Windows BLE console accepts `:say <text>` and `:clear`. `:say` transfers up
to 24 printable BMP Unicode characters (72 UTF-8 bytes maximum) in sequenced,
acknowledged GATT packets of no more than 20 bytes each. The device validates
and commits the complete text in its main loop. A two-line bubble is rendered
above the avatar with the bundled 16 px Chinese font and clears automatically
after about 10 seconds. This retains the original BLE service, bonding policy,
expression control, and v0.4.0 `happy-work`. Emoji are not supported. The new
firmware builds and client tests pass. The app-only upload and independent
flash readback verification pass; Chinese glyph appearance, clipping, residue,
and frame rate still need physical QA.

The local build and data tests pass. v0.2.1 has been uploaded as an app-only update and verified by flash readback. A user photo shows the black body and white eyes; 23 serial sequence entries respond and the optimized idle renderer reaches 60 FPS. Full animation, input and long-run hardware acceptance remains pending.

## Interaction map

| Input | Result |
| --- | --- |
| Tap | `happy` |
| Double tap | `surprised` |
| Hold and move | Eyes and head continuously follow the touch point |
| Long press | `angry` |
| Swipe left / right | Preview and switch to the adjacent expression |
| Swipe up / down | `surprised` / `sleepy` |
| Slowly tilt the device | Gaze continuously follows the tilt direction |
| Four strong alternating horizontal shakes | Loop `dizzy`, then recover after the device settles |
| A / B | Previous / next expression |
| Hold A+B | Enter / exit `Settings`, then open `Bluetooth` or `Hardware Check` |

`idle`, `listening` and `thinking` are persistent base states. Other reactions return to the previously active base state when their animation finishes instead of always returning to idle.

## Hardware

- [M5Stack StopWatch Dev Kit (C152)](https://docs.m5stack.com/en/core/StopWatch)
- ESP32-S3R8, 16 MB Flash, 8 MB PSRAM
- 1.75-inch 466 × 466 circular AMOLED touch display
- BMI270 six-axis IMU
- CST820B touch controller
- Two programmable buttons and an internal vibration motor

See [Hardware baseline](docs/HARDWARE_BASELINE.md) for interfaces, addresses and the current verification boundary.

## Build

Requirements:

- [PlatformIO Core](https://platformio.org/) 6.1.18
- USB-C data cable
- M5Stack StopWatch

The library commits used by the verified build are pinned in [`platformio.ini`](platformio.ini).

```sh
pio run -e m5stack-stopwatch
```

From the project root, the offline desktop preview can be regenerated with:

```sh
python tools/render_grok_previews.py
```

The resulting 12 state SVGs, three keyframe comparisons and `index.html` are
written to `04-output/v0.2.0/previews/`.

## Upload and monitor

The v0.2.0 image was written to the authorized target on 2026-09-16 after a
read-only port/MAC/chip/Flash and recovery-image preflight. PlatformIO used
`COM5` for this run and wrote the existing `default_16MB.csv` layout at
`0x0000`, `0x8000`, `0xe000` and `0x10000`; all four regions passed post-write
`verify_flash`. `COM5` remains a connection snapshot, not a permanent setting.

The write did not use full-chip erase, eFuse, secure boot or flash encryption.
True display, touch, button, vibration, IMU, serial-performance and long-run
hardware acceptance remains pending; code/build success is not a substitute for
those observations. See the project-level G3/G4 evidence for the exact command
and readback record.

```sh
pio device monitor --baud 115200
```

The monitor accepts expression names such as `happy`, `thinking`, `celebrate` or `playful` (`dizzy` remains an alias). Playback testing also supports:

```text
once <expression>
loop <expression>
pingpong <expression>
```

## Repository map

| Path | Purpose |
| --- | --- |
| `src/avatar_engine.*` | Expression catalogue, timelines, easing, drawing and interaction physics |
| `src/main.cpp` | Device setup, touch/IMU/buttons, vibration, diagnostics and serial commands |
| `docs/HARDWARE_BASELINE.md` | Hardware capabilities and verification boundary |
| `docs/ENGINEERING_NOTES.md` | Rendering experiments, measurements and implementation decisions |
| `docs/ROADMAP.md` | Planned work and intentionally unsupported features |

## Known limitations

- The microphone and offline speech recognition are not connected yet. Serial commands only simulate semantic voice events.
- Audio playback, RTC, deep sleep, wake-up strategy and external expansion ports are not integrated.
- Battery life has not been optimized for long-term always-on use.
- Subjective motion and gesture tuning may vary with how the device is held.
- The v0.2.1 Grok bot catalog has passed deterministic conversion, desktop preview and local compilation checks; touch, IMU, buttons, vibration, display quality and performance still require real-device G4 verification.

## Inspiration and provenance

This project uses the user's Grok bot export from [Bible Strong Avatar Lab](https://github.com/smontlouis/bible-strong-avatar-lab) as v0.2.1 visual and animation data. The embedded C++ runtime is separate from the upstream web application and does not bundle its React/TypeScript engine; the exported avatar JSON **is** bundled under `assets/source-grok-bot/`.

The concise relationship is: **Grok bot data retained and attributed; renderer rebuilt for StopWatch hardware.**

Hardware initialization, pin mapping and IMU screen-axis handling reference M5Stack's official [StopWatch User Demo](https://github.com/m5stack/M5StopWatch-UserDemo). See [Third-party notices](THIRD_PARTY_NOTICES.md) for details.

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and run `pio run` before submitting a change. Hardware-dependent claims should include real-device evidence when possible.

## License

This project is licensed under the [GNU Affero General Public License v3.0 or later](LICENSE).
