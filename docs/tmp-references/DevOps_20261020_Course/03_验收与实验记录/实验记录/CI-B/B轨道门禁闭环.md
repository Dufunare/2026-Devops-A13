# B 轨道教学样例：CI 与合并门禁闭环完成

2026-10-14 已核验本地测试、云端 CI、必需检查、实际拒绝合并、同一 PR 修正后恢复通过及正常合并。

- 主要实现 PR #1：https://github.com/Scout7666/devops-20261020-draft/pull/1，已合并。
- 云端首次故障：run 38564298680，构建服务禁网导致注册表认证失败；证据已保存。
- 修正后成功：run 38565118826，提交 fbdcb1aa5149dc1182e011d43ac0b2e11f94bcd0，五组场景全部 PASS。
- main 保护：GitHub Actions app_id 15368 的 e7-b-quality-gate 必须通过；strict 和 enforce_admins 均 true；单账号演示 required_approvals 为 0。
- 故意失败 PR #2：https://github.com/Scout7666/devops-20261020-draft/pull/2。提交 40d7112853e5f12d58a802cb448948de3d850f7f；run 38567115233 失败，1 failed / 24 passed；PR 为 BLOCKED；普通合并命令实际被策略拒绝。
- 修正同一 PR：提交 257fbee52369704f331cf81b5d33efed09b8810d；run 38580500838 成功，25 passed；PR 恢复 clean。
- PR #2 已合并，最终 main 合并提交 e60afef8729bc71ce574abdf3db33f95d0e6c437。合并时间为用户终端与 GitHub API 确认的 2026-10-14T14:33:37Z。

25 项中包含一项专门用于门禁演示的测试。该演示是修正故意错误的测试 oracle，算法实现未改变；不能作为真实算法缺陷修复或额外论文实验成果。

证据在 run-38564298680、run-38565118826、pr-2-rejection、pr-2-recovery 及 main-protection.json。候选来自人工 DeepSeek 回复回放，验证范围为明确的教学样例，不声称全自动模型生成或完整论文基准复现。
