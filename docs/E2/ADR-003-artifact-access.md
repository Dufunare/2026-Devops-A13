# ADR-003：E2 样例 Artifact 使用仓库可读定位

状态：PROPOSED

## Context
`artifact://pair13/<job>/<file>` 是逻辑 URI，不能天然跨机器读取。

## Decision
保留逻辑 URI，同时允许 metadata 增加 `repository_url`、`repository_ref`、`repository_path`。A13 样例提交到 GitHub 仓库。

## Consequences
E2 无需提前部署对象存储，也不依赖本机绝对路径；后续换 Artifact Store 时只替换 resolver。
