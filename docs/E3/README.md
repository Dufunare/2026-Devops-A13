# A13 E3 材料汇总

汇总人：241870063。当前状态：A 组样例与证据已准备，已做本人独立副本复跑；组内互查及正式提交记录见 [REVIEW.md](REVIEW.md)。其他成员的工作仅按真实证据追加。

本材料依据《E3_并行测试基线_20260920.pptx》的 A 组清单整理。课件允许自选小项目，E3 先独立准备样本，E12 再接入另一组的真实数据；本次不声称已经实现或运行完整的 BuildChecker/EChecker。

## 材料入口

| 内容 | 位置 |
|---|---|
| 原实验说明与复现命令 | [原实验 README](../../evidence/E3/241870063/README.md) |
| MD/RD 源码及人工判断 | [源码](../../evidence/E3/241870063/md-rd/)、[实验报告](../../evidence/E3/241870063/md-rd-report.md) |
| C0/C1/C2 的预期报告、SHA、配置与日志 | [原版本证据](../../evidence/E3/241870063/c012-evidence/) |
| MODE 行为对照、跟踪与独立副本复跑 | [补充说明](../../evidence/E3/241870063/supplement-evidence/README.md) |
| 固定发现报告与源码快照哈希 | [md-rd-oracle.json](../../evidence/E3/241870063/supplement-evidence/md-rd-oracle.json) |
| 实际运行环境 | [environment.txt](../../evidence/E3/241870063/supplement-evidence/environment.txt) |
| Linux 原始跟踪及 Make 数据库 | [跟踪目录](../../evidence/E3/241870063/supplement-evidence/linux-trace-2UnSx0/) |
| 全部五个实验提交 | [Git bundle](../../evidence/E3/241870063/c012-with-supplement.bundle) |
| 原始交付包及 SHA256 | [delivery/](../../evidence/E3/241870063/delivery/) |
| 汇总时材料一致性检查 | [repository-audit.json](../../evidence/E3/241870063/repository-audit.json) |
| 个人贡献、AI 使用说明 | [CONTRIBUTIONS.md](../../CONTRIBUTIONS.md)、[AI_USAGE.md](AI_USAGE.md) |

## 版本与预期

以下 SHA 属于 **bundle 内的独立实验仓库**，不能直接在 A13 仓库中 checkout。名称用于说明实验阶段，不表示存在同名 Git tag。

| 阶段 | 完整实验 SHA | 修改与预期 |
|---|---|---|
| C0 | `f72547c269a6fbdd5c5b143c3c2af0bd2765aef0` | 依赖声明正确，`-O0`，程序输出 1 |
| C1 | `3d272ac863c07570b2f1f189085103f85fb3793c` | 新增 `extra.h` 的 include，未声明该依赖，输出 2 |
| C2 | `746c642bec52c86b2b965b42b5e0c0bf2b22890a` | 仅改 `-O0` 为 `-O2`；普通 make 不重建，清理重建输出 2 |
| MODE 基线 | `3d7d36aca7487c2668ae56c7f4ee9242fe257a3b` | 程序增加默认 `MODE=0`，输出 2 |
| MODE 命令变化 | `5a94d5c0d9aa65f07cb7e8cbbfc0af30a8dc7d67` | 仅给编译选项增加 `-DMODE=7`；保留旧产物输出 2，清理重建输出 9 |

原 C2 能展示命令变化未触发重编译，但优化级别不改变本例功能输出。后两个提交补充了可区分的功能对照，原始三个提交及其证据均保留。补充实验的源码与课件 `10/12/19` 示例不同，覆盖相同的命令变化漏重建现象。

所有人工依赖结论限定在 `main.o` 的项目文件范围，系统头文件不计入该人工答案集合：

- MD/RD 样例：遗漏 `config.h`，冗余声明 `unused.h`。
- C0：本例范围内无 MD/RD。
- C1、C2 及 MODE 补充版本：`main.o` 仍遗漏 `extra.h`。

人工报告标记为 `MANUAL_ORACLE`。日志和原始跟踪作为实际观察单独保留，不将人工答案计为检测器输出或准确率。

## 快速复现命令变化对照

在 Linux 环境中准备 Git、GNU Make 和 C 编译器。从 **A13 仓库根目录**执行，工作发生在新临时目录：

```bash
E3_INPUT="$PWD/evidence/E3/241870063"
E3_REPLAY=$(mktemp -d)
git clone "$E3_INPUT/c012-with-supplement.bundle" "$E3_REPLAY/c012"
cd "$E3_REPLAY/c012"

git checkout 3d7d36aca7487c2668ae56c7f4ee9242fe257a3b
make clean && make && ./app
# 预期输出 2

git checkout 5a94d5c0d9aa65f07cb7e8cbbfc0af30a8dc7d67
make && ./app
# 保留旧产物：预期未重编译，仍输出 2

make clean && make && ./app
# 编译命令包含 -DMODE=7，预期输出 9
```

每一步报错时保留输出，并先定位问题。原 MD/RD 和 C0/C1/C2 的复现步骤见材料入口中的原实验 README。

已保存的补充环境是 Debian 13、x86_64、GCC 14.2.0、GNU Make 4.4.1、Git 2.47.3、Python 3.13.14、strace 6.13。复跑系统调用跟踪还需 Linux `strace` 和容器允许的跟踪权限。

## 证据阅读与交付边界

- `mode-*-command.log` 是 `make -n -B main.o` 打印的命令快照；实际编译记录在对应 `build.log` 中。
- `replay-*` 是同一成员从 bundle 克隆后的独立副本自检，不冒充另一位成员的验收。
- 跟踪中 Make 查询 `unused.h` 的属性，编译器 `cc1` 打开 `config.h`；文件属性查询与编译器读入头文件要区分，原始跟踪不等于完整依赖推断。
- `latest-trace-dir.txt`、`replay-dir.txt` 和部分日志含当时的绝对路径。跨机器定位文件应使用本页提供的相对路径。
- `c012/` 是最新源码导出。为避免嵌套仓库，汇总时未复制 `.git`；原始交付压缩包和两个 bundle 保留了可恢复的提交历史。生成的 `app`、`main.o` 仅保留在原始交付包中。
- SHA256 校验文件使用相对文件名，可在 `delivery/` 中运行 `sha256sum -c E3-A13-241870063-supplement-20261009-032058.tar.gz.sha256`。

课件要求相互检查可复现性、人工答案与日志的区分、判断依据和失败定位。组内互查方式与意见应据实登记；课件未明确要求第二名成员完整重跑整套实验。正式提交入口与小组提交记录另在 REVIEW 中补充。
