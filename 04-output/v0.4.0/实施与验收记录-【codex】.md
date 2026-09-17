# v0.4.0 `happy-work` 实施与验收记录

> 日期：2026-09-17
> 结论：本机源码、客户端与构建通过；设备仍为 v0.3.0，写入和实物视觉验收未执行。

## 完成范围

- 第 24 个可调用表情 `happy-work` 复用来源 `happy` 的同一组眼睛关键帧和眨眼参数。
- 黑色圆体下半部增加程序化纸张、握笔小手、移动笔尖和生长笔迹；切换离开时擦除上一帧书写层。默认播一轮回 `idle`，显式 `loop` / `pingpong` 可持续。
- USB 与 BLE 共用原 `AvatarEngine::showFromCommand`，客户端支持连字符；最长 `pingpong happy-work` 为 19 字节，低于 20 字节上限。
- 上游生成表未修改；`python tools/generate_grok_bot_catalog.py --check` 输出 `Grok bot catalog verified: 27 presets, 23 sequences`。

## 本机验证

| 检查 | 结果 |
| --- | --- |
| `python tools/test_ble_expression_console.py` | 5/5 PASS，包括 24 个可调用名称及新命令模式 |
| `python tools/test_grok_bot_catalog.py` | 4/4 PASS |
| `python tools/test_grok_geometry.py` | 8/8 PASS |
| `python tools/generate_grok_bot_catalog.py --check` | PASS，27 preset / 23 来源 sequence |
| PlatformIO Core 6.1.18，`m5stack-stopwatch` 正式构建 | SUCCESS；RAM 62,672/327,680（19.1%）；Flash 1,541,201/6,553,600（23.5%） |
| 版本化应用镜像 | `04-output/v0.4.0/firmware/firmware-v0.4.0-happy-work.bin`，1,541,568 字节 |
| `git diff --check`（正式源码仓库） | 无空白错误；Git 仅提示既有工作树 LF/CRLF 转换警告 |

构建使用项目隔离 Python/PlatformIO、既有短路径映射和 `tools/platformio_safe.py`；没有升级工具链或更改正式 `platformio.ini`。没有按项目要求重复计算固件 SHA-256。

## 未验收与下一步

- **设备写入 NOT RUN**：本轮“执行吧”用于实现；未重新识别串口/MAC，未写入或重置设备。只有当次明确烧录指令后才进入写入门禁。
- **真机视觉 NOT RUN**：还需确认开心眼睛与原 `happy` 一致、纸笔与手部可辨、移动顺畅、切到其他表情或自动回 `idle` 后无残影。
- **真机性能 NOT RUN**：需读取新表情 5 秒窗口 FPS、平均/最大渲染耗时并与 v0.3.0 基线比较。
- **命令真机回归 NOT RUN**：需以 USB 与 BLE 分别发送 `happy-work`、`loop happy-work`、`idle`；菜单打开仍应拒绝。
- v0.3.0 BLE 的陌生端拒绝、旧回执误判、自动重连、10 次循环、延迟与 30 分钟稳定性仍是独立未关闭项。

## Git 边界

正式源码仓库在本轮开始前已有未提交 Grok 渲染、配置和资料改动，其中 `avatar_engine.*` 与本功能重叠。为避免把先前用户改动误打包成 v0.4.0 提交，本轮未做 `git add/commit/reset/clean`；保留现有工作树和版本化应用镜像。根项目仍未启用 Git。
