# v0.2.5 调试字样顶部定位：写入与待验收记录

> 日期：2026-09-17  
> 状态：已构建、写入应用区并读回校验；实物文字位置待大尾巴验收。

## 改动

- 调试模式开启时，当前动画英文名仍用白色 1 倍 `Font0`，仅将中心位置从屏幕底部改为圆屏顶部 `y=42`。
- 黑色文字底框维持 `160×14`，居中于屏幕；设置开关、电池显示、亮度和动画逻辑不变。
- 大尾巴要求项目后续不再重复核算文件 SHA-256，已写入项目 `AGENTS.md`；本版本未生成新的 `SHA256SUMS.txt`。设备身份识别和烧录读回验证保留。

## 本地验证

- `python tools/generate_grok_bot_catalog.py --check`：27 presets、23 sequences，PASS。
- `python -m unittest discover -s tools -p 'test_*.py' -q`：12 项现有测试通过。
- PlatformIO `m5stack-stopwatch` 构建 SUCCESS；RAM 36640 字节，程序 906813 字节；应用镜像 907184 字节。
- `git diff --check -- src/avatar_engine.cpp`：未发现差异格式错误；源码已有其他未提交修改，均保持原状。

## 设备写入

- 当次枚举 `COM5` 的 USB VID/PID 为 `303A:1001`；esptool.py v4.9.0 检出 ESP32-S3 rev v0.2、8 MB PSRAM，MAC `28:84:85:44:6C:00`，与项目设备记录一致。
- 仅执行 `write_flash 0x10000 firmware-v0.2.5-grok-bot-debug-top.bin`；工具报告写入 907184 字节，实际覆盖扇区 `0x00010000–0x000edfff`，内建写入校验成功。
- 随后执行 `verify_flash 0x10000`，结果 `verify OK (digest matched)`，并发出硬复位。未整片擦除，未修改 bootloader、分区表、eFuse 或安全配置。
- 未读取屏幕或执行应用运行时测试；烧录成功不等于文字位置和其它交互已经真机验收。

## 大尾巴验收点

1. 打开调试模式后，动画名称出现在黑色头像最上方，文字完整可读，不被圆屏边缘裁切。
2. 切换表情时名称同步变化，关闭调试模式后文字消失。
3. 顺带核对 v0.2.4 的电池读数、亮度和重启持久化；反馈任何异常画面或操作步骤。
