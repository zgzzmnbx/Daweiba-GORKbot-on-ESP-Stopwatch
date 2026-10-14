# v0.11.4-dev Wi-Fi / BLE 共存黑屏修复候选

## 现场证据与原因

v0.11.3完成USB配网后，用户报告黑屏和重启后仍黑。受控复位后只记录过滤的公开启动/错误行：应用启动版本v0.11.3-dev；wifi报 `Should enable WiFi modem sleep when both WiFi and Bluetooth are enabled`；随后abort、RTC_SW_CPU_RST反复重启。见tests/v0113-boot-crash.log。未输出热点密码、密钥或原始配网串口输入。

原性能档在外部供电时调用WiFi.setSleep(false)。ESP-IDF4.4的ESP32-S3共存模式不能完全禁用modem sleep，与[Espressif官方Wi-Fi文档](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-guides/wifi.html)一致。

## 修复

Wi-Fi启动前先设置兼容电源模式；蓝牙控制器启用时无论性能/省电档都保持modem sleep。每次主循环检查当前控制器状态；首次蓝牙启用前先准备Wi-Fi兼容设置，防止Wi-Fi-only启动后新增蓝牙再触发故障。性能档仍使用既有更快重试节奏。不清热点/蓝牙绑定、不改GATT协议、不关闭蓝牙。

## 验证与状态

tools/test_network_power.py编译执行实际生产Wi-Fi启动、电源更新和首次BLE前置函数：性能/省电×蓝牙开/关四种组合通过。既有USB生产解析/分发及GATT三旧服务范围/四注册失败回归通过。

最终PlatformIO构建通过：RAM118504/327680，程序2229577/6553600。固件产物firmware/StopWatch-Gork-v0.11.4-dev-app.bin。当前app0仍v0.11.3，有启动重启故障；本候选等待当次写入授权，未声称修复已上机。修复后需独立verify_flash、运行稳定、热点IP、PC TLS认证、真实表情回执及用户实屏验收。完整BLE恢复/PTT/听感和T12/T13仍未验收。

应用镜像 2229936 字节。

## 用户当次授权后实际写入

用户选择“允许烧录 v0.11.4”后，重新枚举COM5、核对同一MAC/Flash16MB/app0/OTA1、独立验证旧v0.11.3，再仅写app0。镜像2229936字节，Hash verified和独立verify_flash digest matched通过，覆盖扇区0x10000–0x230fff。未写NVS/绑定/分区/bootloader。写后运行探测返回DOWNLOAD，等待用户无烧录键正常重启；尚未确认黑屏恢复或Wi-Fi互联。

PC8766现场v0.20.1-dev，8766/8765仅127.0.0.1监听。新增HTTP配网测试通过：无控制权拒绝，USB分发、旧调用默认BLE及验证错误不回显秘密；USB专项现15项通过（此前全量158通过，新增一项另验）。

## 正常启动与互联进度

用户正常重启后明确确认“屏幕恢复，版本v0.11.4”。USB HELLO/STATUS真实握手成功，返回运行版本v0.11.4-dev和configured=true；控制复位日志出现SPI_FAST_FLASH_BOOT、应用启动及正确版本，8秒采集窗口未复现原wifi共存abort。用户反馈和日志证明本次黑屏恢复，不代替长稳验收。

当前Watch热点地址为空、state为connecting / retry backoff，尚未完成DHCP连接/PC身份认证。PC正式8766返回v0.20.1-dev，HTTP首页200；公开设备状态route=offline、wifi_connected=false。PC保护配置中的SSID与现场WLAN一致为vivo X200 Pro；密码未读取或回显。已请用户检查手机热点已连接设备/准入限制，并仅在本机密码框核对后重试。

底部空闲音频提示已随此镜像隐藏；尚无用户专项视觉反馈。BLE完整服务发现恢复、Wi-Fi表情/音频/PTT与T12/T13未验收。未提交或推送。
