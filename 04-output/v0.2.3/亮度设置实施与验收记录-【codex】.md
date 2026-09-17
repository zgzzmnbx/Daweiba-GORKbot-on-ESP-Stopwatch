# v0.2.3 设置页亮度调节实施与验收记录

> 日期：2026-09-17  
> 状态：源码、测试和固件构建通过；尚未写入设备，真机触控及持久化待验收。

## 交互约定

- 现有固件没有独立设置菜单，原 A+B 长按入口为 `Hardware Check` 诊断页。v0.2.3 将该页标题改为 `Settings`，保留 Display、IMU、Touch、Vibration、Last event 信息和 A/B 诊断操作。
- 长按 A+B 约 1 秒进入/退出设置页。点击亮度行的 `−` / `+` 各调整 15，允许范围 30–255，默认 150；最低亮度保护避免调成全黑后无法操作。
- 调整立即调用屏幕亮度接口，并写入 ESP32 NVS 的 `gorkbot/brightness`；下次启动读取。NVS 不可用时仍可当次调整，但不会持久化。
- 表情页面、原有触摸手势、按键切换和硬件诊断逻辑不改。

## 本地验证

- `python tools/generate_grok_bot_catalog.py --check`：27 presets、23 sequences，PASS。
- `python -m unittest discover -s tools -p 'test_*.py' -q`：12 项通过。
- PlatformIO Core 6.1.18 / `m5stack-stopwatch`：构建 SUCCESS；RAM 36272 字节，程序 893577 字节；已链接 `Preferences 2.0.0`。
- 应用镜像 `firmware/firmware-v0.2.3-grok-bot-brightness.bin`：893936 字节，SHA-256 `8611E5A3392DC0323161E34772332B1CFEBA62A2B9D47B0AD4F7B38DFE1DE8E0`。ELF/MAP 校验见 `SHA256SUMS.txt`。

## 待完成真机验收

1. 写入前重新核对设备端口、MAC、现有应用与恢复备份；仅写应用区。
2. 启动后长按 A+B，确认设置页可见且硬件检查原有信息/操作未丢失。
3. 点击 `−`/`+`，确认亮度即时变暗/变亮、到边界后不越界；最低档仍可看见屏幕。
4. 调整亮度后重启，确认设置被恢复；再次进入设置页显示相同百分比。
5. 返回表情页，确认渲染、A/B 浏览、触摸手势和 v0.2.2 自动回待机行为未回退。

构建成功不等于真机通过；截至此记录，设备上仍是 v0.2.2 应用。
