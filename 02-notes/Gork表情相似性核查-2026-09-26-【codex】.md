# Gork 表情相似性核查

日期：2026-09-26。范围：只核查，没有修改播放逻辑或固件。

## 原站当前页面

实际打开 https://avatars.bible-strong.app/ 并进入 Grok bot → Animations，页面显示 23 animations，名称与项目全部对应。现场 happy 详情为 4 个姿态、每步保持 2.3 秒、首次眨眼 2.1 秒、随机间隔 2.8–5 秒、眨眼 260 ms。

## 固定来源数据比较

03-Src/avatar-library/defaultStudioDocument.json 与 Watch 正式 avatar-studio-project.json 的 sequences 数组完全一致，均为 23 条。此结论针对项目固定来源快照，不等于已逐字节核对当前站点全部部署资产。

23 条序列的第一步只有 10 种姿态：
- excited / happy / laughing / playful / celebrate 共用 expression-02。
- curious / surprised / scared 共用 expression-03。
- bored / drowsy / sad 共用 expression-04。
- 其他重复首姿态还包括 sleeping/waking、idle/shy、searching/proud、working/angry、suspicious/confused。

忽略名称/语义/步骤标识后，surprised 和 scared 的步骤、保持/过渡时间、过渡类型、循环方式及眨眼参数完全一致。happy 前三步与 laughing 相同，happy 多一步 expression-19；二者眨眼节奏不同。

## 我方显示造成的额外相似

1. gork-avatar.js 的 still 模式一律取 steps[0] 的稳定阶段。因此当前 23 张缩略图只呈现 10 个起始姿态；重复的缩略图是本轮设计问题，不能当作 23 张独立表情图来理解。
2. Gork 默认仍使用简化二维眼睛投影，headY/headX 分别除以 45 后又除以 35/28，头部偏转影响弱；其他形象已走上游几何。不能宣称默认 Gork 视觉与原站渲染完全一致。
3. 我方眨眼使用固定 minIntervalMs，而原站标示随机 min–max 间隔；我方 also 未调用原站 ambientMotion。原 23 内置序列是否实际引用自定义抖动姿态须按引用核对，不把未引用的姿态当已丢失动作。

建议：缩略图选取有辨识度的代表阶段，保留悬停完整预览；默认 Gork 对齐上游几何与眨眼时序。原站本来重复的 surprised/scared 若需区分，应明确作为自定义动画调整，不能假称恢复原作差异。
