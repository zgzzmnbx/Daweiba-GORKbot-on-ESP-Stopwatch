# Gork Android v0.1.0-dev 安装、升级与回退

当前文件是调试签名候选，尚无目标手机安装记录。APK 包名 `com.daweiba.gork`，versionCode 1、versionName `0.1.0-dev`，minSdk 31。闪念包名为 `com.dabawei.flashnote`；安装 Gork 不覆盖闪念。

## 首次安装与核对

1. 在 Windows 命令行运行 `adb devices -l`，只对用户明确选定且显示为 `device` 的手机继续；`unauthorized` 需用户在手机上确认调试授权。
2. 安装前用 `apksigner verify --verbose <APK>` 核对签名，并核对构建原始 `app-debug.apk` 的 `aapt dump badging` 包名与版本。部分 Windows `aapt` 无法读取文件名中的中文 `【codex】`，可检查 ASCII 原始构建路径；不要以文件名推断包名。
3. 手机安装命令：`adb -s <设备序列号> install "Gork-Android-v0.1.0-dev-debug-【codex】.apk"`。安装后冷启动，确认四页、本机角色和闪念独立可打开。当前尚未执行此步骤。

## 覆盖升级

后续版本必须保持 `applicationId=com.daweiba.gork` 且使用与已安装包相同的签名，versionCode 递增。先按版本号归档旧 APK，再执行 `adb -s <设备序列号> install -r <新APK>`；检查草稿、主题、形象、目标选择保留，并确认不会自动重播旧 Watch 命令。当前调试签名是本机开发密钥，不能用于正式跨机器升级承诺；如切换正式签名，需先设计迁移路径并告知用户。

## 回退与设备绑定

保留上一版同签名 APK 才能评估回退；Android 通常阻止 versionCode 降级，若需 `adb install -d -r`，先核对应用数据 schema 与当前包兼容性。切勿为回退直接卸载而无提示，卸载会清除应用私有草稿与偏好。APK 安装/卸载不会替代 Watch 单绑定迁移；手机首次控制 Watch 须执行验收记录中的人工换绑清单。回退或停止使用时，手机手动断开，再在 Watch 本地操作恢复电脑绑定。
