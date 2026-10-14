# PC v0.20.6-dev AI配置保存提示与验收

用户截图显示新DeepSeek表单，但后台只读health仍v0.20.3，answer_setup字段不存在。窗口×的close监听preventDefault并hide，托盘“退出”才app.quit并stopOwnedBackend；先前笼统“正常重开”容易只隐藏再打开，后台保留旧版本。Key尚未提交给新保存接口，不能据此判断其有效性。

修复：实际后台没有answer_setup时禁用保存，并说明托盘退出步骤；已知新能力但接口404时保留同一版本提示。控制权/输入/忙态/本机加密失败分别给安全说明，不展示原始异常。保存期间维持禁用，不让健康轮询触发二次提交；缺接口时不清空密码框、不发送Key。

验证：74前端通过，新增真实DOM与控制器验证旧后台0请求且Key仍留本机输入、缺接口提示、轮询不解除保存禁用、404不回显原始错误。3API配置专项通过：既有DPAPI与控制权/格式/忙态/重启恢复。生成一致性与git diff --check通过。后端业务及布局未改，前版165Python/32桌面/32隔离布局为既有基线，不冒充本轮重测。日志见tests/。

源码与PC/桌面元数据v0.20.6，实际后台以tests/public-runtime.json和当次health为准。请右击系统托盘Gork→退出，再启动并确认v0.20.6，在本机重新输入Key保存。未读取用户Key、写真实凭据、发DeepSeek请求、修改网络、烧录、提交或推送。新运行版本、实际保存和真实AI/PTT/听感仍待现场验证；Watch仍v0.11.5。README/两模块README/AGENTS/当前计划/CHANGELOG同步，旧版本超5归档；变更前备份在Codex-Temp/save-v0206/baseline/。
