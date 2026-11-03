# E8–E10 个人技术决策记录（241830217，A13 / EChecker）

## 背景、问题与限制

课程的 `labs/e8e10/lab.py:scan` 使用全局 `key`（所有 C/H 文件的预处理行、所有 Make 配方、CFLAGS、编译器版本）决定是否刷新：一处局部 include 变化也会刷新 `main.o`、`helper.o` 两个目标。这个策略较保守，确保课程教学样例可解释，但增量收益有限。

个人扩展提出一个可验证的问题：**只改变 `main.c` 或其实际使用的头文件时，能否只刷新 `main.o`，同时仍与不带缓存的 GCC 全量扫描完全一致？**

## 决策：保留课程实现，新增可选的逐目标缓存策略

- 课程的 `scan()`、E8/E9/E10 原命令、BuildChecker 和 B13 补丁逻辑一律不变；独立新增 `labs/e8e10/targetwise_241830217.py`，入口 `scan_targetwise(project, old=None)`。
- 每个目标保存自己的 `target_keys[target]`：该目标当前实际依赖（递归 `gcc -MM` 可获得的项目内 `.c/.h`）的预处理指令及注释边界行、目标自身的 Make 配方、CFLAGS、`gcc --version` 首行。
- 缓存比较时**先检查历史依赖的当前文件**。若签名不变，则复用旧的该目标 `actual`；如果变化，仅对该目标执行 `gcc -MM -MT`。刷新后以新依赖集合更新签名，下一次可复用。
- 不论缓存命中与否，都重新解析 Make 声明图，再计算 MD/RD 发现及 `added/resolved`；不能直接复用旧 `findings`。
- 无目标级历史键、源/头文件缺失、路径不安全、配置不支持时禁止静默复用；缺失源文件实际拒绝为 `COMMAND_FAILED`。保留独立 `schema_version`，不把原课程 `scan()` 报告误当作逐目标缓存。

## 三阶段独立验证的目标

| 阶段 | 与教师基线不同的预期 | 独立核对 |
|---|---|---|
| E8 | 首次刷新两目标；未变化时复用两目标；未被读取的 `unused.h` 改变时仍复用两目标 | MD/RD 边精确匹配，`actual/declared/findings` 等于 `lab.scan(project)` |
| E9 | `main.c` 新增 include 时仅刷新 `main.o`；`helper.c` 新增 include 时仅刷新 `helper.o`；声明变化不刷新实际依赖图 | C0–C3 连续内部 Git 提交；三类集合与全量相等 |
| E10 | 6 个累积变化场景 × 5 次：`unchanged/body/declaration` 刷新 0、`include/header` 刷新 `main.o`、`flags` 刷新两个目标 | 30 对完整 JSON（不仅比较数量），30 行 CSV、6 行中位数统计；可选真 BuildChecker 动态重检 |

`labs/e8e10/test_241830217.py` 另覆盖间接 include、注释边界失效、受影响目标的配方变化、删除源文件拒绝、历史版本不兼容等。`scripts/e8e10/run_241830217.py` 将自主扩展的可重复运行结果保存到个人 `work/`，不读取或修改其他成员证据。

## 反例、代价和适用边界

1. 此策略仍依赖课程已有的 GCC `-MM` 全量依赖采集，**不是 EChecker 论文中的增量 syscall trace 归并算法**。
2. 仅对 `lab.fixture` 的两个显式 Make 对象目标、课程允许的三种 CFLAGS、项目内本地头文件成立。不宣称支持隐式规则、生成头文件、跨目录头文件解析、完整 Make 变量表达式或任意 C 工程。
3. 将 `/*` 和 `*/` 也计入签名以捕捉注释块启闭后激活旧 `#include` 的情况。复杂 C 预处理边界、系统 include 路径与环境变化仍需更完整的依赖模型；不能以此扩展替代生产环境构建正确性证明。
4. 小样例的计时包含 Git HEAD、文件读取、编译器版本调用、Make 声明解析等开销。性能可能低于全量；如实报告中位数，不使用论文加速数据。
5. 运行 E10 时虽然每行比较了全量 GCC oracle，但只有提供 `--dynamic-recheck` 并得到真实 BuildChecker 输出，才能把动态重检记为已完成。GitHub Actions 通过不能代替课程云服务器实测。

## 审查与来源

- 教师提供的 `DevOps_E8_E10_20261031.zip` 操作手册、`lab.py`、`test_profile.py` 为基线；本次不修改基线核心。
- 扩展实现、测试和运行脚本由 ChatGPT 辅助产生，见 `AI_USAGE.md`；个人仍需在课程服务器执行、检查日志和按真实结果填写报告。
- 验收依据为本分支 SHA 及真实 `work/` 路径；没有云端日志前，文档中的云端结果为**待验证**，不预填 PASS。
