# M5Burner v3.0 安装与烧录准备

> 记录日期：2026-09-16  
> 记录性质：官方资料核对 + 本机实测  
> 当前结论：工具已安装、程序可启动、设备端口在线；尚未下载或烧录固件

## 1. 官方流程

M5Stack 的 UIFlow2 Web 文档要求先通过 M5Burner 为设备烧录 UIFlow2 固件，再在 UIFlow2 Web 中选择设备并配置 Access Code。Windows 版本以 ZIP 形式提供，解压后运行。

- UIFlow2 Web：<https://docs.m5stack.com/zh_CN/uiflow2/uiflow_web>
- StopWatch UIFlow2：<https://docs.m5stack.com/zh_CN/uiflow2/stopwatch/program>
- M5Stack 下载页：<https://docs.m5stack.com/en/download>

## 2. 安装记录

| 项目 | 结果 |
| --- | --- |
| 下载地址 | `https://m5burner-cdn.m5stack.com/app/M5Burner-v3-beta-win-x64.zip` |
| 下载包大小 | `129377943` 字节 |
| ZIP SHA-256 | `818A4983C87BF58F1ABAB077DB3F5BB3EC0C279468648300CEF9362FA9D2C69B` |
| ZIP 条目数 | `133` |
| ZIP 路径安全检查 | 未发现绝对路径或 `..` 路径穿越项 |
| 安装目录 | `C:\Users\zgzzm\AppData\Local\Programs\M5Burner` |
| 安装文件数 | `123` |
| 安装体积 | `249507287` 字节 |
| 开始菜单 | `M5Burner.lnk` 已创建并指向主程序 |

## 3. 版本、签名与安全边界

- 外层启动器 `M5Burner.exe` 文件版本为 `1.0.0.0`，SHA-256 为 `713AD4F639A34E7B6DE41E87A489BC7F5C0E47E61A25AA023E9A8234C4702726`。
- 实际桌面程序 `bin/m5burner.exe` 文件版本为 `3.0.0`；启动后在线界面显示 `v202605221800`。
- M5Burner 两个主程序均未带 Authenticode 签名；这是核验边界，不等于安全背书。
- 内置 `packages/tool/esptool.exe` 的 Authenticode 签名有效，签名主体为 Espressif Systems (Shanghai) Co., Ltd.
- Windows Defender 实时防护已开启；对解压目录执行自定义扫描，未发现该路径相关威胁。
- 安装依据为 M5Stack 官方文档入口、官方 CDN 来源、固定哈希和本机安全扫描；后续升级必须重新核验。

## 4. 启动与设备检查

- M5Burner 正常启动并加载在线固件目录。
- 左侧设备类别中可见 `STOPWATCH`。
- 当前目标设备枚举为 `USB\VID_303A&PID_1001&MI_00`，串口 `COM5`，状态 `Started`，驱动 `usbser.inf`。
- `COM5` 只是当前快照，烧录前必须重新枚举。

## 5. 当前烧录门槛

本次没有下载目标固件、没有进入 Burn 流程、没有擦除 Flash、没有向 StopWatch 写入任何内容。首次烧录前必须完成：

1. 核对实物硬件版本和背面引脚标识。
2. 确认官方 StopWatch UIFlow2 固件版本。
3. 确认出厂固件恢复方案或接受使用官方固件恢复。
4. 重新核对 USB 数据线、目标串口和设备下载模式。
5. 获得大尾巴对“首次烧录”的明确确认。

## 6. 首次烧录时的记录要求

- 固件名称、版本、发布时间和来源。
- M5Burner 界面版本、端口、波特率及其他实际参数。
- 进入下载模式的实际操作和设备指示灯状态。
- 烧录开始/结束时间、日志、成功或失败结果。
- 烧录后的屏幕、触摸、按键、USB 和 UIFlow2 连接验证。
