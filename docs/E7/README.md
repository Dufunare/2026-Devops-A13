# A13 E7：BuildChecker 验证阶段

责任人：241830217。仓库：`Dufunare/2026-Devops-A13`；工作分支：`e7/241830217-reproduction`。

## 固定范围与来源

本组 A13 采用 A 轨道 BuildChecker；E7 的目标是验证 E6 检测 MVP（重复、修复、失败、超时）及 PR/CI 门禁。E5 由组员 241830088 在 `e5/241830088-reproduction` 完成，E7 分支已用合并提交 `7bbab16407cd387929a72a5680739d5ab1ba4351` 导入其实现、原始证据和来源记录。

权威材料：`docs/tmp-references/DevOps_20261020_Course/README_文件用途与使用顺序.md`；E7 PPT；`02_学生实验/.../labs/A-buildchecker/` 参考程序；`02_学生实验/.../docs/02_A轨道操作指南.md`、`04_GitHub_CI与合并门禁.md`、`05_验收清单.md`。03_验收与实验记录是教师示范与备课证据，**不得标为 A13 E7 的运行结果**。

教学代码来源于材料包；新增的 `verify_e7_a_evidence.py` 和 `test_e7_evidence_audit.py` 是针对数据来源、原始 trace 与篡改的独立扩展校验。没有宣称完整复现 TSE 论文的 30 项目或性能数据。

## E7 场景预言（工具返回 1 可作为预期故障场景 PASS）

| 场景 | 预期探测状态 | 工具退出码 | 验证标准 |
| --- | --- | ---: | --- |
| unit-tests | 测试通过 | 0 | 教学服务测试全部通过（参考包为 15） |
| original-1/2/3 | SUCCEEDED | 1 | 每次恰好 MISSING(main.o,config.h)、REDUNDANT(main.o,unused.h)；相同输入；不同 trace_id |
| fixed | SUCCEEDED | 0 | findings=[]；与原始输入比只有 Makefile 哈希变化 |
| build-failed | FAILED | 1 | error_code=CHECK_FAILED 且 build_exit_code 非零 |
| unsupported | FAILED | 1 | 构建成功，error_code=UNSUPPORTED |
| timeout | TIMED_OUT | 1 | error_code=TIMEOUT |

**整体验收需 8 项 passed=true、gate exit=0**。单独的 6 项教学预言测试外，新增 5 项离线防篡改测试；完整单元测试应为 11 项。

## 本地/CI 可直接执行（无需课程云服务器）

```bash
python3 -m unittest discover -s tests/e7 -v
python3 -m compileall -q services/buildchecker/buildchecker scripts tests/e7
python3 scripts/secret_scan.py . --history
```

当真实 E7 gate 运行完成并保存结果时，可额外执行（**不重跑 Docker**）：

```bash
python3 scripts/verify_e7_a_evidence.py --gate-dir work/e7-01/gate
```

该审计器会核查原始输入副本 SHA256、三次一致性、不同 trace_id、声明图与实际图差分、finding 证据中的 trace 文件/行号及 Make 数据库行号、CSV/JSON 对应关系。仅使用教师包历史报告进行演示或只运行这条离线命令，**不能替代**本组实际构建、故障注入及原始日志采集。

## 云服务器补验命令

在有 Docker 和 ptrace 权限的 A13 Linux 服务器、**独立工作副本和干净工作区**上，固定本分支的待验证提交：

```bash
git switch e7/241830217-reproduction
git pull --ff-only
git rev-parse HEAD
python3 scripts/lab_cloud.py doctor
python3 scripts/lab_cloud.py build --image course1020-buildchecker:241830217-e7 --out work/e7-build-01 --build-timeout 1200
python3 -m unittest discover -s tests/e7 -v
python3 scripts/lab_cloud.py gate --image course1020-buildchecker:241830217-e7 --out work/e7-01
echo "E7_GATE_EXIT_CODE=$?"
python3 scripts/verify_e7_a_evidence.py --gate-dir work/e7-01/gate
```

成功条件：`E7_GATE_EXIT_CODE=0`；`work/e7-01/gate/gate-result.json` 里 8 项 `passed=true`，`results.csv` 一一对应，审计器退出 0；保留每个场景的 `fixture/`、`evidence/`、`stdout.log`、`stderr.log`、`command.json`、trace 等原始文件。命令**尚未在本组课程云服务器执行**，因此不能预填成功。

E5/E6/E7 使用自己的 `--out` 新目录，不覆盖既有 E5 `evidence/E5/241830088` 或他人 `work/`。校验可见资源是否符合已有 E4 环境适配（最低 3.5 GiB 与原教师建议 4 GiB 有差异）。失败先归档日志，再分析。

## GitHub CI 与合并门禁

`.github/workflows/e7-quality-gate.yml` 设定 `e7-a-quality-gate`，在 push/PR 执行离线测试、密钥检查、镜像构建、服务测试与真实 E7 gate，再复核原始证据；`if: always()` 归档 `work/ci/` 14 天，包括 `commit.txt`。GitHub-hosted Ubuntu 24.04 runner 本身是 CI 环境，**不等于课程云服务器独立复跑**。如仓库策略要求使用自建 runner，应在 CI 成功基线后单独验证权限与容器隔离再调整。

只有成功的标准 PR 检查已出现后，才将 `e7-a-quality-gate` 设置为 `main` 的 required check、`strict=true`、`enforce_admins=true`。**不要直接套用教师的 app_id=15368**：先从本仓库实际 check-run 核对 ID。分支保护可能需要仓库管理员手动操作，后续必须真实演示：错误预言 PR → 失败检查、OPEN/BLOCKED、正常 merge 被拒 → 同一 PR 修正预言 → 最新检查通过 → 合并。教师示范 run ID/PR 不得登记为本组记录。

**注意**：本组先前 E3/E4 合作交付及 E5 源码有自己固定的来源 SHA；E7 结果必须再记录本次触发提交 SHA、image ID、GitHub run ID、运行证据目录，避免将不同阶段混为一份证据。

## 当前状态

- 已完成：课程材料筛选、E5 实现与证据整合、E7 参考 gate 纳入分支、独立原始证据离线审计器及 5 项新增测试、CI workflow。
- 已验证：首个 GitHub CI 提交 `d4780c0` 中 11 项离线 oracle/audit 测试通过；当次源代码扫描由于 Git 路径 C-style 引号导致误把参考 `.env.example` 识别为 `.env`，已修复扫描器的 NUL 路径处理，**更新后完整 CI 仍待验证**。
- 待验证：最新 CI 镜像与实际 8 场景、真实 A13 课程云服务器、失败/修复 PR、管理员 main 保护策略。无真实数据前统一记录 **PENDING**，绝不写 PASS。

本轮新增代码与决策记录在 [AI 使用说明](AI_USAGE.md)；最终结果与云端行动见 [待办清单](云端与验收待办.md)。
