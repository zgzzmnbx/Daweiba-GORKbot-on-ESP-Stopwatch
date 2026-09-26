# 控制台表情菜单实施与验收

版本：v0.14.5-dev；日期：2026-09-26。

## 使用

控制台左侧机器人下方点击「表情菜单」展开；默认收起。选择「桌面小人 / Watch 小人 / 两端」及「一次 / 循环」，点击带预览的表情卡片发送。悬停或键盘聚焦只在缩略图中预览，不发送；点击标题或 Esc 收起。选择待机结束所选目标的循环。23 个标准动画全部可选，设备专属 happy-work 仍从角色页发送。

参考用户指定的 https://avatars.bible-strong.app/ ，2026-09-26 实际检查其 Grok bot → Animations 23 项选择器；当前缩略图与悬停动画复用项目既有固定来源 catalog 和共享 Canvas 渲染器，未引入远程运行依赖。正式来源提交见项目 AGENTS。

## 范围与交互

- 仅控制台菜单和共享渲染器增加静态缩略图模式；没有在悬浮小人窗口增加菜单。
- 缩略图取正式动画第一步的稳定姿态，部分动画起始姿态相同，悬停可辨识后续动作；静态预览不注册持续动画帧，收起立即释放当前预览。
- 保留既有 /api/character、工作台控制权与单一 BLE 通路；首次点击只申请 replace=false，不自动接管或另建连接。Watch 离线阻止发送，预览仍可用。
- 两端接收结果分别显示；服务器「桌面已接收」不代表悬浮窗口已显示。停止后忽略迟到结果，录音/朗读/设备音频期间阻止快捷发送。
- 修复辅助隐藏文字脱离左栏滚动边界引起的根页面溢出；长菜单/日志仍在左栏内部滚动。

## 验证

- node --test 03-Src/stopwatch-voice-companion/tests/test_browser.mjs 03-Src/gork-desktop/tests/*.test.js：64/64 通过。
- python tools/export_desktop_avatar.py --check：桌面与网页正式 renderer/catalog 一致。
- 新回归覆盖：23 项惰性创建；悬停不发送；静态画面不调度动画；折叠释放动画与展开不重复节点；桌面/Watch/两端路由；部分失败；工作台占用不接管；离线限制；连续点击互斥；全局停止后不恢复迟到表情。
- 隔离网页：8879，auto_connect_voice=false、auto_connect_device=false、voice_service_command=[]。通过真实页面点选桌面表情确认 API 接收、切换 Watch 显示未连接提示；没有连接实体 Watch、没有语音请求。
- 展开状态 1180×820、800×540、390×540 检查；页面根 scrollWidth/scrollHeight 与视口相等，没有整页溢出。浏览器无控制台脚本错误。
- 效果截图：表情菜单预览-【codex】.png。

正式实例未重启，悬浮窗口/Watch 真机响应待用户操作确认。隔离预览不替代设备验收，固件未修改或写入。源码版本、README、当前计划、AGENTS 和 CHANGELOG 已同步；保留其他任务已有未提交改动。
