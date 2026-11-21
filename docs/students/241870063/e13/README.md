# H2-inih 与 C5 回滚预检

241830088 已取回两份归档并核对 SHA-256。H2 的 177 项产物引用、五阶段 job/trace 及修复输入哈希一致。C5 错误补丁通过编译与程序测试，因缺少 main.o → extra.h 被复检拒绝，前后快照及归档项目 Makefile 哈希一致。登记结论为“教师 H2 首轮通过”和“H2 C5 回滚预检通过”。实际项目 C5 等待 B13 本轮配对输入。real08 派生层确认单独登记。

[执行版本、环境、首次权限失败及云端原件位置](H2-C5.md) · [归档校验清单](SHA256SUMS)

## 原件取阅与恢复

从个人报告所列课程服务器路径取回两个 tar.gz。把两个包放到同一目录，用 `sha256sum -c <本清单的绝对路径>` 校验。可用 `tar -tzf <包名>` 查看逐文件列表。H2 归档含请求、候选 Dockerfile 和首轮 work 目录。C5 归档含项目副本、错误补丁、前后快照和 validation。恢复到新目录，保留原件。

重建 H2 输入使用教师发放的 e13-upstream-student.zip（SHA-256 `d9818c5f34d6ff5b6016222dabd7f56daca09ceaa5f525be214e146e3d485435`），按课程手册解压到仓库的 data/。从 H2 首轮包恢复 data/e13-upstream-student/H2-inih/request-e12.json 与对应 work 目录。编排镜像、环境和项目 C0/C1 见个人报告。

## 复现入口

以下命令供有需要的审阅者使用。脚本由首次终端命令整理，首次运行的实现 SHA 为 a164ebdc005fa4a868ee63d98367e6d1b8faa75b；新执行使用独立目录并按实际版本登记。仓库本地 git user.name 为执行者学号，H2 入口按学号选择已构建的课程镜像。

```bash
python3 scripts/e13/241870063/replay_h2.py
```

C5 入口可直接读取已恢复的首轮补丁。在仓库根目录运行，将镜像变量设为可访问的同版编排镜像。

```bash
OUT=$(mktemp -d "$PWD/work/c5-replay-XXXXXX")
IMAGE=sha256:a84a0df22c68496beb8c926e8b43ae31a375c919acdae07aa52e4bee617a7e9d
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/course:ro" -v "$OUT:/evidence" -e HOME=/tmp \
  -e PYTHONPATH=/course/labs/e8e10 "$IMAGE" \
  python3 /course/scripts/e13/241870063/preflight_c5.py \
  /course/work/e13-H2-inih-01/candidate.patch
```
