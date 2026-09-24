# v0.12.9 / 固件候选 v0.8.8：小人页朗读与 BLE 传输窗口

日期：2026-09-24。电脑端源码与正式运行实例最新健康检查均为 v0.12.9-dev；Watch app0 已按当次授权写入 v0.8.8-dev 并独立校验。旧吞吐样本采自此前运行的版本。

## 已有真机证据与诊断

- 用户在 Watch 的 Settings → Audio test 页面听到由输入文字合成的语音。说明 TTS、BLE 音频和扬声器链路至少有一次完整成功；不证明普通小人页已经支持音频。
- 正式实例最近成功任务的状态为 `played`、57,600/57,600 字节、总历时 32.6426 秒、平均 1,764.6 B/s。该时间含最后的设备播放等待，不能当作纯链路速率。
- 旧客户端对每个最多约 232 字节 PCM 数据包都等待一个设备 ACK；57,600 字节至少约 249 包。这个串行往返是本项目明确可见的限制。BLE 链路环境、实际 MTU 和连接间隔可能同时影响速率，尚无本机链路层测量。

## 改动

- 电脑端音频 DATA 采用最多 3 包在途的有限窗口，对应固件 4 包接收队列。ACK 必须属于当前加密会话、当前 transfer/epoch，并指向已发包的累计结束偏移；进度只在确认后前进。错位回执不能推进进度；缺失回执、取消、断开或设备错误不继续 COMMIT/PLAY。控制命令和心跳仍由同一把锁串行，CANCEL 保持独立抢占路径。
- 设备候选在启动后及退出设置页时让音频接收器于小人页待命；仅播放，录音 ARM 在普通页被拒绝。普通页音频状态不绘制测试界面，保留小人动画和文字气泡。进入设置、断连、取消时停止音频。动态语音接收/播放时拒绝内置短音；内置短音正在播放时拒绝动态音频 BEGIN，避免共用扬声器冲突。
- 现有 Audio test 页录放路径保留。候选只改应用源码和电脑端，不改分区、绑定信息、NVS 或永久安全设置。

## 已完成验证

- `tools/platformio_safe.py run -d 03-Src/stopwatch-grok-avatar -e m5stack-stopwatch`：构建成功，RAM 63,936/327,680（19.5%），Flash 1,626,325/6,553,600（24.8%）。版本化应用镜像：`04-output/v0.8.8/firmware/StopWatch-Gork-v0.8.8-dev-app.bin`，1,626,688 字节。
- 控制台 Node 40 项、Electron 16 项、Python 控制台与音频协议 68 项通过。新增延迟回执模拟验证 3 包窗口、完整字节一致；错位 ACK、超时、取消和断连回归通过。
- 写前重新核对 USB COM5、芯片 MAC、16 MB Flash 与当次读出的 app0 分区表；仅向 `0x10000` 写入 1,626,688 字节，工具写入校验及独立 `verify_flash` 均通过。具体记录见 `04-output/v0.8.8/固件构建与待写入-【codex】.md`。
- 写后正常启动，Watch Bluetooth 显示 ON / CONNECTED / SAVED；电脑端重新发现表情及音频 GATT 服务，正式 Gork v0.12.9-dev 恢复连接。普通小人页已接收音频并返回 `played`，证明不再必须停留 Audio test 页。
- 首次 64,000 PCM 字节样本（2 秒）传输约 12.5 秒，含播放约 14.2 秒；`window=3`，`packet_bytes=244`，发送阶段约 5.5 KB/s。**样本是 5.6 秒语音的前 2 秒**，用户听到缺字属样本本身截断，不能作播放缺字结论。
- 随后通过本地 TTS 生成完整短句“你好，测试完成。”，1.869 秒、89,698 PCM 字节；发送约 17.5 秒，含设备播放回执 18.6 秒，`stage=played`，无协议错误。应用户要求再次播放同句，89,574 PCM 字节、发送约 17.5 秒、含播放 18.54 秒，用户确认**完整清楚**。新旧样本长度不同，旧版 57,600 字节/32.64 秒还含播放等待；可确认新链路发送阶段约 5 KB/s，不能据此给出严格 A/B 倍数。

## 剩余真机门禁

1. 完整短句可闻听验已通过；仍须观察播放期间小人动画和文字气泡是否正常。
2. 在普通小人页检查停止可中断、内置短音互斥；在 Audio test 页复验录音与回放，以及原六种短音。真实掉线恢复、长稳和陌生端拒绝继续保留。
3. 当前 16 kHz/24 kHz PCM 音频约 64/96 KB 每 2 秒，BLE 传输仍需十余秒。后续如要显著降低等待，优先设计压缩传输与设备端解码，再以同一句音频做严格 A/B 测量；任何新的设备写入另按当次授权执行。

官方 BLE 性能参考：[Espressif BLE FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/bt/ble.html)、[Espressif BLE performance guidance](https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/advanced-development/ble-application-note/performance.html)。
