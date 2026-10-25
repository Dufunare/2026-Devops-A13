# A 轨道教学样例：CI 与合并门禁闭环完成

2026-10-15 已核对本地保存的云端测试报告、断言失败日志、保护配置及合并记录。仓库 Scout7666/DevOps 经用户同意改为公开。

- 主要实现 PR #1：https://github.com/Scout7666/DevOps/pull/1，已合并；合并提交 87e590e22bcbd9741e7f4f440e38e2e46da26ecc。
- 首次成功运行：38681967450；云端执行语法检查、独立 oracle 单元测试、源文件和历史扫描、镜像构建、镜像扫描与真实组件门禁。
- main 保护：GitHub Actions app_id 15368 的 e7-a-quality-gate 必须通过；strict 和 enforce_admins 均 true；单账号教学演示 required_approvals 为 0。
- 故意失败 PR #2：https://github.com/Scout7666/DevOps/pull/2；提交 fb6625d4047ecf75ae97b2b5f7779f82c168b665；失败运行 38683420506。下载的 gate/unit-tests/stdout.log 确认 test_intentionally_wrong_version_exit_code 失败，assert 0 == 1，结果为 1 failed / 15 passed。
- PR 为 OPEN / BLOCKED；普通合并实际被主分支策略拒绝，命令退出码为 1，日志保存在 pr-2-rejection/E7-A-merge-rejection.log。
- 修正同一 PR：提交 10e43880d2fa61b3a5cce616adb807ec486bf0f6；成功运行 38683694031；下载报告确认服务测试 16 passed，门禁 passed=true，全部八项检查通过（服务单元测试一项及七个真实构建/检测场景）。
- 七个真实场景：原始缺陷样例重复三次、修复样例、构建失败、不支持输入、超时。预期缺陷与故障案例的工具退出码为 1，测试正确识别它们后，整体门禁通过。
- PR #2 已合并，合并提交 cb08ff6ec194c6ffaa363e335ba5b2396cbc2bc0；合并记录时间 2026-10-15T05:02:12Z（北京时间 13:02:12）。

16 个服务测试包含一项修复后的门禁演示测试。这里修复的是故意写错的测试预期，算法实现没有改变，不能称为发现并修复真实算法缺陷。

证据目录：run-38681967450、pr-2-rejection、pr-2-recovery、A-main-protection.json、A-PR1-merged.json。

验证范围是小型明确的教学样例与受限的 BuildChecker 教学实现，不代表原论文的完整工具或全量项目基准。以上核对基于本地备份和用户提供的终端输出，本次未重新运行云端实验。
