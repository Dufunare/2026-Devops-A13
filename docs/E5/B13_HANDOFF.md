# A13 → B13：E5 复现与证据交接

交接日期：2026-10-22。A13 执行人：241830088。接收方：B13。

状态：A13 E5 基础复现完成，以下材料已整理供 B13 独立读取与核对；B13 接收确认待反馈。本次交接为教学样例的原始证据和手工分析，正式服务的结构化结果及补丁复检在 E6 和后续联调继续。

## 1. 固定版本与入口

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/Dufunare/2026-Devops-A13.git` |
| 交接分支 | `e5/241830088-reproduction` |
| 运行时源码 SHA | `cf898e29e57b0b6637d2bba6be9f0a9b6b445c36` |
| 原始报告提交 SHA | `bf45399e401558e55caeb1d47c4328b38bbcbee5` |
| 交接材料版本 | 本文件所在的 Git commit；下载时记录完整 SHA，固定读取该 commit 下的文件 |
| 原始证据入口 | [`evidence/E5/241830088/`](../../evidence/E5/241830088/) |
| 文件 SHA256 | [SHA256SUMS.json](../../evidence/E5/241830088/SHA256SUMS.json) |
| 字节来源与公开处理 | [publication-provenance.json](../../evidence/E5/241830088/publication-provenance.json) |
| 正式复现说明 | [实验报告](实验报告.md) |
| 手工分析 JSON | [manual-analysis.json](../../evidence/E5/241830088/manual-analysis.json) |

运行时 SHA 对应构建和采集；之后的提交补充报告及公开证据，保留原始运行身份。接收方应使用“完整交接 commit + 仓库相对路径 + SHA256”定位材料。此快照尚未注册为真实服务 Job 的 Artifact。

## 2. 本次可复核结论

| 目标 | 项目内实际依赖 | Make 声明依赖 | 结论 |
| --- | --- | --- | --- |
| `main.o` | `main.c`、`config.h` | `main.c`、`unused.h` | MD：`main.o → config.h`；RD：`main.o → unused.h` |
| `app` | `main.o` | `main.o` | 一致 |

本次 build 退出 `0`，服务测试 `15 passed`；E5 采集退出 `0`，程序输出 `1`。环境适配、工具版本、命令和运行来源一并公开。

关键原始依据：

- [trace/t.16](../../evidence/E5/241830088/e5-01/evidence/trace/t.16) 第 67 行读打开 main.c，第 580 行成功只读打开 config.h。
- [trace/t.15](../../evidence/E5/241830088/e5-01/evidence/trace/t.15) 第 64、84 行分别派生 cc1（16）与 as（17）；两者归入同一个 cc 编译作业（15）。
- [trace/t.17](../../evidence/E5/241830088/e5-01/evidence/trace/t.17) 第 23 行创建/写打开 main.o。
- [make-db.txt](../../evidence/E5/241830088/e5-01/evidence/make-db.txt) 第 1061 行声明 `main.o: main.c unused.h`；输入 [Makefile](../../evidence/E5/241830088/e5-01/evidence/Makefile) 第 6 行相同。
- [trace/t.14](../../evidence/E5/241830088/e5-01/evidence/trace/t.14) 第 46 行是 Make 对 unused.h 的 `newfstatat` 元数据检查。编译作业及后代没有成功读打开 unused.h，RD 结论限定于本次配置。
- 链接任务的 [trace/t.20](../../evidence/E5/241830088/e5-01/evidence/trace/t.20) 第 71 行写 app、第 82–83 行读 main.o；与数据库第 609 行 `app: main.o` 一致。

完整 trace 为同一次采集的 7 个进程文件，均保持原字节和原始行号。`manual-analysis.json` 的 `analysis_mode=manual`、`provenance_kind=A13_MANUAL_ORACLE` 明示分析来源；该 JSON 供 E5 人工互查使用，不宣称实现了双方共同 finding-report Schema。

## 3. B13 可如何使用

### 复核 E5

1. 固定读取本文件所在的完整交接 commit。
2. 校验公开证据的 SHA256，再按上述文件和行号检查依赖归属。
3. 比较实际/声明依赖并记录接受、建议修改或待确认。

在克隆的 A13 仓库根目录可运行下列只读检查：

```bash
git rev-parse HEAD
python3 - <<'PY'
from pathlib import Path
import hashlib, json
root = Path('evidence/E5/241830088')
manifest = json.loads((root / 'SHA256SUMS.json').read_text())
for relative, expected in manifest.items():
    path = root / relative
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit('SHA256 mismatch: ' + relative)
print('PASS:', len(manifest), 'files')
PY
```

### 对接 MDFixer

按 Pair13 已有约定，MDFixer 后续只消费 `MISSING`。此样例提供的修复目标是 `main.o → config.h`；`main.o → unused.h` 保留为 RD 报告，可由消费方跳过修复。

本次手工元数据未产生真实的 producer Job ID、configuration_id 或自动检测结果。E6 交接时再将自动生成结果映射到双方确认的格式，约定固定仓库/commit/configuration、目标、依赖、声明位置、trace 证据及可读取的 Artifact locator。B13 返回候选补丁时须绑定 base commit 和 configuration，A13 后续在隔离副本中应用并复检。

[双方现有回复](../E2/B13_REVIEW_RESPONSE_2026-10-10.md)将共同 2.0 格式保留为候选；本次 E5 发布未新增双方冻结或互读验收结论。

## 4. 给 DRAFT 环境对接的已测条件

- Linux/amd64、GNU Make、项目编译器、strace；源代码与结果目录可写。
- 项目根路径明确；此样例在容器的 `/evidence` 中 clean build，公开传输的依赖路径使用项目内相对路径。
- 本次 runner 使用 `--cap-add SYS_PTRACE`；运行阶段 `--network none`；按宿主 UID/GID 启动容器以写入证据目录。完整实测参数见 [runner/command.json](../../evidence/E5/241830088/e5-01/runner/command.json)。
- 本次未额外覆盖 seccomp 配置；复杂项目和其他运行环境的跟踪能力仍需分别验证。
- [toolchain.lock](../../evidence/E5/241830088/build-e5-01/toolchain.lock)记录容器实际版本；[来源说明](来源与版本记录.md)记录固定摘要镜像源、Debian 源及本组 3.5 GiB 可见内存策略。
- 本次镜像 ID 仅标识本组 Docker 中已验证的镜像，未发布到镜像仓库。接收方可从固定代码版本重新构建服务镜像；镜像 ID 本身不构成可直接拉取的注册表地址。

## 5. B13 接收确认项

| 项目 | 待 B13 记录的结论 |
| --- | --- |
| 读取版本 | A13 完整交接 commit SHA |
| 文件可读性与哈希 | SHA256 校验是否全部通过 |
| MD/RD 与证据归属 | 接受 / 修改建议 / 待确认，并注明 trace 或声明位置 |
| DRAFT 环境要求 | 可提供 / 差异项 / 待验证 |
| 后续机器接口 | configuration、真实 Job/Artifact、共同格式及 patch recheck 的待办 |

B13 确认后再将实际互读结果、双方固定 commit 和待办回写交接记录。
