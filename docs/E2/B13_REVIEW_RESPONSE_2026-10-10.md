# A13 对 B13 2026-09-29 E2 互审回复

状态：**A13 已处理 B13 回复；共同 2.0 Schema 仍为 PROPOSED，不标记 frozen。**

## 基线

- B13 E2/E3 基线：`f0a93bf34518d7cab9a464854e71cca4852f1452`
- A13 被 B13 固定读取的 E2 基线：`bc1ed352dc0b8ff9e77a69222a69deb03e49a618`
- B13 已对 A13 synthetic artifacts 完成 16/16 互操作验证。

A13 不再把旧 B13 `af194c40...` 当作当前对齐基线；旧文档保留为历史记录。

## 八项回复

| 项目 | A13 对 B13 2026-09-29 回复的处理 |
|---|---|
| 公共 Job/状态 | 接受 |
| FULL_CHECK / INCREMENTAL_CHECK | 接受 |
| baseline | 接受：课程接口显式 baseline；缺失/commit/config mismatch 均拒绝 |
| MD/RD report | 接受进入共同 2.0 候选，不修改历史 1.0 evidence |
| DRAFT 环境 | 接受能力要求；E4 已实际采用 Linux + GNU Make/toolchain + SYS_PTRACE |
| Artifact | 接受 repository-backed locator；最终冻结要求固定 commit/path/SHA-256 |
| Patch recheck | 接受 base commit + configuration + candidate patch |
| 错误/版本 | 接受；破坏性变化升级版本 |

## finding report 2.0 候选

新增：

- `contracts/schemas/pair13-finding-report-v2.schema.json`
- `contracts/examples/v2/`
- `scripts/validate_e2_v2.py`
- `tests/test_e2_v2_contracts.py`

候选采纳 B13 建议：

- 顶层增加 `report_id`、`environment`、`detector`、`provenance`；
- `producer_job_id` 仅真实 BUILDCHECKER/ECHECKER 报告要求；
- `location` 使用条件结构：
  - RESOLVED => path + line；
  - UNRESOLVED => reason，禁止伪造 path/line；
- `evidence` 为至少一个结构化对象，每项要求 `kind` + `detail`；
- 核心对象关闭任意额外字段；
- 扩展只能放在 namespaced `extensions`；
- finding 内 commit/configuration 改为可选；存在时必须等于顶层；
- 共同 2.0 不使用重复的 `makefile_path`；
- `artifact_locator` 正式化为可选结构。

A13 额外保留 `A13_MANUAL_ORACLE`，用于 A13 自建人工样例；它与 `INSTRUCTOR_ORACLE`、`B13_MANUAL_ORACLE` 区分来源。

## v1 历史兼容

A13 不修改 `bc1ed352...` 的 v1 synthetic artifacts，也不修改 B13 2026-09-29 的 16/16 evidence。否则会破坏已经存在的可追溯记录。

后续 consumer 若读取 v1，应通过 adapter 归一化到 v2 语义；共同新生产格式再使用 2.0。

## A13 对 B13 REPAIR 的读取结论

A13 已按固定 B13 `f0a93bf...` 读取：

- `contracts/examples/repair.request.json`
- `repair.succeeded.json`
- `repair.succeeded-no-valid-candidate.json`
- `repair.succeeded-not-applicable.json`
- `contracts/examples/md-report.json`

语义与双方先前决定一致：

- MDFixer 只消费 MISSING；
- REDUNDANT 可 skipped；
- 没有 MISSING => `SUCCEEDED + NOT_APPLICABLE`；
- 无有效候选 => `SUCCEEDED + NO_VALID_CANDIDATE`；
- 成功 => `SUCCEEDED + PATCH_ACCEPTED` 且有 patch_uri；
- patch 绑定 repository/base commit 与 configuration，并由 A13 后续隔离重检。

B13 当前 main 的 md-report Schema 仍是自己的 1.0 格式，因此本次新增的 Pair13 2.0 只作为共同冻结候选，不宣称 B13 已经迁移。

## 冻结条件

只有同时满足以下条件，才把 2.0 标记 frozen：

1. B13 接受本次 A13 v2 candidate 或提出明确 diff；
2. 双方各自在独立 commit 更新 Schema、valid/invalid fixtures、validator/tests；
3. 双方交换完整 commit SHA；
4. B13 读取 A13 v2 report；A13 读取 B13 v2 REPAIR/report；
5. 双方记录文件 SHA-256；
6. 两边文档写入同一组固定 commit。
