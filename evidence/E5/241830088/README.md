# 241830088 的 E5 公开证据快照

本目录供 B13 及课程验收读取。运行日期为 2026-10-22，原始运行源码为 `cf898e29e57b0b6637d2bba6be9f0a9b6b445c36`。交接说明见 [B13_HANDOFF.md](../../../docs/E5/B13_HANDOFF.md)。

## 内容

- `e5-01/evidence/`：原始输入、完整 7 份 trace、Make 数据库、程序输出、构建 stderr。
- `e5-01/runner/`、`e5-command.json`：容器/外层命令、stdout/stderr、退出码。
- `e5-01/input-hashes.json`：四个原始输入的 SHA256。
- `manual-analysis.json`：本次 E5 手工标注的实际/声明依赖集合及证据行；来源为 `A13_MANUAL_ORACLE`。
- `build-e5-01/`：构建日志、镜像 inspect、15 项服务单测和工具链。
- `preflight-e5-01/`、`regression-e5-01/`、`security-e5-01/`：环境、既有契约回归及原始运行结束时的安全扫描记录。
- `publication-provenance.json`：每份公开副本的原始路径、原始哈希、公开哈希及变换。
- `SHA256SUMS.json`：本目录内除该清单自身外全部文件的 SHA256。

从本人本机已校验的原始 `work/` 复制 47 个文本文件。trace、Make 数据库、输入和程序输出保持原字节。3 份环境文本中的云主机标识替换为 `REDACTED_COURSE_HOST`，原始记录保留在本机归档；变换前后的哈希在来源清单中列明。构建二进制 `app`、`main.o` 及临时容器 ID 文件未纳入此精简快照。

仓库 `.gitattributes` 对此快照关闭文本换行归一化，并保留日志和 Make 数据库的原始尾随空格与空行，以便不同操作系统上的接收方验证同一组文件哈希。

`work/` 为原始运行路径，本目录是供 GitHub 读取的固定副本；重跑仍使用新的 `work/` 目录。材料证明本次样例的执行与手工分析，不代表自动服务接口、E6/E7 或 B13 接收验收已经完成。
