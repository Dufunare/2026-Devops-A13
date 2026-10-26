# E7 AI 使用及来源记录（交付版）

日期：2026-10-25 · A13 / BuildChecker · 分工学号：241830217

## 使用工具与授权范围

用户授权 ChatGPT GPT-6 使用已连接 GitHub，在 `e7/241830217-reproduction` 分支直接读取、编写 E7 工程与报告；又授权根据课程包清理临时资料，归档真实 E7 证据并形成作业提交文件。实验原始 CI 在 GitHub Actions 上实际执行，AI 不声称远程登录了课程 SSH 服务器。

## 来源/独立贡献划分

- E5 组员 241830088 的 `e5/241830088-reproduction` 中已导入教师教学包里的检测器、E6/E7 参考脚本与测试；E7 通过双亲合并 `7bbab16` 延续，不把这部分实现列为本人原创，E5 报告及源码校验见 `docs/E5/`。
- 本人 E7 扩展为 `scripts/verify_e7_a_evidence.py`（独立证据链审计）、`tests/e7/test_e7_evidence_audit.py`（5 项篡改/错误路径负例）、`.github/workflows/e7-quality-gate.yml`（真实容器门禁与 Artifacts）。
- CI 中实际发现源扫描器把 Git 中文路径 C-style 引号误读成 .env；针对 `scripts/secret_scan.py` 使用 `git ls-files -z` 修复，保留安全检查逻辑。另将 GitHub runner 镜像仓库定位至官方 Docker Hub，仍锁定原 OCI digest。
- 课程权威文档为 2026-10-20 E7 PPT、A 组操作说明、CI 指南、验收清单和原始里程碑；原上传 `docs/tmp-references/` 在本次收尾按要求从工作树删除，必要来源标识见 `课程材料来源索引.md`。其中大量教师演示记录不作为本组原创实验数据。

## 验证和模型使用边界

本组真实验收凭据为源码 SHA `76a8f004e61560edc3f1d77a6c51fb2113413cc4` 的 [CI Run #40154562661](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661) 及 [Artifact](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661/artifacts/12583718152)，包含全部 Docker 测试和 trace；11 项离线独立测试、15 项服务测试和 8 项 Gate 全部通过，原始证据 SHA256 由 `evidence/E7/241830217/` 索引记录。

本轮未在 A13 课程云服务器执行 E7，也没有替课程教师确认环境等价；GitHub main 分支保护和“失败 PR 被拒 → 修复后合并”尚无本组实证（接口读取分支保护 403）；不能将它们预填 PASS。没有复现整个 TSE/BuildChecker 大规模基准。报告与工作流均保留该区分。
