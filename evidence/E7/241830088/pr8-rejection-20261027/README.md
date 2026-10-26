# PR #8：实际保护拒绝证据

日期：2026-10-27（Asia/Shanghai）。

失败源码 `96119b2c69052260b3b4de25532f7f2dae9c875b`，失败 PR Run [40339033967](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40339033967)，服务测试为 1 failed, 16 passed；唯一失败是故意写错的 `version` 成功退出码预期。

管理员使用 active Repository Ruleset 25888082 保护 main。必需检查为 e7-a-quality-gate / App 15368，strict=true，必须经 PR。GraphQL 查询返回 bypassActors.totalCount=0，管理员没有例外主体，当前执行账号的 current_user_can_bypass=never。规则集相当于本实验的管理员同受约束；传统 branches/main/protection API 返回 404，不把它误解为没有保护。

将同一 PR 从 draft 转为 ready 后，执行 `gh pr merge 8 --repo Dufunare/2026-Devops-A13 --merge --match-head-commit 96119b2c69052260b3b4de25532f7f2dae9c875b`，退出码 1，提示 base branch policy prohibits the merge。`pr-before.json` 证明不是因 draft 被拒，`pr-after.json` 证明仍 OPEN 且 mergeCommit=null。没有执行 --admin 或 --auto。

原始失败 Artifact ZIP 已另存本机，其 GitHub ID 与 SHA256 见 artifacts.json 和 capture-manifest.json；该早期 capture 的 main_protected_at_capture=false 是配置之前的历史快照，实际拒绝时保护状态以本目录 main-before.json、ruleset.json 和 ruleset-bypass-actors.json 为准。

下一步在同一 PR 将预期修正为 0，等待新提交的 CI 并正常合并；恢复和合并材料需来自其实际执行，不能用本失败运行代替。
