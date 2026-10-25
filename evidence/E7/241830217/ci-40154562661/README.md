# E7 A13 GitHub Actions 原始证据索引

**状态：CI 已实际通过（PASS），课程云服务器执行环境与 PR 合并门禁证据另行待确认。**

- 责任人/组别：241830217 / A13 / BuildChecker（A 轨道）。
- 运行代码：[`76a8f004e61560edc3f1d77a6c51fb2113413cc4`](https://github.com/Dufunare/2026-Devops-A13/commit/76a8f004e61560edc3f1d77a6c51fb2113413cc4)；文档清理提交晚于本次实际运行，不能改变运行源码身份。
- [Run #40154562661](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661)；Job `e7-a-quality-gate` #121053217883：**success**。
- 原始 Artifact：[e7-a-evidence-40154562661-1](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661/artifacts/12583718152)（ID 12583718152；195 个文件；14 天保留策略）。
- **Artifact 原始 ZIP SHA256**：`ec06f1e650e0a2117ec18dd7eefd1ebfd236982c235c2945ae7bb371eff0adc6`。请及时本地备份。仓库不提交原始完整 ZIP，以免与代码压缩包重复且膨胀仓库。
- 原始 CI 环境：GitHub-hosted `ubuntu-24.04`，Docker 28.0.4（linux/amd64）；镜像 `sha256:eec09476303ed04737eba511368138e574ec0c21cb534175a4bbdbb8e1ae2103`；基础镜像仍按 E4/E5 固定 OCI digest 构建，CI 使用 canonical Docker Hub 路径。
- 本仓库保存从 Artifact 提取的**原始字节**：`gate-result.json`、`results.csv`、`evidence-audit.log`、`oracle-tests.log`、`commit.txt` 和 `base-image-source.txt`。路径与每份文件的 SHA256 见 `run-manifest.json`。
- 其余完整输入、trace、Make 数据库、实际/声明图、构建输出、服务单测及镜像检查保留于原始 ZIP。**这些不能用教师的 `03_验收与实验记录` 代替**。
- 真实验证：教学服务 15 项通过、独立 oracle/audit 11 项通过、八项 Gate 全部 `passed=true`、离线审计通过；三次原始 MD/RD 相同、仅 Makefile 修改、7 个 trace_id 不重复。
- 场景退出码 1 在原始缺陷与预期故障中属于**预期工具返回值**，不是门禁失败；完整 `gate-result.passed=true` 才是 E7 PASS。
- **未覆盖**：课程云服务器上的再次执行；main 分支保护真实状态、失败 PR 被拒和修复合并；完整论文基准复现。详见 `docs/E7/课程云服务器环境合规确认.md` 与 `docs/E7/验收记录.csv`。

校验原始备份：

```bash
sha256sum e7-a-evidence-40154562661.zip
unzip -l e7-a-evidence-40154562661.zip | tail
```

应匹配索引 SHA256；不要将文档清理后的最终 Git SHA 与本次实际运行 SHA 混淆。
