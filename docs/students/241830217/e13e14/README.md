# E13–E14 成员 C（241830217）最终交付入口

> 2026-11-28：个人固定版本五轮运行和双端证据审计 PASS；B13 服务端总回签已收到，A13 本人确认及 B13 最终确认待登记；组级候选待发布。以下历史预检按原执行版本保留。

| 入口 | 内容 |
|---|---|
| [最终个人报告](FINAL_REPORT.md) | E13/E14 结果与边界 |
| [ADR](ADR.md) | 关键工程决策 |
| [证据索引](EVIDENCE_INDEX.json) | 固定版本、完整归档摘要与 CI/ECS |
| [回签状态](PAIR13_SIGNOFF.md) | 服务端已回签、个人最终确认待登记 |
| [E14](E14.md) / [执行桥](E14_REAL_EXECUTION_BRIDGE.md) | 实现及受控验证 |
| [B13 消费端](E14_B13_CLIENT.md) / [跨机准备](E14_CROSS_MACHINE_PREP.md) | 操作手册、历史准备 |

运行绑定 84cc47f / a5e32dd；文档提交不冒充运行。原始归档私存，公开 Git 只保存索引及摘要。PR28/29 由组内审查与集成。

---

## E13–E14 成员 C（241830217）测试工程与证据索引

## 身份和边界

- 工作分支：`student/241830217/e13e14-c`。
- 首轮执行源码：`9681702414428e7b9a7d0da5d9baa04443bee613`。
- 本 PR 提供：C4/C7/C8 固定样例自动化、C6 假密钥扫描单测、CI 门禁以及首次实验索引。
- 本 PR **不**替代：A13/B13 正式跨组 C1–C8、三个教师项目在最终整合版本的复测、E14 正式四容器 E2E 和 `v0.9-rc` 发布。
- 教师包原有 `compose.yaml`、`orchestrate.py`、`service.py`、`scan_runtime_logs.py` 保持原字节；不覆盖其他成员已实现的 E13 handoff 或 E11/E12 profile 适配。

## 2026-11-20 已有手工预检证据（待归档到组级索引）

| 项目 | 证据位置（个人 ECS worktree） | 终端回显结论 |
|---|---|---|
| H3 tiny-AES-c | `work/e13-H3-tiny-aes-20261120T103352Z/` | 五阶段成功；177/177 本地产物 SHA/bytes 一致，findings=[] |
| C4 超时 | `work/e13-c4-H3-timeout-20261120T105514Z/` | `DRAFT_FAILED` / `TIMED_OUT`，12ms；构建进程未见残留，文件稳定 |
| C4 恢复 | `work/e13-c4-recovery-20261120T105743Z/` | E11-A 正常任务 SUCCEEDED，job/trace 与失败任务不同 |
| C6 密钥扫描 | `work/e13-c6-20261120T105753Z/` | 假 key 扫描 1→0；源码/历史/镜像 0 命中；220 文本日志 0 命中 |
| C7 错误提交→恢复 | `work/e13-c7-failed-20261120T110413Z/` 与 `work/e13-c7-success-20261120T110413Z/` | `COMMAND_FAILED`→`SUCCEEDED`；成功任务 85 产物核验 |
| C8 本机 API 幂等与下载 | `work/e13-c8-H3-20261120T110906Z/` | HTTP 202/409、只创建 1 个任务，177/177 HTTP 下载哈希和响应头一致 |

上述结论来自执行者已提交的终端输出；**原始 work/ 文件需单独打包并做 SHA256**，不能以本 README 冒充本仓库已包含全部原件。C4 和 C7 是教学样例的预检，不主张对 B13 真实项目的正式验收。

## 自动化测试内容

`labs/e13e14/tests/test_member_c_gate.py`：无 Docker 的快速单测，验证 C6 假 Key 命中、脱敏/清理、不可读输入，以及原始产物越界/哈希篡改拒绝。测试只在临时目录内动态构造假 Key，不会把密钥形态的固定字符串写进 Git 历史。

`labs/e13e14/member_c_gate.py`：需要 Docker 的固定样例 E13 回归，执行：

1. **C4**：新请求 `build_timeout=0.01`；外层失败/内层超时；延迟核对 DRAFT 输出文件稳定；以 E11-A 新任务恢复。
2. **C7**：无效 C0 SHA 失败；另一 E11-A 任务成功；校验不同 job/trace 与成功任务全部产物。
3. **C8**：启动仅属于本次测试、独立 `work/api-jobs` 挂载的 Docker API 容器；验证 POST 202、重放同 job、差异输入 409、成功后幂等、所有 HTTP 产物 SHA256/bytes/响应头；最后只清理本次容器。
4. 对本次 `work/` 证据运行 `scan_runtime_logs.py`，保留结果和脱敏输出。

这里的 C4 文件稳定性是短时窗口观测，不是对全部 Docker daemon 内部构建进程的形式证明。C7 是“错误 Git 提交”的失败注入，不是“运行中崩溃”的用例。

### 不涉及 Docker 的本地验证

```bash
cd /root/devops-students/241830217/buildchecker-e13e14-c
python3 -m py_compile labs/e13e14/*.py labs/e13e14/tests/*.py
python3 -m unittest discover -s labs/e13e14/tests -p 'test_member_c_gate.py' -v
python3 scripts/secret_scan.py . --history
```

### ECS Docker 完整回归（会新建任务，勿重复运行旧 OUT）

```bash
cd /root/devops-students/241830217/buildchecker-e13e14-c
test -f data/integration-sample/e11-a.json || python3 run_e11e12.py prepare
python3 labs/e13e14/member_c_gate.py \
  --image course-e11e12:241830217 \
  --api-port 18095 \
  --out "work/e13-member-c-$(date -u +%Y%m%dT%H%M%SZ)"
```

该脚本自动核对镜像标签和本仓库的数字学号 `git config --local user.name`。独立 API 数据库挂载在该次 `--out` 目录内部，不与之前监听 `18085`、`8081` 的服务共享存储；如果 `18095` 被占用，应检查并改用新的空闲端口。不要删除别人的 Docker 容器。

### GitHub CI

`.github/workflows/e13-member-c.yml` 包含 `static` 和 `runtime`：

- `static`：单测、旧 10 契约回归、源码和 Git 历史密钥扫描、四服务 Compose 配置解析。
- `runtime`：固定的基础镜像 digest，记录 **CI 专属** Dockerfile 镜像源差异，运行 C4/C7/C8 并验证所有 HTTP 下载件，扫描运行日志与镜像元数据。上传 `work/ci-e13-member-c/` 和 `work/ci-e13-image/`，包括失败原件。

**CI 镜像环境说明：**当前 `9681702` 的 Dockerfile 写死了清华 APT 和 PIP 源，曾在 GitHub Runner 连不上。CI 只在 `work/ci-e13-image/Dockerfile.ci` 的**临时副本**替换镜像源为 Debian 上游/PyPI，不更改仓库追踪的 Dockerfile；基础镜像 SHA 和源文件保留，副本及 SHA256 一并上传。等组长的正式 CI 镜像源适配进入最终整合分支，应复核此过渡处理，不能将 CI 镜像 ID 冒充原 ECS 镜像。

## 责任和后续

- 组长 A：C1–C3、A→B 报告来源、正式回签、E13 总门禁与 E14 发布。
- 成员 B：真实项目适配、C5、DRAFT 镜像与全项目修复证据；按组内约定 Review 成员 C PR。
- 成员 C：C4/C6/C7/C8、H3、测试工程/CI、E14 Compose 和故障恢复。

本 PR 只解决成员 C 的 **E13 自动化与 CI 第一阶段**。E14 另行提交并按最终已合并固定提交重跑；候选门禁不齐时状态仍为“候选待发布”。
