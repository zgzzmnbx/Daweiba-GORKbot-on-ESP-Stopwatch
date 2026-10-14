# v0.20.0 / Watch v0.11.0 开发基线

2026-10-04，Windows，单执行线程；指挥线程 01a102b6-0f8a-75e0-813d-2d502a1e5795。用户“开始干吧，Watch已经到烧录模式”作为本轮软件实施及当前应用候选写入授权。未读取指挥历史中的密码用于配置。

初始 PC 源码/运行 v0.19.4-dev，固件源码 v0.10.0-dev，设备恢复镜像 v0.9.1-dev。根 HEAD c2912b8648dd9daa3c431c87b47c0c8e5a872a68；嵌套固件 HEAD 08c98cb436e9d0d6b2485744d0a94abb3fa21724。大量既有未提交工作保留，未 reset/clean/stash。编辑前定点保存125项公开源码/上下文，追加保护旧BLE/音频工具；路径清单与两仓库状态在 Codex-Temp/wifi-ble-v020/baseline/。私密配置未复制进交付目录。

基线119项Python、58项控制台、32项桌面和固件构建通过。新增功能沿用现有 Controller、BleExpressionClient、AudioClient、M5Unified 音频及主循环绘制，Android、语音模型及原自定义表情参数未重置。

实际确认 ESP32-S3 revision0.2、16MB Flash、8MB PSRAM，当前 USB COM5 与 MAC 当次匹配。读取分区表和OTA元数据确认 app0=0x10000，容量0x640000，OTA有效seq1。旧v0.9.1应用独立 verify_flash 与真实 app0 一致；未读出NVS或整片私人内容。

变更包括安全BLE配网、TLS-PSK、Wi-Fi主动连接/发现/策略、共享音频核心、实体PTT委托、供电/模式设置、双主题UI与自动测试。完整候选同时包含此前未上机的v0.10动效；本版默认 configured idle 和新场景仍须真机视觉/帧率验收。写入后的启动、BLE、配网和听感不能以镜像校验替代。
