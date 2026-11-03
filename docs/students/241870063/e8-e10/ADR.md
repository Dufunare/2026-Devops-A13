# 决策记录（E8–E10，A 组 EChecker 方向）

## 背景与约束

课堂只覆盖受限 C/Make 样例：两个翻译单元、项目内头文件、显式规则、简单变量、三种 CFLAGS。论文还包含增量系统调用跟踪归并和更完整的命令推断，本教学实现不复现该规模。本次要满足四点：未变化输入复用历史图；include、配方、配置变化时保守失效；用独立采集路径（BuildChecker 的 strace 全量检测）交叉核对对象目标；每条结论都能追溯到本次 `work/` 下的 `OUT`。

## 选择与替代方案

- **历史图键（key）**：取预处理指令行、Makefile 配方行、CFLAGS、编译器版本四项。这四类变化会改变 `gcc -MM` 的读取结果或编译行为；普通函数体、注释变化不改变 key，因此可以复用。
- **失效策略**：key 一变，刷新全部对象目标（保守刷新）。替代方案是按目标精确失效，但需要更细的边级指纹，课堂子集未实现，且容易漏判。
- **真实图来源**：`gcc -MM` 作为主路径；E8 和 E10 额外调用既有 BuildChecker（clean build + `strace` + `make -p` 解析），把 `actual-graph.json` 投影到 `main.o`/`helper.o` 做交叉断言。两条采集路径独立，避免只信一条。
- **声明图**：只解析显式 `target: deps` 和简单变量展开；遇到 `%`、`|`、未知变量或未支持的 CFLAGS 直接抛 `UNSUPPORTED_*`，不猜测、不静默跳过。
- **A 组不生成补丁**：补丁生成、`STALE_REPORT` 拒绝和事务式 `validate` 属于 B 组 MDfixer 轨道，本报告不声称实现。

## 代价与覆盖范围

- 保守刷新会多编译、多扫描，小样例上的增量耗时可能比全量更慢（`performance-summary.csv` 的 `full_over_inc` 可以小于 1），如实记录，不套用论文的加速倍数。
- 只支持显式规则和三种 CFLAGS；隐式规则、`.d` 文件、声明图距离、LLM 提示生成均未实现，属于学生扩展任务。
- BuildChecker 与 GCC 只比较对象目标的投影，不比较 `app` 链接目标，避免不同投影混用造成假一致。

## 验证命令与实际证据

- 服务器仓库：`/root/241870063/buildchecker`，镜像 `course-e8e10:241870063`（ID 见个人报告）。
- E8：`work/e8-A-manual.mWtztX`，依次得到 `BASELINE_PASS`、`BUILDCHECKER_BASELINE_PASS`、`REUSE_PASS`。
- E9：`work/e9-A-manual.*`，内部提交 C0→C1→C2→C3；C1 复用、C2 刷新并新增 `MISSING extra.h`、C3 消除两条 MD。
- E10：`work/e10-A-manual.xez3qv`，30 行矩阵全部 `equal=True`，`gate.json` 的 `passed=True`，最终 BuildChecker 无 `MISSING`。
- 单测：`python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v`，结果见个人报告。
