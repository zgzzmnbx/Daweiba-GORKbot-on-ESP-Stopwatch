# 表情列表滚动修复验收（PC v0.20.15-dev）

用户截图中列表只露出部分卡片且没有滚动条。新增检查先复现：在1480×960 Mantine视图，列表clientHeight和scrollHeight同为791px，底部1281px超过面板935px；这意味着列表自身没有滚动范围，内容被外层裁掉。见tests/before-fix.log。

浏览器为details创建独立内容盒，原flex只约束了details本身。按[Chromium官方布局说明](https://developer.chrome.com/blog/styling-details?hl=en)对::details-content设置flex、min-height:0和边界，内容区继续使用原flex布局，网格占剩余高度。仅添加100%高度无法约束内部盒，其诊断保留为tests/height-only-attempt.log。表情与日志使用overflow-y:scroll、稳定滚动条占位及可见颜色，网格横向不溢出；标签、卡片、表情参数、目标和播放逻辑未变。

## 验证

- 85项现有前端回归通过，见tests/frontend.log；生成页面/锁定Mantine一致性通过。
- 两主题、1480×960/1180×820/800×640/390×760，以及1920×1080下125%/150%/175%缩放，196份隔离Electron截图与布局检查通过。使用本机8887替身，不连接正式服务、设备或云端。
- 每组确认网格底部留在面板中、scrollHeight>clientHeight、滚动条占位至少8px，并实际设定滚动位置到末尾检查最后一项整个边界可见；数据保存在tests/layout.json的expressions-bottom记录，首尾截图见tests/companion-expressions*.png，已查看普通桌面、窄屏和175%缩放结果。
- 原标签互斥、目标留白、首排、日志空间、会话输入栏与设置页布局断言保留。定点修复CSS，其他线程已有改动保留。

## 加载与记录

正式8766只读版本为v0.20.14-dev。用户在Gork按Ctrl+R即可加载本轮样式，版本显示须正常重开后为v0.20.15-dev；未退出、重启或替代正式程序。正式用户实屏滚动确认仍待用户查看，隔离渲染不冒充正式验收。

源码/两模块package及lock/后端版本统一v0.20.15-dev；README、AGENTS、当前计划、模块README、CHANGELOG和对应源码包同步，新增details滚动验收经验。备份为Codex-Temp/ui-v02015/baseline；保留脏工作区，无提交/推送。Watch固件和已授权写入的v0.11.7未改，原实屏、听感、T12/T13、BLE备用及长稳门禁保留。
