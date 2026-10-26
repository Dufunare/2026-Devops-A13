# A13 → B13：真实 E6 结果的候选格式交接

日期：2026-10-26。状态：A13 已生成并自检；共同格式及接收结论仍待 B13 确认。

## 固定来源

- 原始检测代码：`202555aea6092d0e54105403f4402baa9e3c40ec`。
- 独立 E6 原始证据提交：`694d6cb2961698437cf8de581afcee515eb293b7`，PR #6 已审查并合入 E5 基线。
- 来源目录：`evidence/E6/241870063/e6-before/` 和 `e6-after/`。本次输出来自真实课程云主机 CLI 执行及其完整 trace。
- 适配目标：仓库内共同 2.0 **候选** Schema；本次没有单方面将其标记 frozen。

## 交付文件

| 内容 | 仓库相对路径 |
| --- | --- |
| 运行上下文 | `contracts/artifacts/e6-241870063/export-context.json` |
| 修复前候选报告 | `contracts/artifacts/e6-241870063/before/report-v2.json` |
| 修复后候选报告 | `contracts/artifacts/e6-241870063/after/report-v2.json` |
| 两次生产者/Artifact 注册 | 各自目录的 `producer-registration.json` |
| 文件校验清单 | `contracts/artifacts/e6-241870063/SHA256SUMS.json` |
| 可重复执行的适配器 | `scripts/export_pair13_report.py` |
| 接收方可运行的只读检查 | `python3 scripts/verify_pair13_delivery.py` |

修复前报告含 MISSING(main.o, config.h) 和 REDUNDANT(main.o, unused.h)，修复后 findings 为空。声明位置来自输入 Makefile 第 6 行；原始 trace 与 Make 数据库证据保留实际文件、行号及内容。

## 身份和定位语义

本次把已有的真实 CLI `trace_id` 注册为 `job-cli-<trace_id>`，并持久化对应的原始报告及 Artifact 映射。该 ID 用于静态证据生产者追踪；注册文件明确 `http_job_api_deployed=false`，不宣称已有可查询的异步 HTTP Job 服务。

每个 Artifact URI 都有不可变的源仓库 commit、相对路径和 SHA256。报告中的 artifact_locator 指向原始 CLI findings.json；适配后 JSON 的身份由交接提交及本目录 SHA256SUMS 标识。接收方应固定本文件所在的完整交接 commit，并先运行校验。

`repository.commit` 表示基线 Git 源码版本。修复后 Makefile 位于独立输入副本，其实际内容由 `a13.input_sha256` 和原始证据定位；不把修复副本误称为已提交的 Git commit。

configuration_id `a13-e6-md-rd-linux-amd64-gcc14` 是 A13 为本次真实环境登记的候选标识，修复前后相同。环境版本与镜像 ID 取自 E6 构建记录，后续若 B13 需要统一命名规则，应经双方确认后版本化调整。

## B13 接收和后续复检

1. 固定交接 commit，执行 `python3 scripts/verify_pair13_delivery.py`；它逐文件校验输出，并从固定源 Git commit 读取原始 Artifact 验证哈希和 URI 注册。
2. 仅将 MISSING 送入 MDFixer；REDUNDANT 保留在报告中，修复后空集合按无待修复项处理。
3. 请 B13 确认共同候选字段、CLI 生产者注册语义和 Artifact 读取路径，保存其独立消费验证结果后再共同冻结格式。
4. 候选补丁交接仍应绑定 repository/base commit、configuration、patch hash；A13 再在隔离副本中应用并构建、重检。当前教学入口提供固定样例的修复复检；通用 HTTP Job 和通用 patch recheck 服务属于后续平台实现。

本次适配、自检及公开材料不等同于 B13 已接受，也不以 synthetic E2 示例替代真实 E6 原始报告。
