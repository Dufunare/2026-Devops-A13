# 241870063 的 E6 运行证据快照

运行日期 2026-10-26（UTC 06:36–06:49），在 A13 课程云服务器 `/root/241870063/e6-buildchecker` 执行，分支 `e6/241870063-mvp`。报告见 [docs/E6/实验报告.md](../../../docs/E6/实验报告.md)。

## 目录

| 路径 | 内容 | 源码 SHA | 镜像 |
|---|---|---|---|
| `build-e6-01/` | 基线镜像构建、image inspect、15 项服务单测 | `202555a` | `course1020-buildchecker:241870063-e6` |
| `e6-before/` | 原始样例检测：输入副本 `fixture/`、`evidence/findings.json`、实际图/声明图/进程表、Make 数据库、7 份 trace、runner 命令与退出码 | `202555a` | 同上 |
| `e6-after/` | `--fixed` 修复副本复检，结构同上 | `202555a` | 同上 |
| `e6-verify.json` | `verify_e6_evidence.py` 对前后报告的断言结果 | — | — |
| `build-e6-02/` | 加入新测试后重建镜像，16 项服务单测 | `18d333e` | `course1020-buildchecker:241870063-e6b` |
| `e6-gate/` | 新镜像跑完整 A 门禁（8 场景）的原始结果 | `18d333e` | `...:241870063-e6b` |
| `*.exit`、`*.console.log` | 外层 shell 记录的退出码与控制台输出 | | |
| `image-id-e6-0*.txt`、`source-sha-e6-0*.txt` | 镜像 ID 与运行源码 SHA | | |
| `commit-history.txt`、`secret-scan.txt` | 打包时的提交记录与密钥扫描结果 | | |
| `SHA256SUMS.json` | 本目录除自身外全部文件的 SHA256 | | |

## 与原始 `work/` 的关系

服务器上 `work/` 打包为 `e6-work-241870063.tar.gz`（SHA256 `36e0a2b37ae5182f8fd7ca3bd5b50a13bca3e3be2f7db60a2daa8f1d7e52071d`），本目录是其解包副本。与 E5 快照一致，未纳入构建二进制（`app`、`main.o`）和临时容器 ID 文件，共删去 22 个文件；其余文件保持原字节。

`build-e6-01.console.log` 不存在：该次 `tee` 在 `work/` 创建前启动，未能写入；同次运行的完整日志由脚本保存在 `build-e6-01/` 内，退出码见 `build-e6-01/*/exit-code.json`。

本快照只证明课程教学样例 `md-rd` 上的检测与复检，不代表论文完整基准复现。
