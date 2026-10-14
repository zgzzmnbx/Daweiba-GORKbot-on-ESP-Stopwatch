# 笔型视觉参考与来源

本次查看了以下开源项目的实际 SVG 图形与官方许可，借鉴其扁平轮廓、清晰端点和少量内部线条。正式动画中的四种笔形为本预览重新绘制的 Canvas 路径，并以笔尖 `(0,0)` 为统一锚点；没有复制这些项目的 SVG 路径，也没有将整个图标库加入网页。

## Lucide

- 羽毛轮廓、中心羽轴和少量横切线：https://lucide.dev/icons/feather
- 钢笔尖的尖端、呼吸孔和中缝：https://lucide.dev/icons/pen-tool
- 极简铅笔轮廓：https://lucide.dev/icons/pencil
- 仓库：https://github.com/lucide-icons/lucide
- 官方许可：https://lucide.dev/license

Lucide 主体采用 ISC；其中 feather 图标源于 Feather 项目，官方许可页列明相关部分采用 MIT（Cole Bemis）。本次仅研究视觉结构，未复制上述图标路径。

## Phosphor Icons

- 毛笔／画笔的简化笔锋与笔杆：https://github.com/phosphor-icons/core/blob/main/assets/regular/paint-brush.svg
- 项目：https://github.com/phosphor-icons/core
- MIT 许可：https://github.com/phosphor-icons/core/blob/main/LICENSE

研究其笔锋和柄的辨识方式，实际 Gork 毛笔改绘为适合白色单色、小尺寸动画的笔尖锚定轮廓。

## 当前代码许可

Gork 身体／眼睛仍使用原先保留的 Bible Strong Avatar Lab @79fe9ba 程序几何与 AGPL-3.0-only notice。本次原创笔形、笔迹路径和编辑器更改同样以 AGPL-3.0-only 提供；完整源码随网页下载，完整许可在 LICENSE.upstream。
