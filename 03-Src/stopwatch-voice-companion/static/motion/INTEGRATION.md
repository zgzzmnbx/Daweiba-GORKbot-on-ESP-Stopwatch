# Gork 动作编辑器：导出与项目接入

## 先调整，再接入

1. 选择待机／加载／书写／疑惑，调整眼睛、道具和节奏
2. 暂停可检查静态位置；重播可看入场，完成可看退场
3. 从「编辑对象」选择已有自定义表情或新建，新建时填写名称并点「保存为新表情」；选中已有条目后点「保存修改」更新该条目。点「另存为新表情」保留原条目并新增，同名自动生成递增副本；最多 64 个。
4. 保存只更新自定义表情库及菜单，不影响默认表情或当前播放；点击左侧菜单才播放新保存参数。
5. 导出 JSON 保存草稿；「导出 Watch 参数」输出所选自定义表情已保存的 Watch JSON 和 C++ 头文件，供候选工程重新编译。

Windows v0.19.3 使用独立的 `03-Src/stopwatch-voice-companion/motion-library.local.json` 保存命名自定义表情，备份 `.bak`；浏览器草稿不能代替正式库。原 `motion.local.json` 保留为只读新建草稿来源，默认表情始终保持原版。播放时才读取条目并等待 Electron 播放器 ACK；保存期间不改变当前播放快照。Watch 使用构建时参数转换，本页不连接或写入设备。当前语义见根目录 PRD 33 和 `04-output/v0.19.3/`；字段映射沿用 PRD 32。

## 格式和真实消费者

这是单独的 `gork-motion-studio` v2 配置，不是上游 `.avatar.json`、Studio project JSON、GorkCatalog 或 Watch 固件配置；不要直接覆盖它们。

- 顶层固定为 `schema`、`version`、`scenes`
- 四个固定场景：`idle`、`loading`、`writing`、`question`
- `eyes`：位置、左右眼宽高、间距、头部三个旋转角度
- `motion`：循环速度倍数、进入与退出时长（毫秒）
- 非待机场景带对应道具组。书写仅保留笔和笔迹，共用整体位置；笔可独立缩放并选择羽毛笔／钢笔尖／铅笔／毛笔，笔迹可调粗细
- `gork-config.js` 中 `fields` 是字段、上下界和步进的权威定义
- JSON 必须小于等于 20 KiB；禁止未知字段、任意脚本、URL、无穷值、字符串数值及越界值
- 颜色固定黑／白；位置按道具实际包围圆自动内收，最后再经过真实头部路径裁剪

网页、播放器、导出后配置消费全部复用下面的模块，导出结果不是描述性快照：

1. `../avatar-engine.js`、`../avatar-presets.js`（现有共享源码，由导出脚本同步桌面）
2. `gork-config.js`
3. `gork-pens.js`
4. `scene-controller.js`
5. `gork-renderer.js`
6. `gork-player.js`

`GorkConfig.parse(jsonText)` 严格验证并产生全新配置对象。
`GorkScenePlayer.mount(canvas, config, options)` 创建单一 RAF 播放器。

```javascript
const config = GorkConfig.parse(jsonText);
const player = GorkScenePlayer.mount(canvas, config);
player.set('writing', { force: true, mode: 'loop' });
player.setConfig(config); // 同步更新实际渲染参数
player.pause(true);
player.pause(false);
player.complete(); // 用本场景配置的 exitMs 回待机
player.cancel(); // 快速取消，退出上限 400ms
player.dispose();
```

`set` 支持 `force`、`mode: 'once' | 'loop'`、`startedAt`（Unix 毫秒时间戳）。once 播放一个内置动作周期后收起；四个场景保持各自固定动作结构，本编辑器不提供任意关键帧编辑。`getConfig()`、`getState()` 可用于验证读取。系统减少动态效果由 mount 的 `reducedMotion` 或 `setReducedMotion()` 控制。`onFrame` 与 `getState()` 均返回 `paused`、`reducedMotion`、`hidden` 和 `elapsed`；可用 `options.paused` 初始化暂停。播放器在标签页隐藏或 BFCache 暂存时冻结时钟，恢复时继续且不补跑后台时间、不覆盖手动暂停。

### 编辑器的循环播放

默认跟随 `prefers-reduced-motion`。系统要求减少动态效果时，舞台显示「静态预览」和说明，不再把静止状态标成循环。点击「播放循环」或「重播入场」会显式开启本页的完整动作预览；「跟随系统设置」可恢复默认。该选择仅在当前页面生效，不写入场景配置、不改变 Windows/手机的系统设置。手动暂停也不持久化；刷新后重新跟随系统。普通场景选择会解除手动暂停，但仍尊重当前动效模式。

原问题的可复现原因是减弱动效把循环时间置零，且 UI 没有覆盖入口；不能由此认定某一用户的 Windows 设置。

## 当前 Windows 集成

生产入口使用 `GorkDesktopSceneAdapter.mount`，默认 idle 与全部内置表情使用原版 GorkAvatar。`setLibrary(entries)` 只登记自定义条目，不更新正在播放的参数。显式 `set(customId)` 或 `playCustom(entry)` 使用条目快照播放；一次播放后回原版 idle。切换播放器前 dispose，`setAppearance` 保留原有角色及配色，自定义场景固定黑白。上方 ScenePlayer 的 setConfig 示例仅针对独立预览。

`tools/export_desktop_avatar.py` 从共享源码导出播放器、预览器、初始 JSON、许可和白名单。菜单显式播放时，preload 的 playCustomExpression(id, mode) 调用专用 bridge，从后端读取该命名条目，经 `gork:motion-config` 与 ACK 播放。保存不调用 bridge，main 不轮询替换动效参数。`avatar.js` 重载可从 main 的播放快照恢复；preload 不开放任意文件写入。`/character` 允许命名自定义 ID 的桌面目标，Watch/两端目标明确拒绝。

## Watch / ESP32

同一 v2 JSON 通过 `tools/convert_gork_motion.py` 转为 Watch v1 参数和 C++ 头文件，源码已接入 `motion_scene`/`motion_draw`，候选 v0.10.0-dev 已编译并主机仿真。编辑器 Watch 导出要求 expression_id，读取该自定义条目的已保存版本；替换候选 `src/motion_config.h` 后重新编译。没有运行时 JSON 下发；v0.19.2 未改、编译或刷写固件。设备实屏、帧率和 BLE 沿用原待验边界，完整字段映射见根目录 PRD 32。

## 来源与许可

参考编辑器：https://avatars.bible-strong.app/
上游：https://github.com/smontlouis/bible-strong-avatar-lab
项目基线：https://github.com/zgzzmnbx/Daweiba-GORKbot-on-ESP-Stopwatch/tree/c2912b8648dd9daa3c431c87b47c0c8e5a872a68

保留 Bible Strong Avatar Lab @79fe9ba 几何与原始版权 notice；本编辑器／适配器采用 AGPL-3.0-only，许可全文在 LICENSE.upstream。修改版完整对应源码可从网页「完整源码」下载。新增道具和编辑配置格式不是上游原站自带功能。

## v2 书写样式升级与兼容

当前书写不绘制手、手套或纸张边框，只绘制平面白色笔形和逐渐出现的笔迹。默认羽毛笔，可切换钢笔尖、极简铅笔、毛笔。笔尖坐标与笔迹末端来自 `GorkPens.trace()` 的同一条路径；换行时抬笔，退场时笔迹停止增长并淡出。

导入 v1：先严格检查旧结构与边界，再移除 `handScale`，补入 `penStyle: "quill"` 和 `strokeWidth: 3`，其余用户参数保留。旧的浏览器本地保存键继续读取并自动迁移。导出一律 v2，不静默接收未知字段或未知笔型。v2 笔型是配置的持久化字段，会由实际播放器消费。

笔型视觉参考及许可证记录见 PEN-REFERENCES.md；本次各笔形是为笔尖锚点和动画重新绘制的原创 Canvas 路径，没有直接复制图标 SVG。

Windows v0.19.3 显式点击自定义表情会播放完整动作，包括减少动态效果开启时；仅覆盖该播放器，不更改系统设置。桌面播放 requestId 保证 ACK 的共享状态回传不重启相同动作。默认待机及其他内置表情规则保持原版。

Windows v0.19.4 扩大书写五项范围：x −160..160、y −120..200、scale 0.25..2.5、penScale 0.25..3、strokeWidth 0.5..12。原值与 v2 格式不变，field-specs 和桌面共享文件同步；Watch 导出读取新范围并生成对应 C++ 边界。大尺寸使用已有脸部裁剪，位置保留安全中心约束；未更新当前固件候选或设备。
