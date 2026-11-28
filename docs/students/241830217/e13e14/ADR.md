# ADR — E13–E14 成员 C 决策记录（2026-11-28）

| 决策 | 备选/问题 | 选择与依据 | 后果与边界 |
|---|---|---|---|
| C-01 实际 DRAFT 执行 | 宿主执行或各角色任意访问 Docker | DRAFT 独占 socket，Job 绑定桥复用 B 的执行/验证器，记录实际镜像与子容器 | 不扩大角色权限；不支持的项目契约停止，不冒充镜像执行 |
| C-02 Compose 隔离与恢复 | 长构建阻塞健康、全局清理 | 并发 health、逐角色锁、分项目/owner 标签、超时 kill/rm、连续性与单服务门禁 | PR28 控制样例同容器连续；B13 换栈非同容器恢复 |
| C-03 固定原件、不重放写请求 | 猜报告 SHA、重序列化、自动重试污染取证 | 同 Job 原始 graph/findings、profile pin；失败先对账、新任务用新身份 | 人工交接；C4 首次本地原件缺失如实记录 |
| C-04 C5 强制暂停 | 正确补丁覆盖坏补丁后的状态 | POST5 后暂停，五字段清单+27 原件、源码/Git、stderr、执行/cleanup、响应 pin 全通过才 recover | 初版多字段重交，不放松 schema、不重跑 |
| C-05 C8 幂等与修复范围 | 只看 202/409、或强制全项目清零 | 验证 202/202/409/202、全下载与六执行，冻结 toml.o，范围内清零，范围外保留 | 全库唯一性靠 B13 现场证明；不能称全项目清零 |
| C-06 SSH 与 Windows 交付 | 公开 Docker API、存 token、绕过 NTFS | 授权 SSH loopback、无回显凭据、Linux git archive | A13 侧访问方案未部署；授权结束不续跑，历史 checkout 失败保留 |
| C-07 证据与文档增量 | 原目录覆盖、私有归档公开、旧结果归给新 SHA | 归档私存、公开索引；raw pin/JSON 内容分开核验、人工回签另记 | CI 会过期；最终候选另验；原 summary 不改 |
| C-08 合并与发布 | 分叉后直接用个人分支替代组级候选 | #28/#29 独立评审、A 协调合并、保留冻结 SHA、候选统一验收 | 不自行合并 main 或发布 RC，group_release_acceptance=false |

[最终报告](FINAL_REPORT.md) · [索引](EVIDENCE_INDEX.json) · [回签状态](PAIR13_SIGNOFF.md)。记录已实施方案及边界，AI 辅助整理，不替代人工签署或同伴审查。
