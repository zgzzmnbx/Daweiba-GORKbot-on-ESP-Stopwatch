# v0.9.0 实施与验收记录

日期：2026-09-23。电脑端源码版本 `v0.9.0-dev`；独立语音服务保持 `v0.3.2`；设备保持 `v0.8.6-dev`。

## 范围和保护

- 实现四页“对话 / 角色 / StopWatch / 设置”、全局停止、工作台控制权与语音会话解耦、手动角色/气泡和桌面接收。
- 提取浏览器 `Recorder`/`WavPlayer`，保留独立 HTTP `VoiceClient`，提供独立调用示例及说明。
- 未改外部语音仓库、模型、venv、Key、固件或设备；未烧录、未清绑定、未发云端请求、未更新旧发行包，也未重启正式实例。
- 开始时工作区已有大量脏改动；本轮只在电脑端、v0.9.0 交付目录及项目上下文定点修改，未执行 reset、clean 或整仓提交。

## M0–M5

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| M0 | PASS | 已核对 PRD 16、任务书 17、补充 18、现有接口与脏树 |
| M1 | PASS | hash 四页导航、全局状态和停止入口；隔离浏览器逐页检查 |
| M2 | PASS | 对话/设置原有 API 与许可、音色、试听逻辑保留；浏览器和 Node 回归 |
| M3 | PASS | 30 秒工作台租期、独立语音释放、角色/气泡接口及模拟回归 |
| M4 | PASS | StopWatch 日常声音/连接、折叠实验区、共享 BLE 客户端和桌面状态接入 |
| M5 | PARTIAL | 自动回归、隔离浏览器截图、文档完成；真实 Electron、声音与设备门禁待人工 |

## 自动与隔离运行证据

| 项目 | 结果 |
| --- | --- |
| Python：电脑端测试 + 工具回归 | 83 passed |
| 浏览器逻辑：`node --test test_browser.mjs test_audio_client.mjs` | 11 passed |
| Electron 单元测试：`npm test --prefix 03-Src/gork-desktop` | 7 passed |
| 同源渲染器导出检查 | PASS：网页/桌面 catalog 与 renderer 一致 |
| 隔离网页 | 8876 端口、无语音服务配置；四页 hash 导航正常，390 宽 `scrollWidth=clientWidth=375` |
| 截图 | `screenshots/dialogue.png`、`character.png`、`watch.png`、`settings.png`、`dialogue-narrow.png` |

## U01–U28 与 V01–V08

- U01、U05、U07、U08、U10、U12、U13、U15–U21、U23–U27：源码、模拟或隔离浏览器覆盖通过。
- U02：390 宽隔离截图与无横向溢出检查通过。
- U03、U04、U06、U09、U11、U14、U22：自动覆盖关键取消、IME Enter、会话/控制权、桌面 IPC 边界；真实浏览器/桌面人工复查待做。
- U28：NOT_RUN。真人识别、云音色、设备实屏与声音没有在本轮执行。
- V01：PASS，`VoiceClient`/`audio-client.js` 无 Gork/BLE/模型依赖；未复制语音引擎。
- V02：PASS。以 `127.0.0.1:8875` 临时启动独立语音服务 v0.3.2；调用 `capabilities` 和独立示例 TTS，得到 147,244 字节 PCM WAV。Gork 后端/Electron 与正式服务均未启动。
- V03：PASS。使用语音仓库自带的非私人 `zh.wav` 做隔离 ASR，返回 `sherpa_sensevoice` 且文本非空；未使用麦克风或云端请求。
- V04：PASS，`WavPlayer` 注入式停止与迟到结束回归通过。
- V05、V06：PASS。控制器测试覆盖显式接管、释放语音仍保留工作台、旧 generation 失效；隔离服务实测首会话占用时第二会话返回 HTTP 409，释放后新会话可创建。
- V07：PASS，既有能力目录/旧服务兼容和协议版本拒绝回归通过。
- V08：PASS，模块导入、页面打开和示例默认仅探测能力，不录音、不播放、不发云请求。

## 人工门禁

1. 退出旧托盘实例后重新运行 `start-gork-console.cmd`，检查实际 Electron 的角色一次播放、气泡不裁切、托盘与单实例。
2. 在明确授权下分别做真人麦克风、本地/云端音色、真实 StopWatch 表情、六声音量/停止、延迟音频和长稳验收。
3. 如需复测语音模块，先确保没有 Gork 占用会话，再在独立服务上用合成或仓库自带的非私人 WAV 执行；不使用私人录音。
