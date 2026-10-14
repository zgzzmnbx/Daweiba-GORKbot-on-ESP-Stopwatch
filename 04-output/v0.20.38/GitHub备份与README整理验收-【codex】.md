# GitHub 备份与 README 整理验收

日期：2026-10-14。电脑端源码 v0.20.38-dev；本轮文档整理不增加软件版本。

## 文档整理

- 根 README 改为 GitHub 项目入口：项目用途、界面预览、功能、组件状态、Windows 安装、语音/设备配置、架构、程序接入、开发验证、文档、许可及反馈。
- 结构依据 [GitHub 官方 README 建议](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)，使用仓库相对链接与已有隔离截图。
- 原 README 共 960 行，完整保留到 `CHANGELOG-历史归档.md` 的 `readme-history-20261014` 段，注明历史快照语义。旧内容与归档正文比对通过，版本与验收记录不再留在项目介绍中。
- CHANGELOG 主文件保留最近 5 版；页首两项历史非软件发布记录也转入归档。软件版本与实际运行/设备版本分别说明。
- README 180 行，39 个链接/图片引用检查无缺失的本地目标；代码块使用项目实际入口与锁定依赖文件。

## 本轮隔离验证

| 检查 | 结果 |
| --- | --- |
| 控制服务现有 Python 测试全集 | 252 passed |
| 控制台现有 Node 测试 | 106 passed |
| Electron 现有 Node 测试 | 48 passed |
| 独立语音服务现有 Python 测试 | 47 passed |
| `npm run check:ui` | 生成 HTML/CSS 与模板/锁定依赖一致 |
| `tools/export_desktop_avatar.py --check` | 网页/桌面角色、渲染器与动效分发一致 |
| 原 README 迁移完整性、相对链接、CHANGELOG 5 版上限 | 通过 |

Python 测试有两项第三方弃用提示（Starlette/httpx 与 AnyIO），无失败。本轮日志保存在被 Git 忽略的 `Codex-Temp/github-backup-20261014/`，原 README/CHANGELOG 本机备份也在此目录。

## 提交边界

主仓库保存现有源码、配置模板、版本文档、应用区固件候选和验收资料；独立固件子仓库的 `.git` 元数据不进入主仓库，不向其上游推送。本机 `.local.` 配置/授权数据库、环境/模型、恢复备份、快捷方式及带设备标识的原始烧录日志保留本机。待备份文件的凭据格式/明文凭据检查未命中，单文件均低于 GitHub 大文件限制。

本轮未重启正式应用、未调用云语音、未读取私人录音或写入设备；现有自动测试结果不替代设备启动、可闻、性能或长稳验收。Git 提交与远端同步结果以本次提交历史和最终远端核对为准。
