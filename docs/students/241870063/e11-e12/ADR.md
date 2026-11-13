# 决策记录（E11–E12 · 真实项目适配）

编号：ADR-E11E12-001 ~ 003　｜　日期：2026-11-13　｜　作者：241870063

---

## ADR-001：把硬编码的检测口径改成可传参数（profile），而不是复制一份实现

**背景**

原实现的接口等于"只接受教学样例"：根目录必须恰好 `main.c/helper.c` + `config.h`，Makefile 必须有 `main.o:`/`helper.o:` 显式规则，`CFLAGS` 只允许三种写法，`./app` 必须输出 `1`、改 `config.h` 后输出 `2`，全量检测固定跑 `make clean`/`make app`。真实项目几乎不可能同时满足。

**候选方案**

1. 复制一份 `lab.py` 给真实项目用（分叉维护）。
2. 把真实项目改造成教学样例的形状（改项目，不改工具）。
3. 把上述常量抽成 profile 参数，默认值保持原样。

**采用方案与原因**

选 3。理由：① 不制造第二份实现，避免两套逻辑漂移；② 不改真实项目，证据才是"真实项目"的；③ 默认值不变意味着课程原版 10 项测试与 E8–E10 的 16 项测试仍然有效，评审能直接验证"没有偷改判据"。

**输入输出字段**

- 输入：请求 JSON 的 `profile`（`units`、`config_file`、`config_after`、`expected_output`、`expected_output_after`、`build_target`、`clean_target`、`flags_allowed`、`recursive_scan`）。
- 输出：`result.json.profile` 回写实际使用的口径；`incremental-report.json`、`validation/validation.json` 的判定与此一致。

**兼容性与测试**

- `None` → `DEFAULT_PROFILE`，`declarations/scan/validate` 行为逐行等价。
- 测试：`test_default_profile_unchanged`（回归）、`test_scan_maps_profile_units`、`test_unadapted_project_is_rejected`、`test_validate_uses_profile_expectations`。
- 代价：`scan` 的指纹在 `recursive_scan=true` 时会包含子目录文件，跨口径的历史缓存不可复用——这是显式选择，报告里没有把它当成加速比。

---

## ADR-002：镜像与 APT 源的环境适配采用"环境变量覆盖 + 默认值不变"

**背景**

本机到 Docker Hub 完全不通：`registry-1.docker.io:443 i/o timeout`。样例的 `Dockerfile.broken` 首行是 `FROM python:3.13-slim`，DRAFT 第一轮因此被判为 `INFRASTRUCTURE`，而 `auto_build` 要求第一轮必须是 `MISSING_MAKE`，于是整条 DRAFT 失败。同一问题也出现在环境镜像的 `docker:28.5.1-cli` 层。

**候选方案**

1. 给 docker daemon 配 `registry-mirrors`：改共享配置、需重启 Docker、影响同机其他同学。
2. 把 `prepare.py` 的默认镜像改成 DaoCloud：CI 也会被迫走第三方镜像站。
3. `prepare.py` 保留原默认值，新增 `E11E12_SAMPLE_BASE` / `E11E12_SAMPLE_DIGEST` / `E11E12_APT_MIRROR` 环境变量；镜像构建时用 `--build-arg` 覆盖 CLI 层。

**采用方案与原因**

选 3。理由：不碰共享的 daemon 配置；GitHub CI 行为零变化（不设变量即原样）；与项目既有做法一致——`environment/Dockerfile` 本来就用了 DaoCloud 基础镜像 + 清华 APT/PyPI 源 + 固定 digest。

**权衡**

- 样例的 C0/C1 提交 SHA 会因重新生成而变化，因此**不能与 11-08 包内证据（`8f56e1b…`/`dbc6e56…`）或 11-11 CI 证据（`72c929e6…`/`3a720e6e…`）混引**，报告里注明批次。
- 固定 digest 从 `70729b46…` 换成 `f82c9645…`（后者本机已验证可解析），两者同为 `python:3.13-slim`，仅 manifest 不同。

**验证**

`docker run --rm course-e11e12:241870063 docker --version` 通过；`Dockerfile.broken` 与 `candidate.Dockerfile` 首行 tag 部分一致（DRAFT 的 `prepare_candidate` 会强制校验）。

---

## ADR-003：DRAFT 的 iter-01 语义——用"固定 digest 的 broken"，不用候选的新增指令

**背景**

`prepare_candidate()` 的返回值容易被误读为"修复后的 Dockerfile"。实测其返回的是 `[候选的 FROM, *broken 其余指令]`，即**把候选的固定 digest 套在 broken 上**；候选文件里新增的 `RUN` 行只用于第二轮构建。也就是说：iter-01 与 iter-02 的差异恰好是"新增的 RUN"，这才使失败归因唯一。

**决策**

- 保留该语义，并把"iter-01 不含新增 RUN"写成显式测试（`test_accepts_digest_pin_with_added_run` 断言 `apt-get update` 不在返回串里）。
- 由此推出：**broken 的首行 tag 不能依赖公网**，否则 iter-01 会因为拉不到镜像而变成 `INFRASTRUCTURE`，掩盖"缺 make"这一真实故障——这正是 ADR-002 的直接动机。

**约束（对真实项目的含义）**

候选 Dockerfile 必须：单 stage；`FROM` 与 broken 同 tag 且带 `sha256` 固定 digest；原指令（WORKDIR/COPY/RUN make/CMD）按序保留；只允许新增 `RUN` 行。三条都有对应测试兜底。
