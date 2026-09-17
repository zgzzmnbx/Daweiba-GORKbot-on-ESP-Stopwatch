# Luna Max 目标模式开发任务书：KK StopWatch Grok Avatar

> 任务编号：`KGA-20260916-LUNA-01`  
> 产品版本：`v0.2.0`  
> 执行方式：Luna Max 目标模式，单线程持续实施  
> 工作目录：`D:\Codex-Temp\260529-ESP-32-M5StopWatch`  
> 当前授权终点：完成可复现构建、Grok 角色集成、静态/桌面视觉验收和待烧录固件；到 `G3` 停止  
> 明确未授权：首次烧录、擦除 Flash、修改分区、读取或修改 eFuse、公开发布

## 0. 直接复制给 Luna Max 的目标指令

```text
你正在 Windows 本机执行 M5Stack StopWatch Grok Avatar v0.2.0 开发任务。

任务编号：KGA-20260916-LUNA-01
项目目录：D:\Codex-Temp\260529-ESP-32-M5StopWatch
目标：以锁定的 KK StopWatch Avatar 为底座，完成个人非商业使用的 Grok 风格圆屏角色固件，生成可复现构建产物和完整证据，但未经大尾巴新的明确确认不得向设备写入任何内容。

开始前必须完整阅读：
1. AGENTS.md
2. README.md
3. CHANGELOG.md
4. 00-docs/00-PRD/01-产品总览PRD.md
5. 00-docs/00-PRD/02-当前版本计划.md
6. 00-docs/00-PRD/03-v0.2.0-KK-Grok-Avatar开发PRD-【codex】.md
7. 00-docs/00-PRD/04-Luna-Max目标模式开发任务书-【codex】.md
8. 00-docs/00-PRD/05-v0.2.0实施进度与验收记录-【codex】.md

执行规则：
- 先回显任务编号、当前阶段、授权终点和禁止事项，再开始工作。
- 按 L0→L7 顺序执行，每个阶段必须完成该阶段验证和证据回写，才能进入下一阶段。
- 不创建子代理；不要把任务转交给其他线程。
- 不删除、reset、clean、stash、checkout 或覆盖用户现有内容；发现脏工作区先记录，只改本任务路径。
- 先复现锁定的 KK 原版构建，再改动代码；禁止边升级依赖边移植。
- 工具安装、源码导入、本机构建、Python 测试和桌面预览属于已授权范围。
- 不得运行 upload、erase、write_flash、merge_bin、eFuse、安全启动或 Flash 加密操作。
- 到 G3 必须停止，向大尾巴交付固件哈希、大小、构建日志、预览图、测试结果、端口/MAC重新识别计划和恢复点信息，等待明确烧录授权。
- 命令未运行就标记 NOT RUN；失败就记录原始错误，不得把静态检查、上游 CI 或自我判断写成 PASS。
- 每阶段都更新实施进度文件。连续三次遇到同一阻塞时，停止重复尝试，记录原因、已试方案和下一种可行路线。

最终完成标准以任务书第 13 节为准。未通过全部 G0-G2 门禁不得宣称 v0.2.0 可烧录；未获得 G3 授权不得烧录；未做真机测试不得宣称硬件验收通过。
```

## 1. 已锁定输入，不得擅自漂移

| 项目 | 锁定值 | 执行要求 |
| --- | --- | --- |
| KK 工程 | `https://github.com/Trentct/m5stack-stopwatch-avatar` | 正式源码固定到下列提交 |
| KK 提交 | `204963257cb4dc2f3d7501eff900897bac55ef82` | 先原样构建，再建立本地开发分支 |
| Grok 参考 | `https://github.com/blessonism/grok-icon-study` | 只导入实际使用的数据与来源说明 |
| Grok 提交 | `647e9bd7c60290c42a738fad586589b3f36a4680` | 不用浮动 main 替代 |
| PlatformIO Core | `6.1.18` | 使用项目本地虚拟环境 |
| Platform | `espressif32 @ 6.12.0` | 沿用 KK `platformio.ini` |
| Arduino 板型 | `esp32s3box` | 本版本不得自行换板型 |
| Flash/分区 | `16MB` / `default_16MB.csv` | 只编译核对，不写入设备 |
| M5Unified | `774d920cd6851a5231748b56ece1b073645f313f` | 不升级 |
| M5GFX | `93b480bb349749202c8a2a953065c8ae95f58320` | 不升级 |
| M5PM1 | `be9a5456c007c333e7ac963f33bfde1ffa5d82ee` | 不升级 |
| M5IOE1 | `846eec7d05e25c09013be2acdb8804487f48a62e` | 不升级 |
| 恢复镜像 SHA-256 | `ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B` | G3 前重新核对，不复制进源码仓库 |

如锁定依赖无法下载或编译，先保存错误证据。只有证明确为兼容性阻塞后，才能提出最小变更建议；不得直接升级到“最新版”。

## 2. 总体技术路线

### 2.1 保留什么

- 保留 KK 的 `M5.begin()`、屏幕、触摸、BMI270、按钮、M5IOE1 振动初始化。
- 保留 `ExpressionId` 的 12 个状态及 `once/loop/pingpong` 播放模型。
- 保留触摸跟随、四向滑动、按键浏览、IMU 倾斜、连续横向摇晃判定和 A+B 诊断模式。
- 保留 `16667 us` 帧调度、5 秒性能报告和动态 dirty rectangle 局部刷新。
- 保留 AGPL-3.0、第三方说明和上游工程文档。

### 2.2 新增什么

- 一个确定性的 Grok 几何转换器。
- 一个小型、无堆分配的固件几何数据层。
- 一个负责 blob 身体和多边形眼睛的 Grok 渲染器。
- 12 状态到 8 组首批 Grok 眼睛的显式映射表。
- 桌面 SVG 预览生成器和 12 状态预览页。
- Python 数据测试、C++ 编译验证、构建日志、哈希和交接记录。

### 2.3 首版明确不做

- 不移植 Grok 网页仓库的完整 FX、DOM、Canvas、JavaScript 运行时或全部 18 身形。
- 不在 MCU 上解析 JSON、SVG path 或 JavaScript。
- 不加入 Wi-Fi、语音、ASR、LLM、TTS、OTA、账号或云服务。
- 不重写硬件初始化，不升级依赖，不改分区表。
- 不以每帧 466×466 全屏 Sprite 作为最终渲染路径。

## 3. 正式源码目标结构

```text
03-Src/stopwatch-grok-avatar/
├─ .git/                              # 由正式 clone 保留
├─ platformio.ini
├─ README.md
├─ UPSTREAM.md
├─ LICENSE
├─ THIRD_PARTY_NOTICES.md
├─ assets/
│  ├─ source-grok-study/
│  │  ├─ geometry-data.js
│  │  └─ SOURCE.md
│  └─ generated/
│     ├─ grok_geometry_manifest.json
│     └─ previews/
│        ├─ index.html
│        └─ *.svg
├─ include/
│  ├─ grok_geometry.h
│  ├─ grok_renderer.h
│  └─ generated/
│     └─ grok_geometry_data.h
├─ src/
│  ├─ main.cpp
│  ├─ avatar_engine.h
│  ├─ avatar_engine.cpp
│  ├─ grok_geometry.cpp
│  └─ grok_renderer.cpp
├─ tools/
│  ├─ convert_grok_geometry.py
│  ├─ render_grok_previews.py
│  └─ verify_source_invariants.py
├─ tests/
│  ├─ test_geometry_conversion.py
│  └─ test_source_invariants.py
└─ docs/
   ├─ ENGINEERING_NOTES.md
   ├─ HARDWARE_BASELINE.md
   └─ ROADMAP.md
```

不要一次性创建没有用途的抽象层。只有上面列出的文件在当前版本内；如果实际工程证明某个新增 `.cpp` 没有必要，可以合并，但必须在进度记录中解释。

## 4. 几何转换的确定性规范

### 4.1 输入解析

`geometry-data.js` 当前形态为：注释行后接 `window.GROK_GEO = {JSON对象};`。转换器必须：

1. 以 UTF-8 读取文件。
2. 去掉赋值前缀和末尾分号，只用 Python `json.loads` 解析对象；禁止 `eval`、`exec`、Node 执行或浏览器执行。
3. 验证存在 `Re`、`viewBox`、`blobPath`、`palette`、`eyes`、`solids`。
4. 验证眼睛组数至少 25、身形数至少 18、颜色数至少 11；小于基线时失败。
5. 首版只输出 `blobPath`、首批 8 组眼睛及黑/白/灰色常量。

### 4.2 blob 路径转换

- 首版只接受 `M`、`L`、`C`、`Z` 绝对命令；遇到其他命令立即失败并报告，不得静默跳过。
- `C` 三次贝塞尔每段固定采样 8 个等参数点；起点只保留一次。
- 闭合前删除连续重复点；最终至少 32 点且不超过 512 点。
- 输入坐标以 `viewBox` 为准，转换到 `0..1000` 设计空间：

```text
x1000 = round((x - minX) * 1000 / width)
y1000 = round((y - minY) * 1000 / height)
```

- 输出为有符号 `int16_t`；转换后所有点必须位于 `[-128, 1128]` 安全范围，否则失败。

### 4.3 眼睛转换

- 首批固定选择原数据索引 `0..7`，不得用随机挑选。
- 每组必须恰好有左右两个闭合轮廓，每个轮廓至少 3 点。
- 使用同一 `viewBox → 1000` 公式转换；保留点顺序。
- 生成名称固定为 `eye_00` 至 `eye_07`，另在 manifest 中记录原始索引和点数。

### 4.4 C++ 数据格式

使用固定宽度类型，运行时不得申请堆内存：

```cpp
struct GrokPoint16 { int16_t x; int16_t y; };
struct GrokContour { const GrokPoint16* points; uint16_t count; };
struct GrokEyePair { GrokContour left; GrokContour right; };

extern const GrokContour kGrokBlob;
extern const GrokEyePair kGrokEyes[8];
extern const uint8_t kGrokEyeCount;
```

生成文件顶部必须写明：生成器版本、源文件相对路径、源文件 SHA-256、锁定仓库提交和“DO NOT EDIT”。生成顺序、数字格式、换行和末尾换行必须固定。

### 4.5 必测断言

- 同一输入运行两次，生成头文件和 manifest SHA-256 完全一致。
- 8 组左右眼均非空；计数没有 `uint16_t` 溢出。
- 所有点在允许范围；blob 闭合；轮廓没有连续重复点。
- 生成文件不含 `NaN`、`Infinity`、科学计数法、JavaScript 标记或绝对路径。
- 改坏一个测试夹具后测试必须失败，以证明断言真正生效；随后恢复夹具。

## 5. 首版视觉设计与状态映射

### 5.1 视觉规则

- 画布：466×466，背景 `#000000`。
- 主体：暖白 `#F4F2EC`，位于安全圆内，静态边界距画布至少 36 px。
- 眼睛：主体内部的黑色负形；边缘可用单层深灰抗锯齿，不做渐变和发光。
- 默认主体宽高约 300×300 px，中心略高于屏幕中心 8 px。
- 角色必须保持 Grok 的不规则 blob 轮廓，不能退化成普通圆脸、emoji 或两个白色圆角矩形。
- 动画只改变平移、缩放、旋转、squash、眼睛轮廓与视线；首版不做复杂粒子。
- 圆屏边缘不得裁掉主体、眉毛或眼睛；任何状态的 dirty rect 必须裁切到屏幕边界。

### 5.2 12 状态显式映射

| 状态 | 眼睛索引 | 身体/动作基调 | 返回规则 |
| --- | ---: | --- | --- |
| idle | 0 | 轻呼吸，微扫视，偶发眨眼 | 持续基础状态 |
| listening | 1 | 身体前倾 1%—2%，眼睛跟随增强 | 持续基础状态 |
| thinking | 2 | 轻微侧倾，慢速左右扫视 | 持续基础状态 |
| happy | 3 | 上弹后回落，宽扁笑眼 | 自动回基础状态 |
| excited | 4 | 两次短促弹跳，缩放幅度最大但不越界 | 自动回基础状态 |
| curious | 5 | 左右眼轻度不对称，头部侧倾 | 自动回基础状态 |
| confused | 6 | 小幅左右摆动，眼睛不同步 | 自动回基础状态 |
| angry | 7 | 压低、横向抖动，持续时间短 | 自动回基础状态 |
| surprised | 4 | 快速收缩后放大，眼睛竖向拉伸 | 自动回基础状态 |
| sad | 6 | 整体下沉，运动频率降低 | 自动回基础状态 |
| sleepy | 2 | 眼睛垂直压缩，呼吸变慢 | 自动回基础状态 |
| dizzy | 7 | 身体阻尼旋摆；如保留原闪电眼需与 blob 边界兼容 | 稳定后回基础状态 |

映射表必须集中定义，不要把 `switch` 分散在多个绘制函数。索引超界时编译期或测试期失败，不能运行时悄悄回退。

### 5.3 桌面预览硬门禁

在接入固件渲染之前，生成以下文件：

- 12 个 466×466 SVG 状态预览。
- `index.html` 联系表，4×3 排列，显示状态名、眼睛索引和主体包围盒。
- 一个交互预览页或 SVG 叠层，展示 idle→happy、idle→thinking、idle→dizzy 的关键帧，不要求浏览器动画引擎。

执行者必须实际打开预览并逐张检查，不能只检查文件存在。每张图按第 12 节视觉量表评分；出现硬否决项时必须修正后才能进入固件集成。

## 6. 逐阶段执行计划

### L0：上下文、工作区和安全基线

操作：

1. 阅读本任务书要求的 8 个文件。
2. 列出项目一级、二级文件和 `03-Src/` 当前内容。
3. 检查项目根是否为 Git 仓库；检查是否已有正式源码目录。
4. 只读检查两份 Flash 备份路径、镜像大小和已有 SHA-256 文件，不重新读取设备。
5. 检查 Python、Git、现有 PlatformIO、串口枚举，但不得连接或写入设备。
6. 在进度文件写入基线时间、命令、结果、脏文件和禁止事项。

验收：

- G0-01：8 个上下文文件全部读到。
- G0-02：未覆盖现有源码或备份。
- G0-03：明确记录“根目录当前是否为 Git 仓库”。
- G0-04：进度表状态从 `未开始` 更新为 `L0 已通过`。

失败处理：任何关键文件缺失或正式源码目录已存在但来源不明时停止，先报告冲突，不要覆盖。

### L1：正式导入 KK 锁定基线

操作：

1. 目标目录不存在时，直接 clone 到 `03-Src/stopwatch-grok-avatar/`。
2. fetch 并 checkout 锁定提交 `204963...ef82`。
3. 验证 `git rev-parse HEAD` 精确匹配。
4. 建立本地分支 `kk-grok-v0.2.0`；不要修改 `origin` URL。
5. 新建 `UPSTREAM.md`，记录两个上游 URL、提交、导入日期、用途、允许的本地改动和恢复基线命令。
6. 确认 `LICENSE`、`THIRD_PARTY_NOTICES.md`、`platformio.ini` 存在。
7. 在任何代码修改前记录 `git status --short` 应为空。

建议命令形态：

```powershell
git clone https://github.com/Trentct/m5stack-stopwatch-avatar.git 03-Src/stopwatch-grok-avatar
git -C 03-Src/stopwatch-grok-avatar checkout 204963257cb4dc2f3d7501eff900897bac55ef82
git -C 03-Src/stopwatch-grok-avatar switch -c kk-grok-v0.2.0
git -C 03-Src/stopwatch-grok-avatar rev-parse HEAD
git -C 03-Src/stopwatch-grok-avatar status --short
```

验收：G1-01 提交精确；G1-02 基线干净；G1-03 许可证和来源齐全；G1-04 没有设备写入。

### L2：项目本地 PlatformIO 与原版构建

操作：

1. 在 `Codex-Temp/.venv-platformio/` 建立 Python 虚拟环境，不修改系统 Python 默认包。
2. 安装 `platformio==6.1.18`，保存 Python、pip、pio 版本。
3. 在正式源码目录执行原版 `pio run -e m5stack-stopwatch`。
4. 保存完整日志到 `04-output/v0.2.0/evidence/L2-baseline-build.log`。
5. 保存 `.pio/build/m5stack-stopwatch/firmware.bin` 大小与 SHA-256；这是“原版基线”，不得冒充 Grok 版本。
6. 保存 `pio pkg list -e m5stack-stopwatch` 输出，核对 4 个库提交。

建议命令形态：

```powershell
py -3 -m venv Codex-Temp/.venv-platformio
./Codex-Temp/.venv-platformio/Scripts/python.exe -m pip install --upgrade pip
./Codex-Temp/.venv-platformio/Scripts/python.exe -m pip install platformio==6.1.18
./Codex-Temp/.venv-platformio/Scripts/pio.exe --version
./Codex-Temp/.venv-platformio/Scripts/pio.exe run -d 03-Src/stopwatch-grok-avatar -e m5stack-stopwatch
```

验收：

- G1-05：本机原版构建退出码 0。
- G1-06：日志、包清单、固件大小和 SHA-256 齐全。
- G1-07：没有 upload、erase 或串口写入记录。

构建失败时先分类：网络下载、Python/PIO、依赖提交、编译器、源码。每次只改变一个变量；禁止直接更新依赖。

### L3：导入 Grok 必要源数据与转换链

操作：

1. 从已锁定 Grok 提交复制 `replica/geometry-data.js` 到正式源码的 `assets/source-grok-study/`。
2. 写 `SOURCE.md`：仓库、提交、原文件路径、复制日期、SHA-256、用途和“个人非商业开发参考”。
3. 实现第 4 节转换器、manifest 和生成头文件。
4. 实现单元测试；先让合法输入通过，再用临时坏夹具证明断言会失败。
5. 连续生成两次并比较 SHA-256。
6. 将生成器输出和测试日志保存到证据目录。

验收：

- G2-01：输入来源和哈希可追溯。
- G2-02：基线数量检查通过：眼睛≥25、身形≥18、颜色≥11。
- G2-03：两次生成哈希一致。
- G2-04：全部 Python 测试通过，坏夹具验证确实失败。
- G2-05：生成文件无绝对路径、无 JS 运行依赖、无堆分配要求。

### L4：桌面预览与视觉校准

操作：

1. 实现 `render_grok_previews.py`，直接读取 manifest/生成数据并输出纯 SVG 和 HTML；优先只用 Python 标准库。
2. 生成 12 状态预览和 3 组关键帧对照。
3. 实际打开 `index.html`，检查普通窗口和放大视图。
4. 每个状态填写视觉评分、问题和修正结果。
5. 计算每个 SVG 的主体/眼睛包围盒，断言不越出安全圆和画布。

验收：

- G2-06：12 状态均可见、名称正确、不是重复占位图。
- G2-07：无越界、空轮廓、自交造成的大面积错误填充或眼睛跑出主体。
- G2-08：平均视觉评分≥8.0/10，且无第 12 节硬否决项。
- G2-09：保存预览文件和至少一张联系表截图或浏览器视觉证据。

### L5：固件渲染器接入

最小改动顺序：

1. 先新增 `grok_geometry.*`，只提供只读数据访问和边界工具；编译。
2. 再新增 `grok_renderer.*`，先在固定 idle pose 画 blob + eye pair；编译。
3. 修改 `AvatarEngine`，让现有 `Pose`、弹簧、触摸和 IMU 输出驱动 GrokRenderer；不要同时改输入逻辑。
4. 集中加入 12 状态→8 眼映射和身体参数。
5. 扩展 dirty rect：合并旧主体包围盒、新主体包围盒和必要的效果包围盒，先清旧区域再画新区域。
6. 保留 5 秒性能统计；新增串口输出几何点数、最大 dirty rect 和是否发生全屏退化。
7. 每一小步 `pio run`，失败立即定位，不积累多个未编译改动。

绘制建议：

- 将设计空间点在运行时通过统一变换映射到屏幕：中心、缩放、roll、squash、交互偏移。
- 主体使用 `fillPolygon` 或经验证的 M5GFX 多边形路径；如单个凹多边形填充错误，使用确定性三角化，不得靠拆成大量临时 Sprite 回避。
- 眼睛在主体之后以黑色填充形成负形；眨眼通过眼睛局部 Y 缩放完成。
- 绘制过程中使用固定数组或生成期三角形索引；主循环不得频繁 `new`、`malloc`、构造大 `std::vector`。
- dirty rect 加 4—8 px 安全边距并裁切到 `[0,465]`。

验收：

- G2-10：每一步本机构建成功。
- G2-11：12 状态映射完整，编译期/测试期可验证。
- G2-12：原触摸、IMU、按钮、振动、串口和诊断入口仍存在，没有被注释或短路。
- G2-13：渲染路径没有固定每帧全屏提交，没有动态内存热点。
- G2-14：`platformio.ini` 的平台、分区、Flash 和 4 个依赖提交未漂移。

### L6：回归、构建产物和静态性能检查

操作：

1. 从干净构建执行最终 `pio run`，保存完整日志。
2. 执行全部 Python 测试和源码不变量检查。
3. 不变量检查至少覆盖：12 个 ExpressionId、8 组眼睛、`16667 us` 帧间隔、5 秒指标窗口、dirty rect 函数、触摸/IMU/按钮/振动/串口/诊断入口、锁定依赖。
4. 输出 firmware.bin、firmware.elf、firmware.map 的大小和 SHA-256。
5. 从 map 文件记录 Flash/RAM 使用；如较 KK 基线上升超过 25%，解释原因并评估。
6. 扫描源码，确保没有设备写入口令、Wi-Fi 密钥、绝对用户路径或完整备份文件。

验收：

- G2-15：最终干净构建退出码 0。
- G2-16：测试全部通过，`rg` 静态不变量齐全。
- G2-17：固件、ELF、MAP、哈希、大小和日志齐全。
- G2-18：依赖未漂移，Flash/RAM 增量有记录。
- G2-19：没有执行任何设备写入。

### L7：文档、交付和 G3 报告

操作：

1. 更新源码 `README.md`：环境、构建、预览、状态控制、已知限制；烧录章节只说明“需获得授权”，不执行。
2. 更新 `UPSTREAM.md`、`THIRD_PARTY_NOTICES.md` 和工程说明。
3. 更新根 README、当前版本计划、CHANGELOG 和本进度文件。
4. 把最终构建复制到 `04-output/v0.2.0/firmware/`，把日志放到 `evidence/`，把预览放到 `previews/`。
5. 输出 `04-output/v0.2.0/G3-首次烧录前报告-【codex】.md`。
6. 报告当前源码 Git 提交或工作树状态；如尚未提交，只能写“未提交”，不能伪造哈希。
7. 停止执行，等待大尾巴明确授权。

G3 报告必须包含：

- 最终源码提交/状态、上游提交和依赖提交。
- PlatformIO/Python/编译器版本。
- firmware.bin 大小和 SHA-256。
- 分区、Flash 大小、upload 参数和预计覆盖范围。
- 所有测试及退出码、失败/跳过项。
- 12 状态预览和视觉评分。
- 当前设备端口和 MAC 的“待重新识别”状态；不得沿用旧 COM5 当作当前事实。
- 两份恢复镜像路径、大小和 SHA-256。
- 明确问题：“是否授权首次烧录 v0.2.0？”

验收：G2 全部通过，G3 报告完整。此时只能声明“v0.2.0 已完成构建验证，等待首次烧录授权”。

### G3 之后：仅在明确授权后

没有新的明确授权时，本节不得执行。授权后仍须先重新枚举端口、读取芯片基本信息、核对 MAC、检查恢复镜像，再制定一次性的上传命令。禁止整片擦除和分区变更。烧录后进入真机 G4，不得直接宣称完成。

## 7. 文件责任区

| 范围 | Luna 可修改 | 约束 |
| --- | --- | --- |
| `03-Src/stopwatch-grok-avatar/` | 是 | 正式源码主责任区，保留嵌套 Git 历史 |
| `04-output/v0.2.0/` | 是 | 只放构建、预览、报告和证据；不放隐私备份 |
| `00-docs/00-PRD/02-当前版本计划.md` | 是 | 只更新任务状态和证据链接，不改产品边界 |
| `00-docs/00-PRD/05-v0.2.0实施进度与验收记录-【codex】.md` | 是 | 每阶段必须回填 |
| 根 `README.md` / `CHANGELOG.md` | 是 | 只同步真实状态；未验证不得写已完成 |
| 根 `AGENTS.md` | 条件允许 | 只记录可复用项目经验，不写一次性错误日志 |
| `04-output/backups/` | 否 | 只读核验；不得移动、重命名或写入 |
| 其他项目和全局配置 | 否 | 不在本任务范围 |

## 8. 建议证据目录

```text
04-output/v0.2.0/
├─ firmware/
│  ├─ firmware.bin
│  ├─ firmware.elf
│  ├─ firmware.map
│  └─ SHA256SUMS.txt
├─ previews/
│  ├─ index.html
│  └─ *.svg
├─ evidence/
│  ├─ L0-environment.txt
│  ├─ L1-upstream.txt
│  ├─ L2-baseline-build.log
│  ├─ L2-packages.txt
│  ├─ L3-conversion-tests.log
│  ├─ L4-visual-review.md
│  ├─ L6-final-build.log
│  ├─ L6-tests.log
│  └─ L6-size-and-hashes.txt
└─ G3-首次烧录前报告-【codex】.md
```

证据日志不得包含 Wi-Fi、Access Code、密钥或完整 Flash 内容。

## 9. 最低测试集

| ID | 测试 | 通过标准 |
| --- | --- | --- |
| T01 | 源数据结构 | 关键字段存在，数量基线满足 |
| T02 | 确定性生成 | 两次输出 SHA-256 一致 |
| T03 | 坐标与计数 | 范围、闭合、左右眼、点数全部合法 |
| T04 | 负向夹具 | 非法命令、缺眼、越界至少各有一次失败断言 |
| T05 | 状态映射 | 12 状态全部映射，索引均 `< 8` |
| T06 | 预览输出 | 12 SVG + index.html，文件非空、标签正确 |
| T07 | 源码不变量 | 硬件输入、dirty rect、帧调度和指标入口存在 |
| T08 | 原版构建 | 锁定提交、锁定依赖构建成功 |
| T09 | 最终构建 | 干净构建成功，固件/ELF/MAP 齐全 |
| T10 | 依赖锁定 | platform、分区、Flash、4 库提交未变化 |
| T11 | 敏感信息 | 无密钥、绝对用户路径、完整备份进入源码 |
| T12 | 无设备写入 | 日志中没有 upload/erase/write_flash 行为 |

## 10. 回归清单

- [ ] `idle listening thinking happy excited curious confused angry surprised sad sleepy dizzy` 名称仍可解析。
- [ ] `once`、`loop`、`pingpong` 命令仍可解析。
- [ ] 单击/双击/长按/拖动/四向滑动处理仍存在。
- [ ] A/B 浏览及 A+B 诊断切换仍存在。
- [ ] IMU 倾斜与连续横向摇晃判定仍存在。
- [ ] 振动停止使用非阻塞计时。
- [ ] 主循环没有新增长时间 `delay`。
- [ ] 目标帧间隔仍为 `16667 us`。
- [ ] 指标窗口仍为 5 秒。
- [ ] dirty rect 同时覆盖旧、新主体和眼睛边界。
- [ ] 诊断模式退出后可恢复此前基础状态。
- [ ] 断开串口不影响固件独立运行设计。

## 11. 性能判定边界

构建阶段可验证架构和内存，不得伪造真机 FPS。G3 前允许声明：

- 帧调度目标仍为 60 FPS。
- dirty rect 和 5 秒指标采集逻辑存在。
- Flash/RAM 静态占用满足构建限制。

G3 前不得声明：

- 真机达到 60 FPS。
- 真机触摸、IMU、振动或显示已通过。
- 30 分钟稳定性已通过。

获得烧录授权后的真机目标才是：5 秒窗口≥55 FPS、常规平均渲染<12 ms、复杂状态不持续低于45 FPS、30分钟无复位、100次快速交互无卡死。

## 12. 视觉评分与硬否决项

每项 0—2 分，总分 10 分：

1. Grok 识别度：blob 轮廓和眼睛组合具有明确角色特征。
2. 构图：角色居中但不僵硬，安全边距统一，圆屏空间利用合理。
3. 表情区分：12 状态不依赖文字也能大致辨认。
4. 动作连续性：关键帧方向、缩放和 squash 合理，没有突跳。
5. 工程适配：没有不必要的发光、渐变、细碎粒子或高成本全屏效果。

硬否决项，任一出现则 L4 不通过：

- 主体或眼睛越出 466×466 画布或圆形安全区。
- 眼睛跑出主体，或左右眼意外交换/重叠。
- 12 张只是同一张占位图换文字。
- blob 被画成普通圆、emoji 或与 Grok 无关的机器人脸。
- 黑底上出现大面积低对比灰糊、明显锯齿破面或自交填充错误。
- 预览靠人工修图，不能由同一数据和脚本重新生成。

## 13. 最终完成定义

只有同时满足以下条件，目标模式才可结束：

- L0—L7 全部执行，G0—G2 所有门禁为 PASS。
- 正式源码固定在 KK 锁定提交的本地开发分支上，来源和许可证可追溯。
- 原版 KK 与最终 Grok 固件均在本机 PlatformIO 6.1.18 干净构建成功。
- Grok 数据转换确定、可重复、有负向测试；12 状态视觉预览通过评分。
- 最终 firmware.bin、ELF、MAP、SHA-256、日志和测试证据齐全。
- README、当前计划、CHANGELOG 和实施进度已按真实结果更新。
- G3 报告已经生成，并明确停在“等待首次烧录授权”。
- 没有烧录、擦除、修改分区/eFuse，没有公开发布或外部消息。

若有任一未通过，只能报告“部分完成”及阻塞证据，不能用“基本完成”“应该可用”替代。

## 14. 最终汇报模板

```text
任务编号：KGA-20260916-LUNA-01
结论：完成 / 部分完成 / 阻塞
当前停止点：Lx / G3

1. 实际改动
- 文件和模块：
- 与 KK 基线相比：

2. 验证
- 原版构建：PASS/FAIL/NOT RUN，日志：
- 转换测试：PASS/FAIL/NOT RUN，数量：
- 预览验收：PASS/FAIL/NOT RUN，评分：
- 最终构建：PASS/FAIL/NOT RUN，日志：
- 固件大小/SHA-256：
- 设备写入：NO

3. 版本与上下文
- 源码 Git 状态/提交：
- README/PRD/CHANGELOG/进度表：已更新/未更新

4. 已知问题
- 

5. G3 请求
- 恢复镜像 SHA-256：
- 当前端口/MAC：待重新识别/已只读识别
- 是否授权首次烧录 v0.2.0：等待大尾巴明确回复
```
