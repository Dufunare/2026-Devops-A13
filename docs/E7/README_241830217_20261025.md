# A13 E7：BuildChecker 论文1验证

负责分工：241830217 · 工作分支：`e7/241830217-reproduction` · 状态：**E7 技术/CI PASS，环境合规与 PR 实际合并门禁 PENDING**。

## 本阶段事实

E5 的基础复现由组员 241830088 完成（`docs/E5/实验报告.md`），E7 分支通过合并提交 `7bbab16` 纳入检测参考实现与原始证据。E7 在此基础上保留教学源代码中的 8 项门禁及 6 项 oracle，并新增 5 项离线负例测试、原始证据审核、CI 工作流和安全扫描/镜像源适配。

**真实运行**：提交 `76a8f004e61560edc3f1d77a6c51fb2113413cc4` 的 [GitHub Actions Run #40154562661](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661) 通过。服务 `15 passed`、独立 `11 tests OK`、八个门禁场景全部 `passed=true`，全部原始证据内部核查 PASS（重复 3 次，7 个不同 trace_id，仅 `Makefile` 在修复副本中变化）。镜像 ID 为 `sha256:eec09476303ed04737eba511368138e574ec0c21cb534175a4bbdbb8e1ae2103`。

- **原始 ZIP**：[Artifact 12583718152](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661/artifacts/12583718152)，SHA256 `ec06f1e650e0a2117ec18dd7eefd1ebfd236982c235c2945ae7bb371eff0adc6`，含 195 个原始文件（14 天保留）。
- **仓库证据快照**：`evidence/E7/241830217/ci-40154562661/`，含原始 `gate-result.json` / `results.csv`、审计日志及哈希索引。
- **提交报告**：[实验提交报告](实验提交报告.md)；**组内对接**：[组内交接与后续安排](组内交接与后续安排.md)；**逐项验收**：[验收记录](验收记录.csv)。

## E7 八场景

| 检查 | 状态 | 预期工具退出码 | 结果 |
|---|---|---:|---|
| 服务单测 | 全通过 | 0 | PASS |
| original-1 / -2 / -3 | 同样 MD(main.o,config.h)、RD(main.o,unused.h) | 每次 1 | 3/3 PASS |
| fixed | 仅修改 Makefile、findings=[] | 0 | PASS |
| build-failed | FAILED / CHECK_FAILED | 1 | PASS |
| unsupported | FAILED / UNSUPPORTED | 1 | PASS |
| timeout | TIMED_OUT / TIMEOUT | 1 | PASS |

失败输入的工具退出码 1 是正确识别缺陷/故障的**预期行为**；完整 `gate-result.passed=true` 才表示整个门禁通过。

## 如何检查（可离线测试或在 Linux Docker 环境复跑）

```bash
python3 -m unittest discover -s tests/e7 -v
python3 scripts/secret_scan.py . --history
python3 scripts/lab_cloud.py build --image e7-buildchecker:recheck --out work/recheck-build --build-timeout 1200
python3 scripts/lab_cloud.py gate --image e7-buildchecker:recheck --out work/recheck-gate
python3 scripts/verify_e7_a_evidence.py --gate-dir work/recheck-gate/gate
```

输出目录必须新建；程序需要 Linux、Docker、`SYS_PTRACE` 等权限。最后一项是对**已完成的真实门禁证据**的离线核验，不替代实际 strace 构建。GitHub Actions 已保存完整运行，可以按来源 SHA 和 Artifact 核查，不要用教师旧日志代替。

## 当前还缺什么

1. **主分支保护/失败—恢复 PR 演示**：`e7-a-quality-gate` 成功不代表已在 `main` 配为 required check。应由管理员核对 App ID 15368、strict/enforce_admins=true，记录本组真实失败 PR 被拒和修复后合并。现在 **PENDING**，参见 [待办](云端与验收待办.md)。
2. **课程云服务器合规确认**：学生包写明在本组 Ubuntu 云服务器完成，而本轮真实运行位于 GitHub-hosted Ubuntu。课程最低里程碑仅写“单元测试、CI门禁、结果数据”；是否能替代授课指定云服务器，必须由授课方决定。详见 [环境合规确认](课程云服务器环境合规确认.md)。本轮没有自己在课程云主机运行 E7。
3. **E6 独立完成证据**：E7 的固定修复场景可验证检测结果，但不能替代 E6 负责人所需的独立前后报告及说明；与 E6 组员对齐。
4. **论文范围限制**：教学单 Make 单输出任务小样例，不宣称复现 TSE 论文大规模性能/数据实验。

## 资料清理与身份区分

此次从工作树删除 `docs/tmp-references/` 临时教师资料和大量教师示范日志。课程源材料的逻辑路径、关键 blob SHA 与适用范围留在 [课程材料来源索引](课程材料来源索引.md)；E5 自身的运行证据不受影响。Git 历史未重写，所以不要把含 `.git` 的全历史克隆当作精简源码压缩包。

**注意：** CI 的实际运行源码 SHA 为 `76a8f004e61560edc3f1d77a6c51fb2113413cc4`；删除临时目录与更新文档后的 E7 分支 HEAD 会更新，但不会自动倒写先前真实运行身份。需要从新 HEAD 验证时应另存新的 CI Run 和 SHA。
