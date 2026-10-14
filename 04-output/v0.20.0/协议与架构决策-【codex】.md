# 协议与架构决策 v0.20.0 / v0.11.0

PC仅主动连接Watch热点私网IPv4 TCP7443；8766/8765继续127.0.0.1。自动候选来自可信BLE状态、固定身份的mDNS、合法缓存或用户手动地址，并核对实际启用Wi-Fi网卡子网；不扫描全网或修改路由/防火墙。

认证使用成熟TLS1.2 PSK-AES128-GCM-SHA256，双方独立随机32字节设备密钥与16字符身份。首次经原加密且已绑定BLE通道下发；热点密码不复用为控制密钥。PC使用Python3.14/OpenSSL PSK回调，Watch使用锁定Arduino工具链mbedTLS。相较PRD证书指纹提案，本实现用绑定密钥完成双向身份验证；没有关闭认证或明文回退。新平台须确认PSK运行时能力，不支持时明确失败。本密码套件不提供前向保密；NVS未启用物理Flash加密，不能宣称抵抗设备密钥提取。

参考：[Python SSL PSK API](https://docs.python.org/3.14/library/ssl.html#ssl.SSLContext.set_psk_client_callback)、[Espressif ESP-TLS](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-reference/protocols/esp_tls.html)，2026-10-04核对。宿主测试真实TLS握手及错误密钥拒绝通过；mbedTLS服务编译通过，设备TLS握手尚未实测。

帧头24字节，小端：magic GW(2)、version1(1)、kind(1)、payload_len u16、flags u16=0、boot u32、session u32、request u32、payload CRC32 u32。负载最多4096字节。种类0 HELLO、1表情、2文字、3清字、4声音、5既有音频包、6状态/设置/委托；回复128执行结果、255错误、133音频事件、134按键事件。HELLO采用boot/session0；业务必须匹配当前boot和会话。黄金样本为kind5、boot12345678、session10203040、request1、abc：4757010503000000785634124030201001000000c2412435616263。

每个TLS会话最近32个结果有界保存，单调请求号；缓存淘汰、重复冲突、未取得执行结果均明确拒绝重放。新会话不续接旧任务。音频沿用v1包头12字节和原UUID，增加ProductArm11，能力位2标识PTT。两传输进入同一AudioProbe主循环核心，dataDecision/commitAllowed/cancelMatches/playDecision抽到audio_task_core.h并直接宿主编译测试。重复PLAY不再次启动，取消过的播放不冒充正常PLAYED。

任务固定到选择时的单一路径；备用链路断线不改变当前音频路径。Wi-Fi健康观察10秒、至少3个业务成功回执，回升冷却30秒；仅下一轮可升级/回退。三策略 auto_wifi_first/ble_only/wifi_only，手动断开阻止自动连接。Wi-Fi-only下BLE维护设置仍允许，但不隐藏业务回退。

录音16kHz mono PCM16，320000字节/10秒；至少6400字节/0.2秒。播放输入上限480000；Opus解码上限480000，另有120ms临时解码块与库状态。音频队列4×4096约16KB内部静态内存；TLS主循环消息4入/8出，每帧约4120字节，来自PSRAM且有硬上限；TLS任务栈12288字节，TLS动态缓冲、显示和库状态另计。编译静态RAM118120/327680；应用镜像2227328字节，app0容量6553600。实际同时占用、最小heap、连续块、任务栈峰值和帧时尚需设备测量，静态数字不证明运行稳定。

Watch gorknet独立命名空间采用单CRC有效blob原子更新，不覆盖gorkbot原绑定/亮度/音量。PC设备身份DPAPI保护、CAS修订、有效本机备份，热点密码不长期保存。设置确认先发回，再延迟应用可能中断连接的配置；录放中等待空闲。M5PM1直接返回外部/电池/未知，未知诚实显示并使用eco；未以电池电压猜USB。
