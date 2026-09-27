# A13 E2 内部说明：我们做了什么、为什么做、后面还要做什么

> 给还没有开始 E2/论文复现的 A13 成员。读完后应能理解整个实验、A13 的位置、本次仓库产物和下一步。

## 1. 整个实验是什么

四篇论文组成：

```text
DRAFT (B13)
  -> BuildChecker (A13)
  -> EChecker (A13)
  -> MDFixer (B13)
  -> build/test/recheck
```

- DRAFT：为 repository/commit 生成可构建环境；
- BuildChecker：完整构建分析，得到 actual/declaration graph 和 MD/RD；
- EChecker：跨 commit 增量更新 actual graph 并持续检测；
- MDFixer：消费 MISSING 报告并生成 Makefile patch；
- 最后重构建、测试和重检，决定 patch 是否接受。

## 2. A13 两篇论文的关系

### BuildChecker

论文建立 execution-declaration model：
- execution：实际构建中进程读/写/生成了什么；
- declaration：GNU Make 解析后的 target-prerequisite；
- actual 有、declaration 无 -> MD；
- declaration 有、actual 无 -> RD。

它通过 clean build 建立较完整基线。

### EChecker

每个 commit 都 clean build 成本高，所以它：
- 保存历史 actual graph；
- 跟踪 incremental build；
- 分析 `#include` 等源码变化；
- 分析文件新增/删除；
- 比较 Makefile/build command 变化；
- 更新历史 actual graph；
- 再与 declared graph 比较。

正常历史：

```text
BuildChecker(C0) -> baseline(C0)
EChecker(C0 -> C1) -> baseline(C1)
EChecker(C1 -> C2) -> baseline(C2)
```

BuildChecker 不是永远只跑一次：baseline 丢失、配置/环境不兼容变化或需要全量校准时仍可重跑。

## 3. E2 是什么

E2 **不是**现在完成全部论文算法。

E2 是集成前的接口契约阶段：
- 四类 Job 怎么表示；
- A/B 互相交什么；
- 输出是什么；
- Artifact 怎样读取；
- baseline 如何绑定 commit/config；
- finding 和系统失败如何区分；
- 正反例如何验证；
- ADR、AI 使用和个人贡献如何追踪。

所以当前 JSON 是**合成契约样例**，不是 BuildChecker/EChecker 的真实运行结果。

## 4. 本次已经完成的设计工作

1. 固定并审查 B13 `af194c40ffd1394fb56cc9f5b2367b7feffb5a3b`；
2. 接受 B13 公共 Job/状态语义；
3. 给出 FULL_CHECK 输入输出；
4. 给出 INCREMENTAL_CHECK baseline、输入输出和反例；
5. 定义 A13 finding report（MD/RD + commit/config + location/evidence）；
6. 明确只报告项目内依赖，过滤系统/项目外路径；
7. 明确 DRAFT 环境需支持 Linux/toolchain/clean build/跟踪能力；
8. 将 Artifact 从“逻辑 URI”推进到可由 GitHub 仓库实际读取的样例；
9. 定义 `base_commit + candidate patch` 复检语义；
10. 提供 validator、tests、Backlog、ADR、AI_USAGE、pair-review 模板。

## 5. 这些文件有什么用

### contracts/schemas
A13 对 FULL_CHECK、INCREMENTAL_CHECK 和 finding 的字段契约。

### contracts/examples
有效/无效 JSON。用于双方逐字段互审，也作为以后 API contract test fixture。

### contracts/artifacts
实际提交到仓库的合成 Artifact，解决“只有 artifact:// 字符串却无法读取”的问题。

### scripts/validate_e2.py + tests
只检查契约语义，不运行论文算法。验证 baseline/config 等关键约束。

### B13_DELIVERY.md
直接发给 B13 的交付与八项回复。

### PAIR_REVIEW.md
双方真正交流后登记结论。没有对方确认不能写“已冻结”。

### ADR
解释为什么这样设计，不只是留一堆 JSON。

### AI_USAGE.md
记录 AI 建议、人类判断和仍需真实实验验证的部分。

## 6. 现在还没有做什么

- BuildChecker 没有因为这些 JSON 就被复现；
- EChecker 没有真正运行；
- ptrace 的 Docker 权限尚未实测；
- B13 尚未正式确认 A13 新字段；
- Artifact 双向互读还需 B13 回传真实样例；
- MDFixer patch -> A13 recheck 尚未端到端运行；
- 每位成员还需自己的真实 commit/PR/review。

## 7. 后续工作包

### A：BuildChecker
1. clean build；
2. 文件访问/进程跟踪；
3. new file relation；
4. GNU Make database；
5. execution-declaration model；
6. MD/RD verification；
7. 导出契约 Artifact。

### B：EChecker
1. historical actual graph；
2. incremental tracing；
3. commit diff；
4. include/source changes；
5. Makefile/build-command changes；
6. graph update；
7. MD/RD + delta；
8. 新 baseline。

### C：跨组联调
DRAFT environment -> A13 detector -> B13 MDFixer -> patch -> A13 recheck。

### D：DevOps/质量
Contract tests、Issue/PR、CI、日志、ADR、AI_USAGE、CONTRIBUTIONS。

## 8. 最小数据流

```text
B13 DRAFT
  -> environment
A13 FULL_CHECK
  -> actual + declared + MD/RD
A13 INCREMENTAL_CHECK
  -> updated graph + changed findings
B13 REPAIR
  -> candidate patch
A13 recheck
  -> decide whether MD disappeared / new MD appeared
```

## 9. E2 完成判据

1. 双方能解释同一份 Job；
2. 双方都能实际读取对方 Artifact；
3. valid 请求通过；
4. 缺 baseline 等 invalid 请求拒绝；
5. MD finding 与系统失败不混淆；
6. baseline 绑定完整 commit + configuration；
7. 设计与个人贡献可追溯。
