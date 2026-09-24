# Gork 机器人控制台 v0.8.0-dev：Windows 本机启动说明

目标：Windows x64。本目录包已在当前电脑完成真实启动探针；它不是跨电脑完全便携包。

## 启动

1. 先启动独立语音服务，默认健康地址为 `http://127.0.0.1:8765`。不使用语音时，控制台仍可打开，但录音/朗读不可用。
2. 双击 `Gork-Robot-Console-v0.8.0-win32-x64/Gork-Robot-Console-v0.8.0.exe`。
3. 控制台后端默认监听 `127.0.0.1:8766`。重复启动只唤起同一应用，不创建第二个 BLE 控制器。
4. 关闭主窗口会收起；从托盘菜单选择“退出”才结束本程序。退出只停止本程序自己启动的控制台后端，复用的外部语音服务保持运行。

## 可选配置

配置目录位于包内 `resources/project/03-Src/stopwatch-voice-companion/`。复制 `config.example.toml` 为 `config.local.toml` 后可设置语音服务启动入口和回答适配器。不要把 Key 写入 TOML；回答服务凭据只从 `answer_api_key_env` 指定的环境变量读取。未配置回答服务时，“AI 对话”保持禁用，跟读/朗读仍可使用。

## 已知边界

- 包含 Electron 44.4.3、控制台源码和当前电脑的 Python venv；独立语音引擎、模型、回答服务、Key、StopWatch 固件均未打包。
- 当前设备仍为 v0.7.2-P0。设备内置声音需要以后经当次授权烧录 v0.8.0 固件后才可用。
- 目录包未在第二台 Windows 电脑验证；若 Python 基础运行时、VC 运行库、蓝牙驱动或语音模型环境不同，需按源码 README 安装。
- 延迟设备语音非实时。设备录音必须在 StopWatch 的 Audio test 页显式 ARM/按 A；不后台偷开麦克风。
