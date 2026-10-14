# PC v0.20.5-dev 按键对话与 DeepSeek 配置

## 当前结论

用户所见启用后自动退回，现场/api/health仍v0.20.3、answer.enabled=false，原因为未配置回答服务。缺项会被后端拒绝，旧UI只在StopWatch另一页写泛化错误，本页开关在下一次轮询退回。现已补就地说明和待确认状态，并按用户指定提供DeepSeek配置入口。

## 实施

设置→AI回答·DeepSeek：模型选择、API Key密码框和保存。支持deepseek-flash、deepseek-v4-pro，接口固定https://api.deepseek.com/chat/completions，使用非思考模式；既有其他OpenAI兼容配置/环境变量保持可用。DeepSeek来源2026-10-04核对：[官方首次调用](https://api-docs.deepseek.com/zh-cn/)、[官方Chat Completions参数](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/)。

Key在提交时立即从密码框清空，仅Windows当前用户DPAPI加密内容原子保存到Git忽略answer.local.json；读取公开接口只返回模型/key_saved/错误，不含Key/密文。不写全局环境或浏览器存储，不在工具脚本/日志中存用户Key。留空保存保留既有Key，重启恢复。配置写入需现有工作台控制权，正在问答/设备音频/按键委托时拒绝保存。输入校验不回显秘密，固定地址防止向任意地址转发Key。已有请求权限保持独立，保存不录音、不发问、不修改许可。

按键对话缺AI时开关禁用且显示缺项；后端请求中的用户意图不被健康轮询覆盖，失败后回到真实状态并保留明确原因。后台许可撤销同样留原因，手动关闭/成功重试清理旧错误。指南对应官方硬件G2/A黄色键、G1/B蓝色键。

## 验证

- 165 Python全回归：实际DPAPI加密保存/读取/模型更新/空Key保留/损坏文件保留；HTTP控制权/非法输入/忙态拒绝/重启读取，公开接口不回显Key；生产AnswerClient通过MockTransport检查官方地址/Bearer/非思考模式/文本回答。
- 73前端：生成真实DOM与控制器测试，缺AI不发启用请求，异步请求期间轮询不拨回，拒绝原因跨轮询保留，成功重试恢复，停止失败不误报关闭；Key仅明确保存提交，立即清空，无浏览器持久化或正文回显。
- 32桌面，UI构建一致性，git diff --check通过。两个现有依赖弃用警告，零失败。
- 隔离Electron两主题四宽1480/1180/800/390，共32个界面（网络展开/收起、缺AI的按键区、新设置页）通过。检查宽度和控件边界，无裁切；截图已查看。首次经典800反馈超出视窗已压紧后重新通过。全部使用本地替身服务、独立profile，不调用真实Watch或云端；测试重启服务禁用了Robot.start，使用临时加密测试Key。

## 使用与现场门禁

正常退出并重开Gork，版本应显示v0.20.5-dev。设置→AI回答·DeepSeek，在本机输入Key并保存；建议先撤销聊天中已公开的旧Key，换新Key。没有使用聊天中的Key，没有真实调用DeepSeek。随后勾选允许向回答服务发送文字并应用；云端TTS另需文字上传许可，本地ASR不需上传录音。到对话页启用Watch按键对话，等等待按键，按住G2/A、亮REC后说、松开发送；G1/B停止。

尚未验收真实DeepSeek鉴权/额度/返回、Watch麦克风按键链路、可闻回答或BLE完整恢复/T12/T13。Watch保持用户已验v0.11.5；本轮无刷机、网络修改、提交/推送。正式运行仍以tests/public-health.json和当次/api/health为准。

## 恢复与记录

README/两个模块README/AGENTS/当前版本计划/CHANGELOG同步，PC与桌面元数据0.20.5-dev，CHANGELOG最多5版本，超出归档。此次变更前逐文件备份Codex-Temp/toggle-v0205/baseline/，保留原有dirty修改。已保存本机Key配置独立于源码，不随源码回退清除；不得将此私有文件打入发布包。
