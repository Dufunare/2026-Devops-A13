# ADR-002：INCREMENTAL_CHECK 显式 baseline

状态：PROPOSED

## Context
EChecker 论文允许无历史图时 clean build；E2 课件要求删除 baseline 的请求被拒绝。

## Decision
INCREMENTAL_CHECK 必须有 baseline；baseline.commit == base_commit；baseline.configuration_id == 当前配置。缺 baseline 时先 FULL_CHECK。

## Consequences
满足课程反例，FULL_CHECK 与增量职责清晰。以后若支持论文式 fallback，需新版本契约。
