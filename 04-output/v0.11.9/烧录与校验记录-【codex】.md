# Watch v0.11.9-dev 烧录与独立校验

时间：2026-10-05T20:14:04+08:00。用户本次明确回复“授权”，对应已构建的v0.11.9录音开头保护镜像。只写app0，其他分区保留。

重新枚举唯一ESP USB设备COM5，USB序列和工具读取物理MAC一致，ESP32-S3/QFN56 rev0.2、PSRAM8MB、Flash16MB。读取分区确认app0地址0x10000、容量0x640000；读取OTA有效序列1，当前槽app0。

旧v0.11.7 app2234144bytes通过独立verify_flash。新v0.11.9 app2234400bytes仅从0x10000写入，实际擦除范围0x10000—0x231fff，位于app0内；写入Hash校验通过，另进程verify_flash再次digest matched，随后hard reset。未写NVS、热点、蓝牙绑定、设置、引导、分区表、OTA元数据或芯片安全配置。

首次调用误用companion Python环境，缺intelhex，在导入工具阶段即失败；此时设备未操作。切换项目既有.venv-platformio后完整执行成功，未安装或修改依赖。过程日志见tests/flash-*.log。

完成写入和独立校验；**不等同于正常启动、实屏版本或首字录音改善验收**。请正常重启（不按住烧录键），核对Settings v0.11.9-dev，再在红色REC出现后立即说完整短句，检查识别文本开头。准备时保留500ms实际采集前缀再亮REC，总10秒含准备期，REC后约9.5秒。性能/长稳仍按用户要求延期。

PC源码v0.20.25-dev，正式最近读取v0.20.24-dev，当前识别/合成已是cloud/cloud、Ethan。未重启Gork、未由助手录音或调用云、未提交/推送。
