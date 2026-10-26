> 2026-10-26 整合更新：指定课程服务器已用 a887b57 完成 16 项服务、17 项独立及 8 项门禁和原始证据审计，环境问题已通过实际执行关闭；E6 独立证据已审查。下文保留 241830217 原始 CI 报告及当时状态，当前状态以 [整合收尾记录](INTEGRATION_20261026.md) 和 [验收 CSV](验收记录.csv) 为准。

# DevOps E7 论文1验证实验报告

**实验项目：A13 BuildChecker 全量依赖检测验证（A 轨道）**  
**课程：2026 年秋季 DevOps 项目实验**  
**提交人学号：241830217（按分支命名，正式提交前核对）**  
**小组：A13｜分工：E7 测试、CI 与证据复核**  
**报告整理日期：2026-10-25**

> **结果摘要**：基于此前已导入 E5 的 BuildChecker 教学实现，已在 GitHub Actions `ubuntu-24.04` 的 Linux/AMD64 实际执行 Docker 构建、系统调用跟踪、原始/修复/故障场景。服务测试 **15/15**、独立单元测试 **11/11**、E7 八项门禁 **8/8**，证据审计通过。**课程指定云服务器执行环境的合规认可、主分支保护及失败 PR→修复→合并演示尚待确认或补验**，本报告不将其标为通过。

## 1. 实验目标与背景

按 10 月 20 日《E5_论文1复现》《E6_论文1MVP》《E7_论文1验证》及 A 轨道指导，阶段目标分别是：E5 通过系统调用与 Make 依赖声明理解 MD/RD，E6 生成实际/声明依赖图并自动检测，E7 验证正确性、重复性、修复与故障处理，并通过 CI 留存证据与演示合并拦截。

A13 负责 BuildChecker/EChecker；B13 负责 DRAFT/MDFixer。原始 E5 复现由组员 241830088 在 `e5/241830088-reproduction` 完成，其原始证据与来源见 `docs/E5/实验报告.md`、`evidence/E5/241830088/`。本人的 E7 代码基于该 E5 分支，合并点为 `7bbab16407cd387929a72a5680739d5ab1ba4351`，不把 E5 的旧日志重新署名为 E7 实测。

本阶段验证论文“真实依赖与构建声明相比较”的核心思想，**不等于**重跑整篇 TSE/BuildChecker 论文的所有项目、性能数据或复杂多 Make 场景。

## 2. 环境、源码与原始证据

| 项目 | 实际记录 |
|---|---|
| 代码仓库 | `https://github.com/Dufunare/2026-Devops-A13` |
| 工作分支 | `e7/241830217-reproduction` |
| **实际测试源码 SHA** | `76a8f004e61560edc3f1d77a6c51fb2113413cc4` |
| CI 服务/Run | `e7-a-quality-gate` · [Run #40154562661](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661)（结论 SUCCESS） |
| 执行平台 | GitHub-hosted `ubuntu-24.04`，Linux AMD64（**非课程指定云服务器**） |
| Docker 版本 | Engine 28.0.4，API 1.48 |
| 本轮镜像 ID | `sha256:eec09476303ed04737eba511368138e574ec0c21cb534175a4bbdbb8e1ae2103` |
| 基础镜像 | `docker.io/library/python@sha256:f82c96458eedc847b233e582eb31336f4954b39cae020b6dcf5b3ed0e5cbcd74` |
| 原始 Artifact | [e7-a-evidence-40154562661-1](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661/artifacts/12583718152)；ID 12583718152 |
| ZIP SHA256 | `ec06f1e650e0a2117ec18dd7eefd1ebfd236982c235c2945ae7bb371eff0adc6` |
| 长期证据索引 | `evidence/E7/241830217/ci-40154562661/README.md`，含 JSON、CSV、审计结果、哈希索引 |

本轮测试日志和完整原始 trace 来自 Actions 真实产物 `work/ci/`（Artifact 内总计 195 个文件），不是课程材料中教师的预先演示日志。原始 ZIP 的保留策略为 14 天，提交前应另行存档。

CI 的镜像地址在 GitHub 网络中从 E4 的 DaoCloud 代理改用官方 Docker Hub 路径，**固定 OCI digest 不变**；这是环境适配，不代表两台机器的内核/ptrace 配置等价。E5 本组原始课程主机记录见其独立报告。

## 3. 实现与测试方法

### 3.1 使用的教学基线

E5 导入的 `scripts/lab_cloud.py`、`services/buildchecker/buildchecker/fullcheck.py`、`scripts/run_e7_a_gate.py` 与原有 6 项 oracle 测试来自教学材料，归属与原始 SHA256 记录在 `docs/E5/source-manifest.json`。其中基于 `strace -ff` 与 GNU Make 数据库采集读取/声明图，比较 `A - D`（Missing Dependency，MD）与 `D - A`（Redundant Dependency，RD）。

### 3.2 本人 E7 扩展

新增 `scripts/verify_e7_a_evidence.py`，对运行后保存的 `gate-result.json`、`results.csv`、输入 SHA256、`actual-graph.json` / `declared-graph.json`、trace `t.PID` 及 Make 数据库声明行号进行**交叉核查**，并验证原始三次重复输入相同、trace_id 唯一、修复仅改 Makefile。

新增 `tests/e7/test_e7_evidence_audit.py` 的 5 项负例测试：重复 finding、输入篡改、Make 声明错误行号、失败 `openat` 伪造证据、trace 路径穿越。原有独立 oracle 6 项，共 11 项。

新增 `.github/workflows/e7-quality-gate.yml` 将源码扫描、独立测试、镜像构建/扫描、真实 8 场景和事后证据审计串成流水线，并在通过/失败时均归档 Artifact。针对 CI 中发现的非 ASCII 路径误识别，修改 `scripts/secret_scan.py` 使用 NUL 分隔的 `git ls-files -z` 解析路径，保留了原本的密钥检查逻辑。

### 3.3 E7 运行场景与预期结果

| 场景 | 验证行为与判定标准 | 实际工具退出码 | 结果 |
|---|---|---:|---|
| unit-tests | BuildChecker 服务单测 15 项成功 | 0 | PASS |
| original-1 | 检出 MD(main.o,config.h) 与 RD(main.o,unused.h) | 1（按缺陷门禁预期） | PASS |
| original-2 | 与第一次相同的错误集合；独立 trace_id | 1 | PASS |
| original-3 | 与前两次相同的错误集合；独立 trace_id | 1 | PASS |
| fixed | 仅修改 Makefile；`findings=[]` | 0 | PASS |
| build-failed | `FAILED / CHECK_FAILED` | 1（按故障预期） | PASS |
| unsupported | 多输出场景 `FAILED / UNSUPPORTED` | 1（按故障预期） | PASS |
| timeout | `TIMED_OUT / TIMEOUT` | 1（按故障预期） | PASS |

**完整门禁结果：`passed=true`，8/8**。故障用例中工具退出码 1 表示正确拒绝故障，而非 CI Gate 未通过。基于独立审计的三次原始输入 SHA256 一致、7 个 trace_id 唯一；前后修复的哈希差异仅为 `Makefile`，且声明/实际依赖图差分与 findings 一致。

## 4. 执行过程、问题与实际结果

- 初次 CI 确认 11 项独立测试通过，但仓库中带中文路径的 `.env.example` 被旧扫描器的 Git C-style 路径引号误解为已跟踪的 `.env`；改用 `git ls-files -z` 后扫描通过。
- GitHub runner 最初无法通过课程主机使用的 DaoCloud 代理解析固定镜像索引；在 CI `docker build` 时使用 canonical Docker Hub 路径及相同 OCI digest，后续构建/镜像扫描通过；未修改 E4 的固定基线 Dockerfile。
- 在 **2026-10-25** Run #40154562661 上：`pytest` 服务 15 passed、独立 `unittest` 11 tests OK、三次原始、修复及三种故障全部通过、离线原始证据审计 `passed=true`、CI Conclusion **success**、Artifact 上传成功。
- 在本阶段整理提交记录时，移除了原临时 `docs/tmp-references` 教师材料目录；另建立 `课程材料来源索引.md` 保存来源标识与适用范围，避免将教师演示日志误附入个人提交包。
- 不应把文档整理提交 SHA 或 E5 的独立运行 SHA 写作本轮 CI 所执行的源码 SHA；后续若以新 HEAD 重跑，应另存新运行链接与关联 SHA。

## 5. 结果分析与可信度范围

本轮固定教学样例的原始配置中，编译作业确实读取 `config.h`，而 `main.o` 声明缺少它，故为 MD；Makefile 声明了本构建作业未使用的 `unused.h`，故为 RD。仅改 Makefile 的修复副本错误集合为空。该 RD 结论限定于**本次构建配置和观察语义**，不是对所有配置的静态证明。

证据可由 `gate-result.json`、`results.csv`、`findings.json`、声明/实际图与进程 trace 交叉定位。新增离线审计器证明**保存的证据内部可核查**，不能保证 BuildChecker 算法对任意项目都完备，也不能用以取代真实 strace 构建；因此本轮同时运行了真实容器化门禁。

## 6. 尚未完成的教学验收与限制

1. **课程指定云服务器环境合规：PENDING。** 实际运行是 GitHub-hosted Ubuntu 24.04。课程材料指定“在本组云服务器上完成”，而 E7 里程碑的最低证据未单列“CI 之后再重复云主机运行”。是否允许替代，请按 `docs/E7/课程云服务器环境合规确认.md` 向教师/助教确认；如不接受须另行复跑，不能宣称已满足指定主机要求。
2. **main 分支保护与失败→修复→合并演示：PENDING。** 本次 CI success 本身不代表 `main` required status check 已启用或真实 PR 合并被禁止。本组尚需管理员确认规则，并在演示 PR 中保存失败被拒、修复通过及合并记录。
3. **E6 独立交付：需与 E6 负责人另行核对。** 本轮 E7 的 `fixed` 自动测试证明检测与修复场景正确，不等于 E6 所需前/后报告、哈希和运行日志均已以负责人身份单独归档。
4. **论文范围：** 未重跑论文的大规模开源项目数据集、速度指标及复杂递归 Make 场景；本报告是课程教学 MVP 的 E7 验证。

## 7. 复现命令与提交清单

对仓库代码快照（应包含 E5 整合实现）可在 Linux + Docker 环境执行：

```bash
python3 -m unittest discover -s tests/e7 -v
python3 scripts/lab_cloud.py build --image e7-buildchecker:submission --out work/e7-build-submission --build-timeout 1200
python3 scripts/lab_cloud.py gate --image e7-buildchecker:submission --out work/e7-gate-submission
python3 scripts/verify_e7_a_evidence.py --gate-dir work/e7-gate-submission/gate
```

每次使用新 `work/` 目录以保留历史证据，所需 Linux、Docker 和 ptrace 权限由运行者自行保证。

**建议提交附件**：① E7 分支的**工作树源码 ZIP**（不包含 `.git` 与已删除的教师临时目录）；② 本实验报告 PDF；③ 如作业允许，附已核对 SHA256 的 `e7-a-evidence-40154562661.zip`，它包含完整 raw trace 和 CI 原始日志。仓库内另有 `docs/E7/验收记录.csv`、`组内交接与后续安排.md` 和 `evidence/E7/241830217/` 精简索引。

**阶段结论**：E7 教学样例的技术实现与 GitHub CI 八场景验证已通过；指定课程云服务器的环境合规及 PR 实际合并门禁演示仍需补证。已完成与待完成内容均按相应状态如实记录。
