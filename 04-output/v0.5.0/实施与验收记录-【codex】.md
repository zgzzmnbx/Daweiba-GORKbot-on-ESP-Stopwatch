# v0.5.0 BLE 聊天气泡实施与验收记录

> 日期：2026-09-17
> 结论：源码、Windows 客户端和固件构建完成；收到大尾巴当次“执行烧录”指令后，v0.5.0 仅写入设备应用区，写入校验与独立读回校验通过。运行效果待验收。

## 本次完成

- BLE 控制台新增 `:say 文字` 与 `:clear`。最多 24 个可打印 BMP 字符且 UTF-8 ≤72 字节；按 17 字节数据块分包，每次 GATT 写入仍 ≤20 字节。
- 加密授权、固定队列和主循环处理链路保留；设备按事务 ID、分包顺序、总长度和 UTF-8 有效性接收。只有 Commit 成功才替换气泡。
- Grok bot 画面上方新增深灰/白线两行气泡，使用既有 M5GFX 中文 16 px 字库；约 10 秒自动消失，或由 `:clear` 立即清除。书写动画与表情时间轴不变。
- Windows 客户端的文字发送仅接受对应通知回执；过期表情回执不会被当成文字成功。原表情命令的旧回执误判与自动重连缺陷未借此宣称修复。

## 本机验证

| 检查 | 结果 |
| --- | --- |
| `python tools/test_ble_expression_console.py` | 9/9 PASS；含 72 字节中文、多包组装、清除、旧回执忽略和菜单拒绝 |
| `python tools/test_grok_bot_catalog.py` | 4/4 PASS |
| `python tools/test_grok_geometry.py` | 8/8 PASS |
| `python tools/generate_grok_bot_catalog.py --check` | PASS；来源仍为 27 preset / 23 sequence |
| PlatformIO Core 6.1.18 正式构建 | SUCCESS；RAM 62,912/327,680（19.2%），Flash 1,544,681/6,553,600（23.6%） |
| 版本化应用镜像 | `04-output/v0.5.0/firmware/firmware-v0.5.0-ble-chat-bubble.bin`，1,545,040 字节 |

没有因常规迭代重复计算文件 SHA-256。构建使用既有隔离 PlatformIO 和短路径映射，不改变正式工具链或分区。

## 本次设备写入（2026-09-17）

- 当次授权：大尾巴明确指令“执行烧录”。
- 写前重新枚举端口：COM5 为 `USB\\VID_303A&PID_1001&MI_00`，COM3/COM4 是蓝牙串口；esptool 识别 ESP32-S3 QFN56 revision v0.2、8 MB PSRAM、MAC `28:84:85:44:6c:00`、16 MB Flash，与既有 StopWatch 恢复记录相符。
- `image_info` 接受 `firmware-v0.5.0-ble-chat-bubble.bin`：1,545,040 字节、5 segments、镜像校验有效。分区表 `default_16MB.csv` 的 app0 起点为 `0x10000`，容量 `0x640000`。
- esptool 4.9.0 仅执行 `write_flash --verify 0x10000`；报告覆盖扇区擦除范围 `0x00010000–0x00189fff`、写入 1,545,040 字节、内建写入校验通过、硬复位。随后单独执行 `verify_flash 0x10000`，结果 `verify OK (digest matched)`，并再次硬复位。
- 未执行整片擦除、分区表/bootloader/NVS 写入、eFuse 修改或电脑蓝牙配对变更；例行迭代未额外生成 SHA-256 校验文件。v0.3.0 正式镜像和首次完整 Flash 恢复点仍保留。

## 尚未执行

- **实屏 NOT RUN**：需拍摄中文/英文单行和两行气泡、替换、自动消失、`:clear`、`happy-work` 切换；核查中文字形和残影。
- **性能 NOT RUN**：气泡开/关分别记录 FPS、平均/最大渲染耗时，不以编译通过推断 55/60 FPS。
- **无线安全/稳定性 NOT RUN**：v0.3.0 BLE 的陌生端拒绝、10 次重连、延迟和 30 分钟稳定性仍待补测。

正式源码仓库本来就有未提交且与渲染文件重叠的 Grok 改动；为避免把用户改动误并入版本提交，本轮不执行 `git add/commit/reset/clean`。
