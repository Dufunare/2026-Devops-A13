# E7 AI 使用与实现来源

日期：2026-10-25；任务：A13 的 E7 BuildChecker 教学验证，负责学号 241830217。

- ChatGPT GPT-6 通过用户指定的 GitHub 连接直接读取分支和 `docs/tmp-references`，对照 E7 PPT 及教师的课程文件使用顺序。区分 A13 BuildChecker、B13 DRAFT，以及学生实验包与教师实际演示记录。
- 将组员 241830088 的 E5 分支合并到 `e7/241830217-reproduction`，保留双亲提交及 E5 运行证据。原教学代码中 `scripts/run_e7_a_gate.py`、`tests/e7/test_e7_a_gate.py` 等明确归属教师材料经 E5 导入，非本轮自主设计。
- 自主增加 `scripts/verify_e7_a_evidence.py`：对保存的 E7 成果做 JSON/CSV、一致性、输入 SHA256、实际/声明图集合差、finding 原始 trace 行号、Make 数据库来源复核；不执行 Docker，也不能替代真实实验。
- 自主增加 `tests/e7/test_e7_evidence_audit.py` 5 项伪造证据/路径篡改负例测试，以及 GitHub Actions workflow。
- 首次 Actions 执行确认 11 个离线预言/审计单测通过，但因 `secret_scan.py` 对 Git 非 ASCII 文件名的引号解释错误，参考目录里的 `.env.example` 被误判为 `.env`；本轮据真实日志修改为 `git ls-files -z` + `os.fsdecode`，待后续 CI 再确认。未为了通过测试而移除真实密钥检测规则。
- 无课程云服务器 SSH/Docker 使用权限，不声称已运行 E7 的 Docker/strace 八场景或实际配置 main branch protection/PR merge rejection。PENDING 情况如实记录。

和论文的边界：课程小样例验证 BuildChecker 执行/声明依赖集比较与故障处理；不是在论文 30 个开源项目上做性能或有效性复现。教师 `03_验收与实验记录` 仅供比对观察。
