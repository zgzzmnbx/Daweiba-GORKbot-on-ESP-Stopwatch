# 工具目录

用于项目维护、构建辅助、设备探测和验证脚本。

新增脚本必须使用项目相对路径，不得写死 `COM5` 或本机绝对路径；涉及擦除、烧录、eFuse 或外部发送的动作必须明确标注并设置安全门槛。

双击 `start-expression-console.cmd` 可打开 StopWatch 表情串口控制台。它自动识别 `USB\VID_303A&PID_1001` 的唯一串口，以 115200 波特率发送带换行的已支持命令；也可用 `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\stopwatch-expression-console.ps1 -Port COMx` 显式指定端口。输入 `:list` 查看表情、`:help` 查看示例、`:q` 退出。请先关闭设备上的 Settings 菜单，且不要让 M5Burner 等程序同时占用串口。

双击 `start-ble-expression-console.cmd` 可创建独立的 `.venv-ble` 并安装锁定版本的 Bleak，然后扫描带目标 GATT Service UUID 的 `GorkBot-SW`。首次连接前必须在设备 `Settings → Bluetooth` 中打开 BLE，再点击 `Pair` 开启 120 秒本地配对窗口；设备完成绑定后，后续仅允许该已绑定控制端写入。客户端使用 GATT 写入回执与状态通知，不使用固定 MAC、不创建蓝牙虚拟串口，也不后台扫描。

v0.4.0 源码新增 `happy-work`（开心眼睛 + 下半部写字动画）：串口与 BLE 控制台均支持 `happy-work`、`once happy-work`、`loop happy-work` 和 `pingpong happy-work`。该功能已随 v0.5.0 写入设备，真机显示仍待验收。

v0.5.0 BLE 控制台新增 `:say 你好，今天加油！`：在表情画面上方显示两行聊天气泡，约 10 秒后自动消失；输入 `:clear` 可提前清除。文字最多 24 个可打印 BMP 字符、UTF-8 编码最多 72 字节，支持中文和英文，不支持 emoji。控制台会自动分包并逐包等待回执。v0.5.0 已写入设备并读回校验，实际显示效果待验收；更新脚本后请关闭并重新打开控制台。

手工运行测试：`python tools/test_ble_expression_console.py`。测试仅覆盖客户端协议、服务筛选、回执和 mock GATT，不等价于真机配对、安全负向测试或稳定性验收；这些属于获得明确烧录授权后的 G4 门禁。
