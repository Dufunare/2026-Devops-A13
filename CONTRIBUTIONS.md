# A13 贡献登记

本文件只登记真实、可追溯的工作。请每位成员用自己的 GitHub 身份补充。

截至 2026-10-09，已核对 GitHub `main` 分支的 7 条提交，最新提交为 [`b755aff`](https://github.com/Dufunare/2026-Devops-A13/commit/b755aff8df18cd363a2e556b201a7b3a240e1a44)。下表区分已进入主分支的贡献和已完成但尚未提交的本地材料；提交记录本身不作为审查通过或运行验收通过的证明。

| 成员 | 负责范围 | Issue | Commit | PR | Review | 运行证据 |
|---|---|---|---|---|---|---|
| Dufunare（提交作者 Chenyu Du） | 仓库初始化、论文及 README 整理；E2 BuildChecker/EChecker 契约与 B13 对齐，补充 Schema、样例、验证脚本及验证记录，并合并 PR #2 | [#1](https://github.com/Dufunare/2026-Devops-A13/issues/1)（原登记） | `f17b820`、`d0936e6`、`fd13722`、`f6296c5`、`bc1ed35`（完整链接见下表） | [#2](https://github.com/Dufunare/2026-Devops-A13/pull/2)，已合并 | 合并记录已核实；组员审查记录待补 | [E2 契约验证记录](evidence/E2/2026-09-26-contract-validation.md) |
| 241830088 / zycAlmira | E4 BuildChecker 容器环境、Make 命令、环境自检、密钥扫描、冒烟检查与测试、MD/RD fixture；调整镜像构建使用的 Debian 软件源 | 待补 | `dc76e74`、`b755aff`（已进入 main，完整链接见下表） | 待补 | 待补 | [E4 环境与运行说明](docs/E4/README.md)；个人实际运行日志待补 |
| 241870063 / Mikasa-79（王宣昊） | E3 MD/RD、C0/C1/C2、MODE 补充实验、Linux 跟踪、独立副本自检及材料汇总；通过 E3 分支提交审阅 | 未建 | [实验提交链](evidence/E3/241870063/supplement-evidence/commit-history.txt)，保存在 Git bundle 中；[A13 汇总分支提交](https://github.com/Dufunare/2026-Devops-A13/commits/e3/241870063-materials) | 见 [E3 提交记录](docs/E3/REVIEW.md) | 本人独立副本自检已完成；[组内互查待记录](docs/E3/REVIEW.md) | [E3 材料入口](docs/E3/README.md) |
| 241870063 / Mikasa-79（王宣昊） | E6：在课程云服务器运行 BuildChecker 自动检测与修复复检，补充一项路径过滤测试，整理 E6 证据与报告 | 未建 | `18d333e` 及 E6 文档提交（分支 `e6/241870063-mvp`） | 待开 | 待组员审查 | [E6 实验报告](docs/E6/实验报告.md)；[E6 证据](evidence/E6/241870063/README.md) |
| 成员4 | 待分配 | 待补 | 待补 | 待补 | 待补 | 待补 |

## 已核实的主分支提交

时间为北京时间，作者身份根据 Git 提交及 GitHub 账号关联记录登记。

| 时间 | 作者 / GitHub 账号 | 提交 | 可确认的贡献 |
|---|---|---|---|
| 2026-09-20 11:06 | Chenyu Du / Dufunare | [f17b820](https://github.com/Dufunare/2026-Devops-A13/commit/f17b8205b489fcc9a67fff52c758ce729fc44727) | 初始化仓库 |
| 2026-09-20 11:09 | Chenyu Du / Dufunare | [d0936e6](https://github.com/Dufunare/2026-Devops-A13/commit/d0936e6851280fccbcce3d2114270fe55115cf74) | 添加论文资料和 README 内容 |
| 2026-09-26 14:09 | Chenyu Du / Dufunare | [fd13722](https://github.com/Dufunare/2026-Devops-A13/commit/fd13722e876053c34ec9935bd4c9d59ad1bf976b) | E2 契约对齐、Schema 和样例、对接文档、验证脚本及测试 |
| 2026-09-26 14:11 | Chenyu Du / Dufunare | [f6296c5](https://github.com/Dufunare/2026-Devops-A13/commit/f6296c5cf5e817626bfaabd177d06814e81ea771) | 添加 E2 契约验证证据与贡献登记 |
| 2026-09-27 11:12 | Chenyu Du / Dufunare | [bc1ed35](https://github.com/Dufunare/2026-Devops-A13/commit/bc1ed352dc0b8ff9e77a69222a69deb03e49a618) | 合并 E2 契约对齐 PR #2 |
| 2026-09-30 11:39 | 241830088 / zycAlmira | [dc76e74](https://github.com/Dufunare/2026-Devops-A13/commit/dc76e744fd27415ee40c862df8e17fddf69cbf3f) | 添加 E4 BuildChecker 环境、辅助脚本、测试及 fixture |
| 2026-09-30 12:46 | 241830088 / zycAlmira | [b755aff](https://github.com/Dufunare/2026-Devops-A13/commit/b755aff8df18cd363a2e556b201a7b3a240e1a44) | 调整 Dockerfile 的 Debian 软件源 |

上述 7 条提交中，Dufunare 名下包含 1 条合并提交。提交数量不等同于工作量，也不能据此推断其他成员未开展实验；未上传的工作应补充相应材料后登记。

## 规则

1. 不替其他成员制造 commit/review。
2. 每位成员至少审查自己负责的 Schema/样例/论文对应部分。
3. 与 B13 达成的决定必须链接到双方可见的 Issue/PR/会议记录。
4. 论文复现运行证据与 E2 合成 fixtures 分开登记。

## 2026-11-28 补充：成员 C（241830217 / Dufunare）E13–E14 个人交付

| 工作 | PR / 固定代码 | 证据与边界 |
|---|---|---|
| E13 C4/C6/C7/C8、H3 与 CI | [#22](https://github.com/Dufunare/2026-Devops-A13/pull/22) 6ca6e57 | B 审查同意；受控样例、ECS 首轮，不宣称组级全覆盖 |
| E14 Compose、健康、连续性、故障恢复 | [#23](https://github.com/Dufunare/2026-Devops-A13/pull/23) 587c533 | B 审查同意；教学样例与 CI |
| 实际 DRAFT 执行桥、子容器证据与恢复 | [#28](https://github.com/Dufunare/2026-Devops-A13/pull/28) 84cc47f | 受控 CI/ECS PASS，待独立评审和集成 |
| B13 消费端、Windows CI、C5/C8 原件门禁 | [#29](https://github.com/Dufunare/2026-Devops-A13/pull/29) a5e32dd | 10/10 CI、五轮跨机及双端审计 PASS；A13/B13 总回签与 B13 11-28 最终确认齐备，个人冻结版本双边联合验收成立 |

详见 [个人最终报告与证据入口](docs/students/241830217/e13e14/README.md)。A 的 C1–C3 与协调、B 的真实适配及验证器、B13 部署/运行/服务端原件和现场核验归各自贡献，C 登记本人代码、测试、客户端实际运行与证据整理。AI 辅助实现和文档，不代签、不代审查。上述个人/协调分支不等于已合入 main 或发布 RC。
