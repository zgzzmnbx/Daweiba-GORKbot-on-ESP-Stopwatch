# Avatar Lab 固定来源快照

上游：https://github.com/smontlouis/bible-strong-avatar-lab
参考站点：https://avatars.bible-strong.app/
提交：79fe9ba06e4874b11394b8e8a3f2c493c9d197ba（项目原有本地参考，2026-09-26 导入）。
许可：AGPL-3.0-only，全文见 LICENSE；保持既有个人、非商业、本地使用范围，本版不公开发布。

- defaultStudioDocument.json：上游 10 个形象的完整几何/眼睛/配色与动作快照。
- standaloneEngine.generated.ts：上游预生成无依赖几何引擎源字符串，未经修改。
- upstream-core/：对应 TypeScript 源码；预生成引擎入口为 geometry 的 expressionFields / poseFromExpression / renderAvatar 及 ambientMotion 的 ambientBodyOffset / ambientEyeOffset / applyAmbientBodyMotion / applyAmbientMotion / hasAmbientMotion。
- 我方适配：static/gork-appearance.js 负责白名单配置、颜色与 Canvas Path2D 绘制；旧 Gork 默认路径保留。其他形象使用正式上游几何而非近似 CSS 轮廓。

可复现分发（无需临时克隆、网络或新增 npm 依赖）：

    python tools/export_avatar_library.py
    python tools/export_desktop_avatar.py

两个命令均支持 --check。完整引擎重新编译可在对应提交上执行原 scripts/generate-standalone-engine.mjs；日常导出直接用本目录保留的上游预生成源码。
