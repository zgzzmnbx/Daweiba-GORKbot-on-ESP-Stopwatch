# M5Stack StopWatch 硬件与开发知识基线

> 记录日期：2026-09-16  
> 适用设备：M5Stack StopWatch，SKU C152  
> 资料性质：官方文档摘要 + 当前 Windows 本机观察；尚未进行芯片级读取和固件写入

## 1. 证据分级

- **官方事实**：来自 M5Stack 产品文档、教程或官方 GitHub 仓库。
- **本机观察**：来自 2026-09-16 当前 Windows 的 USB/串口枚举。
- **推断**：根据用户已连接 StopWatch 与 ESP32-S3 USB 特征作出的判断，必须明确标注，不能代替实机身份读取。

## 2. 产品定位与核心规格（官方事实）

StopWatch 是面向便携和交互场景的圆形触控开发板，可用于便携智能设备、电子徽章、轻量 IoT 终端和穿戴交互原型。

| 类别 | 规格 |
| --- | --- |
| 主控 | ESP32-S3R8，Xtensa 32位 LX7 双核，最高 240MHz |
| 存储 | 16MB Flash、8MB PSRAM |
| 无线 | 2.4GHz Wi-Fi |
| 显示 | 1.75 英寸 AMOLED 圆屏，466×466，CO5300，QSPI |
| 触摸 | CST820B |
| 按键 | 2个可编程按键 + 1个电源键 |
| 姿态 | BMI270 六轴 IMU |
| 时钟 | RX8130CE RTC |
| 音频 | ES8311 Codec、MEMS MIC、AW8737A 功放、8Ω/1W 扬声器 |
| 反馈 | 内置振动电机 |
| 电源 | M5PM1 多级电源管理、450mAh 内置电池、USB-C 5V输入 |
| 扩展 | HY2.0-4P、背部 2.54mm 7P/6P 总线 |
| 结构 | 52.0×52.0×15.5mm，约39g，挂绳孔、背部磁吸 |

## 3. 最高优先级安全警示（官方事实）

StopWatch 有 v1.0 和 v1.0.1 两个硬件版本：

| 硬件版本 | 贴纸标记 | 实际功能 |
| --- | --- | --- |
| v1.0 | `BAT` | `5V IN`，不是电池引脚 |
| v1.0 | `5V IN` | `5V IN` |
| v1.0.1 | `*BAT` | `BAT` |

**在实物版本和标识核对完成前，禁止向背部所谓 BAT 引脚连接锂电池。**

## 4. 操作方式（官方事实）

- 开机/复位：短按一次电源按钮。
- 关机：连续按两次电源按钮。
- 进入下载模式：用 USB-C 数据线连接电脑，长按电源键约 2 秒，绿色 LED 亮起后松开。

USB 设备正常枚举不等于已经证明处于下载模式；需要结合 LED、串口/烧录工具返回结果判断。

## 5. 主要管脚与总线（官方事实）

### 5.1 AMOLED

| ESP32-S3 | GPIO39 | GPIO40 | GPIO38 | GPIO41 | GPIO42 | GPIO46 | GPIO45 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CO5300 | CS | SCK | TE | D0 | D1 | D2 | D3 |

- 屏幕复位不直接连接 ESP32-S3，由 M5IOE1 的 `PYG5 / PYB_OLED_RST` 控制。
- AMOLED 电源由 M5IOE1 的 `PYG8 / PYB_L3B_EN` 相关控制。

### 5.2 系统 I²C

- `GPIO47 = SYS_SDA`
- `GPIO48 = SYS_SCL`

共享器件：

| 器件 | 地址/作用 |
| --- | --- |
| CST820B | 触摸控制器，触摸中断 GPIO13 |
| ES8311 | `0x18` |
| BMI270 | `0x68` |
| RX8130CE | `0x32` |
| M5IOE1 | `0x4F` |
| M5PM1 | 电源管理 |

### 5.3 音频

| 信号 | GPIO |
| --- | --- |
| I2S MCLK | 18 |
| I2S BCLK | 17 |
| I2S ASDOUT | 16 |
| I2S LRCK | 15 |
| I2S DSDIN | 21 |

- `M5IOE1 PYG3 / PYB_AU_EN`：Codec 和麦克风供电。
- `M5IOE1 PYG10 / PYB_SPK_EN`：AW8737A 扬声器功放使能。

### 5.4 按键、振动与扩展

- 黄色 KEYA：GPIO2。
- 蓝色 KEYB：GPIO1。
- 振动电机：由 `M5IOE1 PYG9 / PYB_MT_PWM` 控制。
- Grove PORT.A：GND、5V、GPIO10、GPIO11。
- 背部 `MUX_IO_1/2` 可在 UART0 GPIO43/44 与 USB GPIO20/19 间切换，默认 UART；切换由 `M5IOE1 PYG1 / PYB_MUX_CTR` 控制。

### 5.5 电源管理要点

- M5PM1 管理多级 3.3V、外部 5V、电池充电和唤醒相关功能。
- 默认充电电流为 185mA；官方表中低电平配置可到 425mA。
- RTC/IMU 中断、充电状态和外部供电可参与中断/唤醒流程。
- 低功耗开发必须同时考虑 ESP32-S3、M5PM1 和外设供电域，不能只关闭屏幕或调用普通延时。

## 6. 软件开发路线（官方事实）

### 6.1 Arduino IDE

官方快速路线：

1. 安装 Arduino IDE 和 M5Stack 板管理包。
2. 开发板选择 `M5StopWatch`。
3. 安装 `M5Unified`、`M5GFX` 并安装提示的依赖。
4. 可先使用驱动库中的 BarGraph 示例完成编译和烧录。

官方文档同时提供 Battery、Button、Display、IMU、MIC、RTC、Speaker、Touch、Vibration、M5PM1/M5IOE1 示例入口。

### 6.2 PlatformIO

官方产品页给出的基线配置如下；正式采用前仍需锁定依赖提交或发布版本：

```ini
[env:m5stack-stopwatch]
platform = espressif32 @ 6.12.0
board = esp32s3box
framework = arduino
board_build.partitions = default_16MB.csv
board_upload.flash_size = 16MB
board_upload.maximum_size = 16777216
board_build.arduino.memory_type = qio_opi
monitor_speed = 115200
build_flags =
    -DESP32S3
    -DBOARD_HAS_PSRAM
    -DCORE_DEBUG_LEVEL=5
    -DARDUINO_USB_CDC_ON_BOOT=1
    -DARDUINO_USB_MODE=1
lib_deps =
    M5Unified = https://github.com/m5stack/M5Unified
    M5GFX = https://github.com/m5stack/M5GFX
    M5PM1 = https://github.com/m5stack/M5PM1
    M5IOE1 = https://github.com/m5stack/M5IOE1
```

### 6.3 ESP-IDF

官方 `M5StopWatch-UserDemo` 是硬件评估/出厂演示参考工程，README 当前要求 ESP-IDF 5.5.4，流程为：

```text
python3 ./fetch_repos.py
idf.py build
idf.py flash
```

该路线更适合研究官方初始化顺序、电源管理、低功耗和完整硬件能力，但工程复杂度高于 Arduino 路线。

### 6.4 UiFlow2 和固件工具

- 官方支持 UiFlow2 图形化开发。
- 可通过 M5Burner 烧录官方/示例固件。
- 产品页提供 User Demo EasyLoader 和出厂固件使用/恢复教程入口。

## 7. 当前电脑连接状态（本机观察）

2026-09-16 Windows PnP 枚举结果：

| 项目 | 结果 |
| --- | --- |
| 串口 | `COM5` |
| USB VID/PID | `303A:1001` |
| 接口0 | USB 串口，Microsoft `usbser.inf` |
| 接口2 | `USB JTAG/serial debug unit` |
| 状态 | 两个接口均已启动，无设备问题 |
| 父设备标识 | `USB\\VID_303A&PID_1001\\28:84:85:44:6C:00` |

### 当前判断（推断）

`VID 303A` 是 Espressif USB 设备特征，`PID 1001` 和 JTAG/serial 组合与 ESP32-S3 原生 USB 接口一致。结合用户说明刚连接的是 StopWatch，可以高度判断它对应当前设备；但仍需只读芯片探测或后续受控烧录流程确认，不能仅凭 USB 枚举宣称已经识别到具体板型或硬件版本。

## 8. 当前本机工具状态（本机观察）

- Python：可用。
- `arduino-cli`：PATH 中未发现。
- `pio` / `platformio`：PATH 中未发现。
- `idf.py`：PATH 中未发现。
- `esptool` / `esptool.py`：PATH 中未发现。

这不代表电脑完全没有 Arduino IDE 或其他图形化工具，只表示当前命令行环境无法直接调用上述工具。

## 9. 首次开发建议顺序

1. 人工确认设备背面硬件版本和 `BAT` / `5V IN` 标识。
2. 明确首个应用和是否需要低功耗/音频/Wi-Fi。
3. 选择单一主技术栈，锁定版本。
4. 确认官方恢复固件或恢复流程。
5. 进行只读芯片探测，记录芯片、Flash、端口和安全状态；不修改 eFuse。
6. 建立最小显示/触摸/按键工程并完成干净编译。
7. 经确认后首次烧录，再按外设逐项验证。

## 10. 尚未掌握或尚未实测

- 实物硬件版本和背部引脚标识。
- 当前出厂固件版本、分区表和配置。
- 屏幕、触摸、按键、音频、IMU、RTC、振动、Wi-Fi 和低功耗的本机实测结果。
- 电池当前电量、充放电状态和实际续航。
- 不同工具链版本下的编译兼容性。

## 11. 官方来源

- 产品页：<https://docs.m5stack.com/zh_CN/core/StopWatch>
- Arduino 教程：<https://docs.m5stack.com/zh_CN/arduino/stopwatch/program>
- M5Unified：<https://github.com/m5stack/M5Unified>
- M5GFX：<https://github.com/m5stack/M5GFX>
- 出厂演示工程：<https://github.com/m5stack/M5StopWatch-UserDemo>
