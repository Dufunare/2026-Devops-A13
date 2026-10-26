# A13 E7：整合验证与收尾

更新日期：2026-10-26。E5：241830088；E6：241870063；E7 原始验证：241830217；整合和课程云主机验证：241830088。

## 已完成

- E6 PR #6 已正式审查并合入 E5 基线；独立原始输入、前后检测、修复哈希与门禁证据均核验通过。
- E5/E6/E7 经整合 PR #7 由 Dufunare 合入 main（`5770c424b3f15e55c2668216c53a7fef7a0fcfbb`），保留阶段历史。
- 整合源码 `a887b574a61524b967f731889ca5523f40684730` 的 [CI Run 40304725572](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40304725572) 与 [PR Run 40304984811](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40304984811) 均成功。
- 同一源码已在本组指定 Ubuntu 云服务器完整执行：**16 项服务测试、17 项独立测试、8 项门禁及原始证据审计通过**；[课程主机证据](../../evidence/E7/241830088/course-20261026/README.md)。环境待办以实际执行关闭，无需假定教师接受 GitHub runner 替代。
- 修正旧 run-manifest 的截断 SHA256；真实 E6 输出的 [B13 候选格式与 Artifact 定位](../E6/B13_AUTOMATED_HANDOFF.md) 已适配并自检，接收确认仍待 B13。

## 当前收尾

管理员需将 `e7-a-quality-gate` 设置为 main 必需检查，启用 strict、enforce_admins 和 PR 合并。配置见 [main-protection-required.json](main-protection-required.json)。当前账号没有 admin 权限，不能单方面完成该设置。

独立 `e7/241830088-protected-demo` PR 将保留同一 PR 的故意错误版本预期、失败 CI、普通合并被保护规则拒绝、修复后新 CI 和正常合并记录。在记录真实拒绝之前，相关验收项保持 PENDING；故意错误仅用于课程门禁演示，修复后版本返回码断言应为 0。

## 复跑和接收检查

在 Linux 课程服务器的独立学号目录中，使用新的 out 目录：

```bash
python3 -m unittest discover -s tests/e7 -v
python3 scripts/verify_pair13_delivery.py
python3 scripts/lab_cloud.py build --image e7-buildchecker:recheck --out work/recheck-build --build-timeout 1200
python3 scripts/lab_cloud.py gate --image e7-buildchecker:recheck --out work/recheck-gate
python3 scripts/verify_e7_a_evidence.py --gate-dir work/recheck-gate/gate
```

## 历史与当前状态

241830217 原始源码 `76a8f00` / Run 40154562661 和 `9533f07` / Run 40156221388 的 15/11/8 结果继续作为历史证据保留；新增 E6 和契约测试后的 16/17/8 属于新的整合源码。服务新增故障演示测试后的数量以相应新运行日志为准。

- [整合收尾与实际版本](INTEGRATION_20261026.md)
- [逐项验收 CSV](验收记录.csv)
- [原始实验提交报告](实验提交报告.md)
- [原始 README](README_241830217_20261025.md)
- [原始 CI 证据索引](../../evidence/E7/241830217/ci-40154562661/README.md)
