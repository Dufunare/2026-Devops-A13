# E13–E14 成员 C 最终个人报告（241830217）

2026-11-28（北京时间）。**个人固定版本功能、五轮真实跨机运行、双端离线审计完成；B13 服务端总回签已收到；A13 本人确认发送及 B13 最终确认待登记；组级候选待发布。**

## 1. 责任与固定版本

本人负责 E13 C4/C6/C7/C8、H3 tiny-AES-c、测试运行工程、E14 Compose/健康/日志/Trace/故障恢复和 CI。A（241830088）负责 A 侧报告来源、C1–C3 和组级发布协调；B（241870063）负责真实项目适配、C5、验证器相关工作。本人消费 B13 服务；B13 的部署、快照、故障配置、实际服务端运行及现场取证属于对方贡献，不计作本人开发。AI 辅助代码、测试、审计与文档；实际运行由对应操作者完成。

| 运行源码 | 范围 | 证据 |
|---|---|---|
| `9681702414428e7b9a7d0da5d9baa04443bee613` | 首轮 E13 教师/保护预检 | [历史 README](README.md) |
| `84cc47fbd21948fb286e12cc4c49f527112a17ee` | PR [#28](https://github.com/Dufunare/2026-Devops-A13/pull/28)，真实 DRAFT 执行桥、受控 CI/ECS | [执行桥](E14_REAL_EXECUTION_BRIDGE.md)、PR28 |
| `a5e32ddb1acb5d3ee51a19c744ec1a6fe71ab31e` | PR [#29](https://github.com/Dufunare/2026-Devops-A13/pull/29)，冻结消费端与真实跨机 | [消费端](E14_B13_CLIENT.md)、[证据索引](EVIDENCE_INDEX.json) |

后续文档提交不改变原实际执行 SHA。PR22/23 经 B 审查同意，尚未单独合并，组级统一确认包含关系。

## 2. E13 质量门禁

| 项目 | 个人已完成 | 边界 |
|---|---|---|
| H3 tiny-AES-c | 11-20 ECS 五阶段；177/177 产物，findings=[] | 教师首轮 PASS，原 work 目录在 ECS，未随跨机包交付 |
| C4 | 首轮超时/新任务；PR28 下游 20 秒超时及无迟到写入；B13 真实 1 秒超时与新 normal 恢复 | 固定版本 PASS |
| C6 | 假 Key 1→0、工作区/历史/镜像/日志扫描、脱敏与不可读输入负例，CI 回归 | 受控样例 PASS；本次五轮 B13 未专门注入假密钥 |
| C7 | 错误提交失败→独立成功，85 产物；PR28 失败隔离、旧 Job 拒绝、单服务恢复 | 受控样例 PASS，跨机 C4/recovery 补充隔离证据 |
| C8 | 本地独立 Store Docker 门禁；B13 tomlc99 202/202/409/202、服务端 Store 唯一性回签 | 真实跨机 PASS（冻结范围） |

E13 课件要求对方项目与 C4–C7 的实际新运行、H1–H3 分开记录、缺陷闭环。最终组合候选须汇总双方项目、C1–C8、H1–H3 的对应证据；不能仅用个人受控样例签发 RC。

## 3. E14 实现与 CI/ECS

DRAFT 独占 Docker socket；固定 Job/角色/输入/顺序的受限执行桥复用 B 的 imgrunner/validate，实际 DRAFT 镜像运行下游容器。原始请求、候选 Dockerfile、C0/C1、Profile、报告 URI/SHA、exec/inspect、Job/Trace 贯穿五阶段。健康并发、逐角色任务锁、限定 Compose project 和 ownership 清理，实际超时 kill/rm，单服务停止和恢复。见 [E14](E14.md)、[执行桥](E14_REAL_EXECUTION_BRIDGE.md)、[ADR](ADR.md)。

- PR28 11-24 固定 HEAD：当时 9/9 workflow；87/87 离线+10/10 契约；ECS 正常及两次恢复各 247 产物、11 下游容器、MISSING=0；实际下游超时无迟到写入，单服务同容器恢复且其他三角色连续。ECS 归档 1159771 B、3855 项、摘要见索引，原件在 ECS，组内独立复核待完成。首次 ECS 预检端口环境变量影响单测，隔离环境后通过，未改源码。
- PR29 固定 HEAD：GitHub 10/10 workflows、Linux 115+10、Windows 17/17；操作者本机 Windows 17/17。[消费端 CI](https://github.com/Dufunare/2026-Devops-A13/actions/runs/45801343951)、[E13](https://github.com/Dufunare/2026-Devops-A13/actions/runs/45801344044)、[E14](https://github.com/Dufunare/2026-Devops-A13/actions/runs/45801343979)。Windows 全量/稀疏 checkout 曾因旧 papers/*:Zone.Identifier 路径失败；改用 Linux git archive，不关闭 NTFS 保护。CI 归档保留期见索引，元数据已核对，本次未下载 CI/ECS 原件。
- A13 侧访问层仍属提案，未在 ECS 部署。真实跨机消费 B13 独立协议；B13 C4/recovery 串行换栈，不称同容器连续性；同容器连续证据属于 PR28 控制样例。

## 4. B13 真实跨机实验（11-26 至 27）

同步四角色 member2-e14-1 使用 b13-level-v1 冻结 C0/C1；独立异步 e11e12-1 使用 tomlc99。所有源码/镜像/项目/输入 pin 见 [EVIDENCE_INDEX.json](EVIDENCE_INDEX.json)。通过授权 SSH loopback，不开放 Docker API、不保存 Token；第三 POST 后交换本轮 graph/findings；C5 第五 POST 后强制暂停核验回滚原件。

| 场景 | Job / Trace | 实际结果 |
|---|---|---|
| normal | `job-e5b6db9822b544cba0d409e105d73b63` / `trace-940c7309a1dd4868bd1a437b3cdd9472` | 6 POST；MISSING=0、REDUNDANT=1、仅 Makefile 写回 |
| C4 | `job-32fce11c3c4448d4b96bdfa1a7477208` / `trace-c0fc3d3389164645bc26ae1663fedf16` | 2 POST；预期超时、清理及源码不变 |
| recovery | `job-ca339fc359f744cb812c8ed2ce1275c7` / `trace-404d1ba7f4c147548af8024a326f5519` | 6 POST；MISSING=0、REDUNDANT=1、仅 Makefile 写回 |
| C5 | `job-8532b300328b40efa3c403682205ef93` / `trace-d2244084a65645849bc00e7d3cc9d573` | 7 POST；MISSING=0、REDUNDANT=1、仅 Makefile 写回；27 份回滚原件强制核验 |
| C8 | `job-eea43b0f196741d08e9c8150d26cddfe` / `trace-2048f49ed9de4e6d873c0e0e3d03df63` | 202/202/409/202；6 操作、12 inspect、范围内 MISSING=0、范围外=1 |

normal/recovery/C5 正确消除 MD、保留 REDUNDANT(main.o, unused.h)。C4 实际 worker 超时，kill/rm 与 ownership 查询空输出，源码不变；另建新 Job 正常恢复。C5 apply-check 真实失败、前后十个 tracked 文件原字节相同、Git 前后为空、execution/cleanup 与 HTTP 绑定；27 份原件核验后才正确修复。C8 下载 2216/2216 与服务端逐字节相同，同键同 Job、冲突 409、完成后重放；Store 全库唯一性/无额外执行以 B13 独立现场核验与总回签为依据，state、409 和原始 HTTP 互证。冻结范围 toml.o；范围外 toml_json→toml.h 一条 MISSING 如实保留。

## 5. 审计、过程事件与回签

双端总包、十份轮次归档、Job/Trace、镜像和全 SHA 见索引。原始审计结论 PASS_ARCHIVE_AND_CROSS_END_AUDIT：十份轮次归档、5227/5227 服务端 manifest、2285/2285 客户端 HTTP 记录、C5 27/27、C8 2216/2216、26 个下游容器 ID 无重复。同步 role-result 与 HTTP 按 JSON 内容比较，固定报告/交接原件按原字节；凭据特征扫描 0 命中，不能证明不存在任意未知凭据。本次收口再次复算总包、十份内层归档及审计文件摘要，未运行服务。

- C4 首次 Token 错误为 HTTP 403 鉴权拒绝、无 Job/Trace；首次客户端失败目录被清理，服务端日志保留，不补造。
- C5 初版清单多三个字段，在 recover 前发现不兼容；对方重交五字段清单，27 原件不变，未执行失败 recover、未重跑。
- C8 范围外缺失并非全项目零缺失，不扩修。
- [回签状态](PAIR13_SIGNOFF.md)：B13 服务端总回签收到，A13 待本人确认发送，B13 待最终确认客户端总包完整摘要；不改原 summary 中 false 字段。完整私聊、签署文件、原始归档/审计 JSON 不入公开 Git。

## 6. 复现与组级收口

操作入口见 [E14_B13_CLIENT.md](E14_B13_CLIENT.md)，保留原始请求和输入 SHA；任何新运行需授权及新 Job/Trace/out/key，不重放旧写请求。复现/回退仅操作所属 Compose project、端口及上一可用镜像与配置，保留失败/恢复证据；日志按 job_id、trace_id、stage、status、artifact SHA 定位。

收口前协调分支 4aa93b4 与 a5e32dd 共同基线 d43c678，个人分支领先 19、落后 2；由 A 协调 #28/#29 同伴审查及正常集成，不改写运行 SHA、不机械重复合并历史 PR。合并后固定候选须完成 CI、正式双向项目、C1–C8（尤其 C6/C7 的要求范围）、H1–H3、E14 正常/超时/坏补丁/单服务不可用与新任务恢复，并补组级三仓库 SHA、镜像、日志资源、Issue/PR、回退及发布清单。未齐时不发布 v0.9-rc。CI 原件须在保留期截止（PR28 12-08、PR29 12-10 UTC）前保存。

个人技术及证据审计已完成，不增功能、不重跑已通过五轮。个人回签确认、原 ECS/CI 留档和组内独立评审、候选验收仍需完成。
