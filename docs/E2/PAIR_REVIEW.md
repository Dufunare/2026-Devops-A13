# A13 <-> B13 Pair Review

状态（2026-11-16）：**finding-report 2.0 固定版本已获双方确认；A13 登记 FROZEN_FIXED_PAIR。B13 待回填本次归档提交。**

## 历史基线

- A13 E2 合并：`bc1ed352dc0b8ff9e77a69222a69deb03e49a618`（PR #2）
- B13 E2/E3 当前固定基线：`f0a93bf34518d7cab9a464854e71cca4852f1452`
- 旧 B13 `af194c40...` 仅作为 A13 最初起草 E2 时的历史基线，不再用于当前冻结判断。

## 已确认

| 主题 | Pair13 当前结论 |
|---|---|
| 公共 Job 字段/状态 | 双方接受 |
| FULL_CHECK | 双方接受总体输入输出 |
| INCREMENTAL baseline | 双方接受先 FULL_CHECK，再显式 baseline incremental |
| Artifact | 双方接受 repository-backed locator |
| Patch recheck | 双方接受 base commit + configuration + candidate patch |
| 错误边界 | findings 属于 SUCCEEDED；系统执行错误进入 error |

## 已有互读证据

B13 已从 A13 `bc1ed352...` 固定并读取 5 份 synthetic Artifact + 1 份 Schema，并完成 16/16 检查；结果保存在 B13 `evidence/E3/2026-09-29-a13-interop/`。

这些证据只证明 E2 格式和消费链路，不声称真实 BuildChecker/EChecker 已运行。

A13 现在也已按 B13 固定提交 `f0a93bf...` 阅读 REPAIR request/result、MD report 和 pair-review 约定；处理记录见 `B13_REVIEW_RESPONSE_2026-10-10.md`。

## 候选阶段历史与最终确认

B13 2026-09-29 提议共同 finding-report 2.0。A13 已提供 v2 candidate，但仍需 B13 对新版本本身做互读。

- [x] A13 处理 B13 2026-09-29 回复
- [x] A13 新增 v2 Schema/fixtures/validator/tests
- [x] B13 确认 A13 v2 candidate
- [x] B13 产生/迁移自己的 v2 样例
- [x] A13 读取 B13 v2 样例
- [x] 双方记录 SHA-256 与固定 commit
- [x] 双方确认同一固定版本；A13登记冻结，B13待回填本次归档提交

## 2026-11-16 固定版本冻结

A13实际互读代码931563895a40df91a326cac5791e089d767e49a7 / B13代码与样例1d7f4839eff567aa7037d431df86952f24076c4d。A13校验器SHA256为20ae9007cd184404ceb07080222d5af91dbb49d35805019e07d91e2ea56a4023，Schema不变。B13原文确认已接收并复算，见evidence/coordination/20261116/B13_V2_ACK_20261116.md；其公开归档版本为e3bc9a9105b508636945ff250ae57a336c2b07b4（B13 PR #33）。

A读B的19份原件、B重跑A的16项单测、B反向读A的6样例均有固定记录。机器登记见contracts/pair13-finding-report-v2.freeze.json；新文档head只归档确认，不取代上述实际执行版本。B13当前文档为B13_ACK_FIXED_PAIR，待收到A13本次归档提交后回填，不冒称双方仓库文档已同时更新。历史修复前12/19及原件保持原样。

范围仅为E2报告契约；新镜像三包消费、跨机HTTP、真实项目和DRAFT候选跨宿主导入分别验收。
