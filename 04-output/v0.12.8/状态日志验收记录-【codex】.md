# v0.12.8-dev 状态日志验收记录

2026-09-24

## 变更

- 左侧日志工具栏合并，正文 14px / 1.6 行高，桌面阅读区 196px，窄屏 180px；机器人保持常驻。
- 右侧新增运行日志标签页，按全部、蓝牙（BLE/DEVICE）、语音（VOICE/SERVICE/AUDIO）、异常（警告和错误）筛选。
- 复制当前筛选内容，复制失败显示手动复制提示；两处清空同步。向上滚动暂停自动跟随，勾选后回到最新记录。
- 黑白主题共用，记录按正常、成功、警告和错误区分颜色。继续最多 120 条本页内存摘要，不记录聊天正文或原始异常，不新增后端连接或轮询。

## 验证

`node --test 03-Src/stopwatch-voice-companion/tests/test_debug_console.mjs 03-Src/stopwatch-voice-companion/tests/test_browser.mjs 03-Src/stopwatch-voice-companion/tests/test_audio_client.mjs`：40 项通过。

隔离预览端口 8878，显式关闭自动连接语音和设备、禁用托管语音启动。浏览器验证蓝牙筛选仅显示 BLE/DEVICE、复制成功提示、浅色主题和展开入口跳转。1180×820 视口完整日志区约 772×475，左侧正文高196；390×540 视口完整日志区约366×174，文档无整体溢出。

未重启正式 Electron、未连接设备、未请求云服务或烧录。正式控制台刷新可加载静态界面；刷新前保存待发送文字，本页日志刷新后清空。源码版本及 README/AGENTS/当前计划/CHANGELOG 同步。固件及语音服务未修改。
