# KK — M5Stack StopWatch 表情角色

[English](README.md) | [简体中文](README.zh-CN.md)

[![构建固件](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml/badge.svg)](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml)
[![许可证：AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

认识一下 **KK**：一个住在 M5Stack StopWatch 里的小表情角色。

KK 运行在 M5Stack StopWatch 的圆形 AMOLED 屏幕上。它的眼睛、眼皮、眉线、关键帧和过渡均由 C++ 实时绘制，不使用图片序列帧。产品画面保持纯黑背景，并针对 466 × 466 圆屏、局部刷新和直接交互进行了优化。

> 这是一个社区项目，与 M5Stack 官方没有隶属或背书关系。

## 主要特点

- 12 种程序化表情：`idle`、`listening`、`thinking`、`happy`、`excited`、`curious`、`confused`、`angry`、`surprised`、`sad`、`sleepy`、`dizzy`；
- 以 60 fps 为目标渲染，使用动态脏矩形减少 AMOLED 传输开销；
- 支持单击、双击、长按、连续触摸跟随和上下/左右滑动；
- 加速度计与陀螺仪共同驱动倾斜跟随，眼睛先移动、头部稍后跟随；
- 连续 4 次强力左右往复摇动会触发循环的旋涡眩晕；
- A/B 实体键浏览表情，并由震动马达提供反馈；
- 长按 A+B 进入 `Settings`，再进入 `Bluetooth` 或 `Hardware Check`；
- 串口语义命令为未来语音识别或外部控制提供稳定入口。

## v0.2.0 Grok 渲染器

v0.2.0 保留 KK 的输入、动画时间轴、60 fps 调度和 dirty rectangle 流程，
把脸部绘制层替换为固定点 Grok 几何渲染器。源数据保存在
`assets/source-grok-study/`，固件运行时只使用生成的 C++ 常量，不加载
JavaScript。

- 一个白色 blob 主体和黑色眼形负空间，统一从 `1000 × 1000` 设计空间缩放；
- 12 个表情状态映射到 8 个实现眼组，源数据保留 25 组眼睛；
- 固定点几何、确定性耳切三角化，不使用图片序列帧；
- 绘制路径不在每帧申请堆内存；
- 5 秒串口指标增加几何点数、最大 dirty 面积和全屏退化状态。

## 交互方式

| 操作 | 结果 |
| --- | --- |
| 单击 | `happy` |
| 双击 | `surprised` |
| 按住并移动 | 眼睛和头部持续跟随触点 |
| 长按 | `angry` |
| 左右滑动 | 跟手预览并切换相邻表情 |
| 向上 / 向下滑动 | `surprised` / `sleepy` |
| 缓慢倾斜设备 | 视线持续跟随倾斜方向 |
| 4 次强力左右往复摇动 | 循环 `dizzy`，设备停稳后恢复 |
| A / B | 上一个 / 下一个表情 |
| 长按 A+B | 进入 / 退出 `Settings`；从设置页进入 `Bluetooth` 或 `Hardware Check` |

v0.2.2 起仅 `idle` 默认持续；其余 22 条动画触发后播放一遍，再返回 `idle`。串口显式 `loop <名称>`、`pingpong <名称>` 时持续播放；`once <名称>` 播完返回 `idle`。此修复版已写入应用区并读回校验，正常启动后的行为验收仍待完成；以下 v0.2.0 内容为历史实现说明。

v0.2.3 将长按 A+B 的硬件检查页改为 `Settings`，保留原诊断信息，并加入触屏 `−/+` 亮度调节（30–255、步长 15、默认 150）。亮度写入 ESP32 NVS，重启后恢复。本版本已构建，尚未写入设备或完成真机验收。

v0.2.4 的 `Settings` 首页还显示电池电压估算的百分比/电压，并提供可保存的 `Debug mode` 开关；原硬件诊断移至 `Hardware Check` 子页。开启调试后，头像画面底部用很小的白字显示当前动画英文名。该整合固件已写入并读回校验，尚未完成真机验收。

v0.2.5 将调试模式的动画名移到黑色头像顶部，应用区已写入并读回校验；文字在实物上的观感仍待验收。

## v0.3.0 BLE 表情控制（已配对，G4 核心链路通过）

v0.3.0 增加可选的 `GorkBot-SW` BLE GATT 外设。BLE 默认关闭，用户在本机
`Settings → Bluetooth` 打开后，再点击 `Pair` 开启 120 秒配对窗口；设备只把
完成加密绑定的控制端作为后续写入来源。命令特征只允许加密的带响应写入，状态
特征提供加密读取和通知；USB 串口、按键、触摸和 IMU 仍保留。

BLE 回调只做固定长度 ASCII 校验和有界入队，表情解析、菜单忙拒绝、震动和状态
回执均在主循环中处理。Windows 客户端为 `tools/ble-expression-console.py`，由
`tools/start-ble-expression-console.cmd` 创建独立环境并使用本次锁定的 Bleak 版本。
本版本已通过 Arduino BLE 安全 API 探针构建、正式固件构建和 mock GATT 客户端测试；
v0.3.0 已在授权目标的 `0x10000` 应用区写入，并通过 esptool 读回校验。
设备本地 Pair 后，`BleakClient(pair=True)` 已完成服务发现、状态通知、23/23 条
标准表情命令回执和一次断线重连；陌生端拒绝、10 次重连、延迟/FPS 及长期稳定性
仍待 G4 补测。

## 硬件

- [M5Stack StopWatch Dev Kit（C152）](https://docs.m5stack.com/en/core/StopWatch)
- ESP32-S3R8、16 MB Flash、8 MB PSRAM
- 1.75 英寸 466 × 466 圆形 AMOLED 触摸屏
- BMI270 六轴惯性传感器
- CST820B 触摸控制器
- 两个可编程按键和内置震动马达

接口、地址和当前验证边界请参阅[硬件基础资料](docs/HARDWARE_BASELINE.md)。

## 编译

需要准备：

- [PlatformIO Core](https://platformio.org/) 6.1.18
- USB-C 数据线
- M5Stack StopWatch

已经验证的依赖提交均锁定在 [`platformio.ini`](platformio.ini) 中。

```sh
pio run -e m5stack-stopwatch
```

从项目根目录重新生成桌面预览：

```sh
python tools/render_grok_previews.py
```

预览输出在 `04-output/v0.2.0/previews/`，包含 12 张状态 SVG、3 组关键帧
对照和 `index.html`。

## 烧录与串口监视

v0.2.0 已于 2026-09-16 在明确授权后写入目标设备。写入前已重新核对
端口、MAC、芯片、Flash 和恢复镜像；本次使用 `COM5`，写入既定
`default_16MB.csv` 布局的 `0x0000`、`0x8000`、`0xe000` 和 `0x10000`，
写后四个区域均通过 `verify_flash`。`COM5` 仍只是本次连接快照，不是永久配置。

本次未执行整片擦除、eFuse、安全启动或 Flash 加密。屏幕、触摸、按键、
振动、IMU、串口性能和长时间稳定性仍需真机观察；构建/写入成功不等同于
这些功能验收通过。准确命令和读回记录见项目级 G3/G4 证据。

```sh
pio device monitor --baud 115200
```

串口监视器接受 `happy`、`thinking`、`dizzy` 等表情名称，也支持以下播放测试命令：

```text
once <expression>
loop <expression>
pingpong <expression>
```

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `src/avatar_engine.*` | 表情目录、时间轴、缓动、绘制和交互物理 |
| `src/main.cpp` | 设备初始化、触摸、IMU、按键、震动、诊断和串口命令 |
| `docs/HARDWARE_BASELINE.md` | 硬件能力和验证边界 |
| `docs/ENGINEERING_NOTES.md` | 渲染实验、测量数据和实现决策 |
| `docs/ROADMAP.md` | 计划工作和暂不支持的能力 |

## 当前限制

- 麦克风和离线语音识别尚未接入，串口命令只是模拟语义语音事件。
- 音频播放、RTC、深度睡眠、唤醒策略和外部扩展口尚未集成。
- 尚未针对长期常亮使用优化续航。
- 动作与手势的主观体验可能会随设备握持方式而变化。
- Grok 几何已通过确定性转换、桌面视觉和本机构建检查；显示、触摸、按键、震动、IMU、串口性能和稳定性仍需 G4 真机验证。

## 灵感与来源

本项目的表情、动画和播放分层受到 [Bible Strong Avatar Lab](https://github.com/smontlouis/bible-strong-avatar-lab) 启发。它是针对 ESP32 硬件重新实现的独立 C++ 项目，不包含上游网页应用、TypeScript 源码、导出的角色数据或视觉素材。

两者的关系可以概括为：**受到架构启发，为完全不同的硬件重新实现。**

硬件初始化、引脚映射和 IMU 屏幕坐标处理参考了 M5Stack 官方的 [StopWatch User Demo](https://github.com/m5stack/M5StopWatch-UserDemo)。详情请参阅[第三方声明](THIRD_PARTY_NOTICES.md)。

## 参与贡献

欢迎提交 Issue 和 Pull Request。修改前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并运行 `pio run`。涉及硬件的结论应尽可能附上真机验证证据。

## 许可证

本项目使用 [GNU Affero General Public License v3.0 or later](LICENSE) 开源。
