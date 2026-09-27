# A13 -> B13 E2 接口交付说明

> 面向配对组 B13。状态：**A13 草案，可用于互审；未决项仍需双方在 Issue/PR 中确认。**

## 1. 交付基线

A13 本次对齐基于 B13 以下固定版本：

- B13 仓库：`ma058/2026-Devops-B13`
- 分支：`main`
- Commit：`af194c40ffd1394fb56cc9f5b2367b7feffb5a3b`
- B13 已合并 PR：#2

A13 阅读并对齐了 B13 的公共 Job/Artifact Schema、FULL_CHECK/INCREMENTAL_CHECK 合成样例、baseline ADR、状态/错误约定和 Artifact 访问草案。B13 的消息也明确说明：这些字段在 A13 留下可追溯确认前仍是草案。

## 2. A13 对 B13 八项问题的逐项回复

### 2.1 公共 Job 字段与状态

**结论：接受。**

A13 接受 B13 当前公共字段：`schema_version`、`job_id`、`trace_id`、`job_type`、`status`、`input`、`output`、`error`，以及创建请求中的 `idempotency_key`。

接受状态枚举：`QUEUED / RUNNING / SUCCEEDED / FAILED / TIMED_OUT / CANCELLED`。

接受语义：

- 检测到 MD/RD 是正常分析结果，Job 仍为 `SUCCEEDED`；
- 构建失败、分析器异常、超时、权限错误属于 `job.error`；
- E2 只定义异步 Job 契约，不要求现在部署 HTTP 服务。

### 2.2 FULL_CHECK 与 INCREMENTAL_CHECK

**结论：接受 B13 总体形状，并补齐 A13 专有字段。**

A13 提供：
- `contracts/examples/full-check.request.json`
- `contracts/examples/full-check.succeeded.json`
- `contracts/examples/incremental-check.request.json`
- `contracts/examples/incremental-check.succeeded.json`
- `contracts/examples/invalid/`

FULL_CHECK 核心输入：
- repository URL + 完整 commit SHA；
- DRAFT/调用方提供的环境；
- `configuration_id`；
- `project_root`；
- `clean_command`；
- `build_command`。

FULL_CHECK 核心输出：
- actual dependency graph Artifact；
- declared dependency graph Artifact；
- error report Artifact；
- findings 摘要。

INCREMENTAL_CHECK 核心输入：
- 新 commit；
- `base_commit`；
- 与 base commit/configuration 匹配的 baseline；
- 构建环境与命令。

核心输出：
- updated actual dependency graph；
- 当前 error report；
- findings delta（added/removed/persisting）。

### 2.3 baseline 策略

**结论：接受 B13 的课程接口方案。**

EChecker 论文允许在缺少历史 actual dependency graph 时执行 clean build 建立历史图；但 E2 课件明确要求“删除 baseline 的增量请求应被拒绝”。

因此课程接口采用：
1. 先 FULL_CHECK 建立 baseline；
2. 再 INCREMENTAL_CHECK；
3. 缺 baseline 直接拒绝；
4. `baseline.commit == base_commit`；
5. `baseline.configuration_id == environment.configuration_id`。

这只是把论文中的基线建立步骤显式拆成 FULL_CHECK，并不否认 EChecker 论文的 fallback。

### 2.4 MD/RD 报告

**结论：提供 A13 报告样例，B13 MDFixer 只消费 MISSING。**

最小 finding 字段：
- `finding_id`
- `type`：`MISSING` 或 `REDUNDANT`
- `target`
- `dependency`
- `commit`
- `configuration_id`
- `location`
- `evidence`

报告样例：`contracts/artifacts/job-full-a13-001/md-report.json`。

路径规则草案：
1. 项目内路径统一为以 `project_root` 为基准的 POSIX 风格相对路径；
2. 去除 `./`，跨组数据不使用调用机绝对路径；
3. A13 报告只包含项目内依赖；系统头文件和项目外第三方文件按项目根路径过滤；
4. 若暂时无法精确定位 Makefile 声明，使用 `location.status = "UNRESOLVED"`，不得伪造行号。

### 2.5 DRAFT 环境要求

**结论：给出最小能力要求；具体容器权限待实现后实测冻结。**

A13 需要 DRAFT 环境满足：
- Linux 用户空间；
- GNU Make；
- 项目要求的编译器/工具链；
- 可执行 clean build 和普通 build；
- 明确 `project_root` 与工作目录；
- 源码与输出目录可写；
- 若实现使用系统调用跟踪，环境必须允许所选跟踪机制。

BuildChecker 论文使用 `ptrace` 跟踪构建文件操作，因此环境必须允许 ptrace 所需权限。常见 Docker 配置可能涉及 `SYS_PTRACE` 和 seccomp；最终 flags 由 A13 真正复现后实测冻结，E2 不虚构唯一参数。

建议 DRAFT 成功结果至少让下游看到：
- `image_ref`；
- 可选 image digest；
- `project_root`；
- `configuration_id`；
- 推荐 clean/build 命令；
- 是否保留编译工具链；
- 跟踪能力/权限说明。

### 2.6 Artifact 读取

**结论：A13 提议 E2 采用“仓库托管样例 Artifact + 逻辑 URI”。**

保留 B13 URI：`artifact://pair13/<producer_job_id>/<filename>`。

为使 URI 可实际读取，A13 在样例 metadata 中额外允许：
- `repository_url`
- `repository_ref`
- `repository_path`

A13 样例提交在 `contracts/artifacts/<producer_job_id>/<filename>`，B13 可以通过 GitHub 读取，不依赖 A13 本机绝对路径。

正式冻结前，希望 B13 也提供至少一份同样可实际读取的 Artifact。共享对象存储/下载端点可留到后续实现。

### 2.7 MDFixer Patch 修复后复检

**结论：A13 接受“base commit + candidate patch”语义。**

MDFixer 生成 patch 时，它还不是正式 Git commit：
1. B13 返回 `patch_uri`，并记录 base commit/configuration；
2. A13 在隔离工作区 checkout 对应 commit；
3. 应用 candidate patch；
4. build/verify；
5. 重新检测；
6. 返回 before/after target MD count、new MD count、build result、base commit、configuration 和 patch identity。

候选通过后，才由项目流程决定是否形成正式 commit/PR。

### 2.8 错误与版本

**结论：接受 B13 区分。**

- MD/RD -> `SUCCEEDED.output.findings`
- 构建失败/分析失败/超时/权限问题 -> `job.error`

版本策略：
- 新增可选字段：允许，但双方样例/validator 同步；
- 删除、改名、改语义、改变状态枚举或必填性：破坏性变化，先在双方可见 Issue/PR 讨论，再升级 Schema 版本；
- 交接记录 Schema 版本与对方契约 commit SHA。

## 3. A13 提供给 B13 的文件

- `contracts/schemas/a13-full-check-input.schema.json`
- `contracts/schemas/a13-incremental-check-input.schema.json`
- `contracts/schemas/a13-finding-report.schema.json`
- `contracts/examples/`
- `contracts/artifacts/`
- `scripts/validate_e2.py`

## 4. 仍需双方确认

1. B13 是否接受 finding/location/evidence 字段；
2. B13 是否接受 repository-backed Artifact locator；
3. DRAFT 最终跟踪权限字段名；
4. MDFixer 是否绑定 patch 到 base commit/configuration；
5. 双方实际互读 Artifact 的证据；
6. 最终冻结 Schema 的 commit SHA。

## 5. 论文语义与课程契约的边界

当前契约不声称已经实现论文工具。

BuildChecker：clean build 中跟踪实际文件执行关系，同时从 GNU Make 内部数据库得到 build declaration，建立 execution-declaration model，根据差异检测 MD/RD。

EChecker：以历史 clean-build actual dependency graph 为基础，结合增量构建跟踪、源码预处理指令变化、文件变化和 Makefile/build-command 变化，推断新 actual graph 并检测错误。

E2 做的是**定义这些未来实现如何与 B13 交接**，不是用合成 JSON 代替论文复现。

## 6. B13 建议回复格式

请逐项回复：接受 / 建议修改 / 尚未决定，并在修改时给出具体字段和 JSON 例子。未决定项进入双方 Backlog，不标记为已冻结。
