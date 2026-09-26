# ADR-001：E2 契约与论文实现边界

状态：PROPOSED

## Context
A13/B13 复现四篇论文，同时 E2 要求统一 Job/Artifact。论文核心若直接依赖 HTTP/Job 细节会强耦合。

## Decision
E2 冻结服务边界 DTO。公共 Job/Artifact 共同确认；A13 定义 FULL_CHECK/INCREMENTAL_CHECK/finding 对外模型。内部模型以后按论文实现，必要时用 adapter 转换。

E2 不要求部署 Scheduler、消息队列或微服务。

## Consequences
论文复现可独立开发，跨组协议稳定；实现阶段需 adapter/serialization 和 contract tests。
