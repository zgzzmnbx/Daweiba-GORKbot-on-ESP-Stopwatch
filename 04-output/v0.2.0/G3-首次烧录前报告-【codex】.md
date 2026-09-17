# G3 首次烧录前报告

任务编号：`KGA-20260916-LUNA-01`  
版本：`v0.2.0`  
结论：`完成构建验证，等待首次烧录授权`  
当前停止点：`G3`  
报告日期：2026-09-16

## 1. 实际改动

- 在 `03-Src/stopwatch-grok-avatar/` 导入 KK StopWatch Avatar，并锁定上游提交 `204963257cb4dc2f3d7501eff900897bac55ef82`，工作分支为 `kk-grok-v0.2.0`。
- 保留 KK 的 M5Unified 初始化、触摸、IMU、按钮、振动、串口命令、状态时间轴、`16667 us` 调度、5 秒指标和 dirty-rectangle 主流程。
- 导入 `grok-icon-study` 几何源文件，锁定提交 `647e9bd7c60290c42a738fad586589b3f36a4680`；使用 Python 标准库转换为固定点 C++ 几何和清单。
- 新增 `GrokRenderer`：白色主体、黑色眼形负空间、12 状态到 8 个实现眼组的映射、固定数组绘制、主体边界和几何性能指标。
- 新增 12 张单态 SVG、3 组关键帧对照、联系表 HTML、确定性转换测试、负向夹具、不变量和安全审计。

## 2. 验证结果

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 原版 KK 基线构建 | PASS，退出码 0 | `evidence/L2-baseline-build.log` |
| Grok 转换与负向测试 | PASS，8 个 Python 测试，退出码 0 | `evidence/L3-conversion-tests.log` |
| 12 状态桌面预览 | PASS，浏览器实际加载 12 状态 + 3 关键帧 | `evidence/L4-visual-review.md`、`evidence/L4-preview-grid.png` |
| 视觉评分 | PASS，平均 `8.83/10`，无硬否决项 | `evidence/L4-visual-review.md` |
| 固件分步构建 | PASS，退出码 0 | `evidence/L5-grok-build.log` |
| 最终干净构建 | PASS，清理 `.pio` 后退出码 0 | `evidence/L6-clean.log`、`evidence/L6-final-build.log` |
| 最终测试与不变量 | PASS，三个测试阶段退出码均为 0 | `evidence/L6-tests.log` |
| 依赖/平台锁定 | PASS | `evidence/L2-packages.txt`、`evidence/L6-tests.log` |
| 设备写入 | `NO`，未执行 | `evidence/L6-tests.log` |

### 最终产物

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| [firmware-v0.2.0-grok-avatar.bin](firmware/firmware-v0.2.0-grok-avatar.bin) | 906592 bytes | `47C72B834883DE457995B15F024EEA4C8F625AA762E563F1952A350145FAB1CD` |
| [firmware-v0.2.0-grok-avatar.elf](firmware/firmware-v0.2.0-grok-avatar.elf) | 16707688 bytes | `CCC8DA5D5394DA5BCEAD3425DCBE388E6F2111BF26F58169EA6B30D244339B01` |
| [firmware-v0.2.0-grok-avatar.map](firmware/firmware-v0.2.0-grok-avatar.map) | 12376030 bytes | `D2EE42A5E8A59F956B306BC25311FBC22AA0DC5E6DD5CE71D9EAE3F318E8B6AF` |
| [bootloader-v0.2.0-grok-avatar.bin](firmware/bootloader-v0.2.0-grok-avatar.bin) | 15104 bytes | `2A71D69B471E20C2BAC7FB469F3C6A807B3EBEE780E348E5889DB0DA849CA363` |
| [partitions-v0.2.0-grok-avatar.bin](firmware/partitions-v0.2.0-grok-avatar.bin) | 3072 bytes | `BD0F7954ACA2EF7D925EE21AAA1F3DC8822D1D6CE5CBBD26A135E5886BFFF6CE` |

构建期占用对比：原版 Flash `881457` bytes，Grok Flash `906229` bytes，增加
`24772` bytes（`2.81%`）；RAM 从 `29872` 增至 `29888` bytes，增加 `16`
bytes。此处是 map/build 统计，不是真机 FPS 或稳定性结论。

## 3. 环境、来源和源码状态

- Python：`3.14.3`
- PlatformIO Core：`6.1.18`，项目隔离环境 `Codex-Temp/.venv-platformio/`
- Platform：`espressif32 @ 6.12.0`
- Board：`esp32s3box`
- Framework：Arduino `3.20017.241212+sha.dcc1105b`
- M5Unified：`774d920cd6851a5231748b56ece1b073645f313f`
- M5GFX：`93b480bb349749202c8a2a953065c8ae95f58320`
- M5PM1：`be9a5456c007c333e7ac963f33bfde1ffa5d82ee`
- M5IOE1：`846eec7d05e25c09013be2acdb8804487f48a62e`
- 分支基线提交：`204963257cb4dc2f3d7501eff900897bac55ef82`
- 当前源码状态：工作树含本次有意修改和新增文件，尚未提交；未伪造本地提交哈希。
- 来源与许可证边界：KK 的 AGPL-3.0-or-later 记录在 `LICENSE`；Grok 参考仓库锁定提交未含许可证文件，本版本按已确认的个人、非商业、本地使用范围处理，不作公开发布或再分发权利声明。

## 4. Flash 与分区边界

`platformio.ini` 当前只读核对到以下配置：

- Flash：`16MB`
- 分区表：`default_16MB.csv`
- `board_upload.maximum_size`：`16777216`
- Arduino memory type：`qio_opi`
- 分区表中的 `app0`：offset `0x10000`、size `0x640000`；`app1`：offset `0x650000`、size `0x640000`
- 未配置固定 `upload_port`；未选择端口、未运行 `pio run --target upload`，也未运行任何写 Flash 命令。

若未来获得明确授权，标准应用写入的预计范围只能作为待复核计划：优先核对实际设备、MAC、分区表和当前应用槽位，再决定是否只写 `app0` 或采用其他明确方案。当前报告不把预计范围当作已发生事实，不执行整片擦除、分区变更、eFuse、安全启动或 Flash 加密操作。

## 5. 恢复点与设备识别

两份恢复镜像均为只读核验结果：

1. 项目副本：`04-output/backups/2026-09-16-StopWatch-current-state-v0.1.1/StopWatch-current-fullflash-16MB-20260916.bin`
2. 第二副本：`C:\Users\zgzzm\Documents\M5Stack-Backups\2026-09-16-StopWatch-current-state-v0.1.1\StopWatch-current-fullflash-16MB-20260916.bin`

- 大小：`16777216` bytes
- SHA-256：`ACC86A969D2C201564A0910654261381A7A7D9F3D579A692908B24799626B87B`
- 当前端口：`待 G3 放行后重新识别`；L0 的 `COM3/COM4/COM5` 只是枚举快照，不能直接沿用。
- 当前 MAC：`待重新识别`。
- 硬件版本和 `BAT/5V IN` 标识：`待人工确认`。

## 6. G3 决策

截至本报告生成时，已完成本地源码、转换、桌面视觉、静态检查和干净构建；尚未完成任何真实设备显示、触摸、按键、振动、IMU、串口性能或 30 分钟稳定性验收。

**是否授权首次烧录 v0.2.0？当前状态：等待大尾巴明确回复。**

在收到明确授权前，任务停止于 G3，不执行端口写入、擦除、分区修改、eFuse、Flash 加密或安全启动相关操作。

## 7. 后续执行附记（2026-09-16）

大尾巴随后明确回复：`授权首次烧录 v0.2.0`。授权后的 G3 只读预检已通过：
当前设备为 `COM5`、ESP32-S3 rev `v0.2`、MAC `28:84:85:44:6C:00`、16MB
Flash；写入前完整恢复镜像与设备 `verify_flash` 返回 `digest matched`，安全启动
和 Flash 加密均关闭。

随后完成 G4 首次写入：bootloader、既定分区表、`boot_app0` 和 v0.2.0 应用均写入
成功，四段写后读回校验均为 `verify OK (digest matched)`。详见
`evidence/G3-device-preflight-20260916.txt` 和
`evidence/G4-flash-and-verify-20260916.txt`。真机显示、输入、振动、IMU、串口性能
和稳定性验收仍未完成。
