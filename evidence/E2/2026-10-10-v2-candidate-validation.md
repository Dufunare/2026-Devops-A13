# Pair13 finding-report v2 candidate 验证记录

日期：2026-10-10

A13 根据 B13 2026-09-29 互审意见新增共同 2.0 候选，并在隔离目录运行语义 validator 与 unit tests。

结果：

```text
PASS contracts/examples/v2/md-report.valid.json
EXPECTED REJECTION empty-evidence.json
EXPECTED REJECTION tool-without-producer-job.json
EXPECTED REJECTION unknown-core-field.json
EXPECTED REJECTION unresolved-with-path.json
EXPECTED REJECTION unsafe-dependency.json
All Pair13 finding-report v2 semantic checks passed.

Ran 8 tests
OK
```

验证范围：

- valid report 可接受；
- UNRESOLVED location 不能夹带 path；
- dependency 不允许 `..` 越界；
- evidence 不能为空；
- 核心未知字段拒绝；
- BUILDCHECKER/ECHECKER 报告必须绑定 producer job；
- finding 内可选 commit/config 若存在必须与顶层一致；
- extensions 必须使用命名空间。

边界：这只是 A13 的 2.0 candidate 自检，不代表 B13 已接受，也不代表真实检测器已产生 2.0 报告。
