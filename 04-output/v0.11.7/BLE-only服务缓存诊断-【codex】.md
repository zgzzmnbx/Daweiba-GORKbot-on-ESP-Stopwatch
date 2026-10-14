# v0.11.7 BLE only 服务缓存诊断

诊断时间：2026-10-04晚至2026-10-05。Watch v0.11.7-dev，正式PC v0.20.14-dev；源码另有v0.20.17-dev界面改动，本次未重启、修改正式服务或写固件。

用户选择BLE only后无法连接，实屏Bluetooth状态为Control ON、Link Waiting、Binding Saved。扫描能唯一发现目标GorkBot-SW（28:84:85:44:6C:01）；Windows仍显示已配对。

## 当前只读证据

- 正式后台服务发现报WinError -2147024874（设备不识别此命令）。
- 表情服务句柄40、音频服务55可以非缓存发现特征；表情加密状态特征非缓存读取成功（状态Success/0，5字节），无协议错误。这支持现有加密绑定仍可用，不能把问题笼统归因于配对密钥失配。
- Windows缓存枚举包含GATT、GAP、表情、音频以及两条同UUID的短音服务（句柄70和85）；两条短音服务特征查询均失败，新增网络服务d001缺失。非缓存完整枚举报WinError -2147418113；按UUID查询短音/网络亦失败。
- 生产代码已使用use_cached_services=False。本次直接WinRT非缓存查询仍复现，不能仅靠换一个缓存参数宣称修复。

诊断脚本与原始结果：Codex-Temp/ble-only-diagnostic/probe.py、first-probe.json、probe.json、read-status.py。脚本不配对、不取消配对、不写GATT；诊断会话及时释放。未发送云请求或声音，未清绑定或热点。

## 恢复方案

微软BluetoothCacheMode文档明确，远端Service Changed或设备解除配对可使系统GATT缓存失效。当前现象高度指向旧GATT缓存残留；重配后的实际服务发现结果用于验证这一判断。

1. 获得用户当前授权，仅重建这只Watch与本电脑的蓝牙配对。用户退出Gork托盘，避免正式后台自动重连与重配竞争。
2. Watch保持BLE only、Control ON；用户在Bluetooth清除旧蓝牙绑定，打开120秒Pair窗口。热点名称、密码和其他设置保留。
3. 运行现有定向恢复工具，显式地址28:84:85:44:6C:01，必须唯一匹配名称和地址，使用--apply执行Windows取消旧配对再程序内配对。不影响其他蓝牙设备。
4. 核对四个服务、特征与通知；用户正常打开Gork、回小人页面后核对基本指令回执。声音的实际听感仍由用户确认，不以连接状态代替。

预定命令：

```powershell
& 'Codex-Temp/.venv-companion/Scripts/python.exe' tools/repair_stopwatch_ble_pairing.py --address 28:84:85:44:6C:01 --apply
```

工具回归tools/test_repair_stopwatch_ble_pairing.py：2 passed，覆盖地址匹配、错误名称、歧义目标拒绝。

## 2026-10-05 已执行定向重配

用户回复“打开”，继而明确“已退出，Pair已打开”；本次按前述恢复方案授权执行。实际执行前确认8766无监听，避免与正式后台自动重连竞争。定向恢复工具退出码0，Windows取消目标旧配对并程序内重配成功，未改其他蓝牙设备、热点配置或固件。

恢复后的Cached和Uncached完整枚举均Success：GATT(1)、GAP(20)、表情(40)、音频(55)、短音(70)、网络(85)，四个业务服务的特征发现全部成功；短音服务仅一条，网络d001重新可见。由同设备、同固件重配前后的结果，可确认旧Windows服务缓存是本次完整服务发现故障的原因。

BLE表情通知订阅成功，短音CAPABILITIES及GET_STATUS均收到STATUS回执。音频HELLO在这次诊断中超时，未开麦克风或播放；不能据此标完整音频恢复。已核对main.cpp的setMenuOpen：进入设置调用audioProbe.leave，回小人页调用audioProbe.enter(false)。已请求用户回小人页面并正常打开Gork，继续核对正式连接和音频。

证据：Codex-Temp/ble-only-diagnostic/repair.log、after-repair-services.json、after-repair-services.log、verify-protocols.log。前置first-probe.json保留；probe.json为最新查询结果。正式程序退出前新运行版本已读到v0.20.17-dev，本次没有由助手重启正式程序。

## 正式Gork重开后的基本连接

用户确认“已打开”后，正式8766返回v0.20.17-dev，connected/enabled/ble_connected均true、route=ble、wifi_connected=false，收到真实表情命令回执OK:IDLE，operation_error/ble_error/audio_error均空。蓝牙连接及基本表情命令已恢复，服务缓存故障已关闭。证据：Codex-Temp/ble-only-diagnostic/formal-after-reopen.json。

附加音频客户端无法扫描已连接设备的广播，改用已知绑定地址后虽连接成功，但未取得音频特征；前后正式Gork均保持连接且OK:IDLE，不把该并行诊断结果当作正式音频故障或音频通过。无开麦、录音、播放或云请求。证据：live-audio-verification.json、verify-live-audio.log。

正式后台当前Watch按键对话为disabled、无错误。已请求用户在正常Gork设置中启用并做一轮短按录音、再按发送，确认BLE路径的REC与可闻回答；该基本业务确认尚待回复，不属于延期的性能/长稳测试。本次不重复要求Wi-Fi路径已确认的v0.11.7录音提示/双端书写/听感验收。

## 用户补充及后续回执修复

用户已开启按键对话，确认“短按黄色G2/A能看到红色REC了”“直接Watch朗读是可以的”。正式状态有两轮真实录音回传、识别/回答/合成耗时；回答播放前仍出现BLE中断。源码定位到中文自定义表情名称作为BLE回执被PC的ASCII解析拒绝，造成超时主动断开。v0.11.8候选已修复协议名/显示名分离并构建；未烧录，需本次授权。见04-output/v0.11.8/自定义表情蓝牙回执修复验收-【codex】.md。旧服务缓存故障已恢复，不再要求重新配对；新问题不归因于热点或麦克风。

文档依据：[Microsoft BluetoothCacheMode](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.bluetoothcachemode)。保留用户延期的性能/长稳范围，不执行批量稳定性测试。
