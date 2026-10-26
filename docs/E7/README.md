# A13 E7：整合验证与收尾

更新日期：2026-10-27。E5：241830088；E6：241870063；E7 原始验证：241830217；整合和课程云主机验证：241830088。

## 已完成

- E6 PR #6 已正式审查并合入 E5 基线；独立原始输入、前后检测、修复哈希与门禁证据均核验通过。
- E5/E6/E7 经整合 PR #7 由 Dufunare 合入 main（`5770c424b3f15e55c2668216c53a7fef7a0fcfbb`），保留阶段历史。
- 整合源码 `a887b574a61524b967f731889ca5523f40684730` 的 [CI Run 40304725572](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40304725572) 与 [PR Run 40304984811](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40304984811) 均成功。
- 同一源码已在本组指定 Ubuntu 云服务器完整执行：**16 项服务测试、17 项独立测试、8 项门禁及原始证据审计通过**；[课程主机证据](../../evidence/E7/241830088/course-20261026/README.md)。环境待办以实际执行关闭，无需假定教师接受 GitHub runner 替代。
- 修正旧 run-manifest 的截断 SHA256；真实 E6 输出的 [B13 候选格式与 Artifact 定位](../E6/B13_AUTOMATED_HANDOFF.md) 已适配并自检，接收确认仍待 B13。

## 当前收尾

2026-10-27 已核实 active main 规则集 25888082：必需检查 `e7-a-quality-gate` / App 15368，strict=true，要求通过 PR；GraphQL `bypassActors.totalCount=0`，没有管理员例外，当前账号不可绕过。

[PR #8](https://github.com/Dufunare/2026-Devops-A13/pull/8) 首次失败源码 `96119b2c69052260b3b4de25532f7f2dae9c875b` 的普通合并已实际被拒（exit=1），且当时不是草稿。[原始拒绝证据](../../evidence/E7/241830088/pr8-rejection-20261027/README.md) 已归档。同一 PR 已将 version 成功返回码预期修正为 0，修复源码9d1712a的PR Run40372248900与push Run40372238651均成功：服务17项、独立17项、门禁8项及原始审计通过。随后普通合并为99cc7e01d4562d2357470ed14585c0d587fb76df；[恢复与最终合并证据](../../evidence/E7/241830088/pr8-recovery-40372248900/README.md) 已归档。

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
- [当前实验提交报告](实验提交报告.md)
- [241830217历史实验报告](实验提交报告_241830217_20261025.md)
- [原始 README](README_241830217_20261025.md)
- [原始 CI 证据索引](../../evidence/E7/241830217/ci-40154562661/README.md)
