# Pair13 个人冻结版本回签状态（2026-11-28）

**五轮运行及双端归档审计 PASS；B13 服务端总回签已收到；A13 本人确认发送及 B13 最终确认待登记。**

范围限定 A13 241830217 的冻结客户端 `a5e32ddb1acb5d3ee51a19c744ec1a6fe71ab31e`，B13 成员3操作的同步 `7ddbd700ece7bedaa3a1d0c73cb6e8110fec9eb4` 与异步 `1dcc785760b8f60d5f58802a78b7962b6185ed57` 部署；全镜像和任务身份见 [证据索引](EVIDENCE_INDEX.json)。不替代组级正式双向验收与发布。

| 项目 | 状态 | 依据 |
|---|---|---|
| B13 服务端总回签 | RECEIVED 2026-11-27 | 对方文字总回签认可五轮及我方服务端复算；C8 Store 全库唯一性为 B13 现场核验 |
| A13 双端审计 | PASS | 双方总包、十轮次归档、5227 manifest、2285 HTTP、27 C5 原件、2216 C8 原件、26 子容器 |
| A13 客户端总回签 | DRAFT / PENDING_MEMBER_CONFIRMATION | 已整理待本人确认发送的 Markdown，摘要见索引；本文不是代签 |
| B13 最终确认 A13 总包及 C5/C8 摘要 | PENDING_PEER_ACK | 待明确回复认可完整 SHA 和范围 |
| 双边最终确认 | PENDING | 不改写原 summary 的 false 字段 |
| 组级发布 | NOT_ACCEPTED | 合并后固定候选独立验收 |

B13 总回签确认 normal/C4/recovery/C5/C8 全部通过；其现场报告 Store 共 10 个目录（9 历史+1 本轮）、同键唯一 Job，重放和 409 不新增实际执行。A13 未查询在线全库或 Docker daemon。C4 首次 403、C5 清单格式修正（recover 前发现，未实际执行失败 recover）、C8 范围外缺失一条均如实记录。

| 包 | 字节 / SHA256 |
|---|---|
| A13 客户端总包 | 2508573 / `3fea847de93b5482a67cc5c170dcde89595a2b10fcd5abcd9bea42615adf7f7b` |
| B13 服务端总包 | 3581442 / `f9e6dedf8546ee5395d5e172944ea48cb507b11dde641c7de6a9f37432163cb0` |
| 双端审计 | 21850 / `42b32e31612ed477327b2188ebf5e2d01cf08a8a98cb622a828f80b7b080e352` |

双方原始回签、私聊、完整归档和审计 JSON 在私下交付渠道保管，不公开复制。收到最终明确确认后追加日期、确认来源与绑定 SHA；原件不覆盖。线上联调已经结束，不需恢复 SSH 或重跑。
