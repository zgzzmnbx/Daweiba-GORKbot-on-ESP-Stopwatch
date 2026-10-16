# PC v0.20.40-dev 顶栏电脑语音音量验收

日期：2026-10-14。范围：PC控制台与本机语音输出。正式进程保持，Watch固件不改。

## 交付行为

顶栏五个快捷图标左侧增加Phosphor喇叭、0–100%滑块与百分比。默认100%延续原响度；键盘可调，0%静音。明/暗与经典主题共用，窄窗口把音量和快捷图标排列为两行。

电脑对话朗读、设备录音在电脑回放、声音/语音库试听使用Web Audio GainNode，当前播放即时调整。程序推送和旧任务哨兵的电脑语音在工作线程里按保存比例衰减PCM16，从下一段开始生效；已有完整片段的Windows播放保持到结束，不因调节重新播放或中断。原缓存WAV不改、不重新合成；声音ID、音色、速度、上传许可保持。

不调系统音量、不调麦克风增益、不修改Watch输出音量，也不为拖动滑块录音/合成/试听。Watch设备页原音量滑块保留。系统短提示音和架构视频不由本语音滑块调节。

`GET /api/voice/volume` 返回安全的单一整数音量；`PUT /api/voice/volume` 要求现有工作台owner并严格接受0–100整数，额外字段/布尔/小数/字符串拒绝。保存到同目录受忽略的`voice-volume.local.json`，当前Controller测试默认内存隔离。连续拖动300ms合并提交、松手立即保存、请求串行且最后值优先；失败回退确认值并提示，未知读取禁用，取得控制权不使用强制接管。

## 验证结果

- **257项后端通过**，其中新增音量覆盖PCM样本50%/0%、格式保持、原音频不变、owner/范围校验、持久化、不启动播放，以及生产通知PC分支衰减/Watch分支原样。
- **113项界面通过**，覆盖读取已存音量、实时GainNode、拖动最新值合并、失败/控制权占用回退和未知禁用，并保留上一版全部回归。
- `npm run check:ui`与`git diff --check`通过；两条既有Starlette/anyio弃用警告。
- [隔离Electron结果](tests/result.json)：生产HTML/ES模块与原严格CSP；启动显示已存37%，实际拖动/提交24%，百分比同步；经典、Mantine明/暗×1180/390共6组，音量与五图标均完整、无横向溢出，配色/开关/通知入聊原回归保持。
- Web Audio实测用替身AudioContext核对真实WavPlayer的GainNode连接与当前播放增益；后端用真实PCM字节核对幅度，实际Electron核对页面操作与API请求。本轮未播放真实音频，人耳响度由用户自然使用确认。

![隔离顶栏预览](tests/header-preview.png)

[暗色窄窗](tests/header-mantine-dark-390.png) · [浅色宽窗](tests/header-mantine-light-1180.png) · [经典宽窗](tests/header-classic-1180.png)

图标为既有固定提交Phosphor regular新增`speaker-high.svg`，来源、上游MIT许可保持。

## 当前正式运行与加载

结束前仅GET健康检查：正式8766为v0.20.39-dev，voice.ready=true，Watch按键对话enabled=true、stage=ready。未刷新、重启或接管用户窗口；源码与五处元数据已更新v0.20.40-dev，新音量接口须从托盘正常退出、原入口重开后加载。仅刷新旧后台会显示未知/禁用，不冒充保存成功。

README、项目AGENTS、当前版本计划和最近五版CHANGELOG已更新，更早版本已归档。原未提交改动保留，本轮未提交或推送，原性能/长稳延期保持。
