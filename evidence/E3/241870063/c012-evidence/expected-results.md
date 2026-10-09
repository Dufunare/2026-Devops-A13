# E3 C0/C1/C2 人工预期报告

本文件记录人工判断的预期结果，尚未代表 BuildChecker/EChecker 的实际检测输出。
依赖判断范围为项目内文件；系统头文件不计入以下 MD/RD 结论。

## C0
- SHA：f72547c269a6fbdd5c5b143c3c2af0bd2765aef0
- 编译选项：-O0 -Wall -Wextra
- main.o 所需项目文件：main.c、config.h
- Makefile 已声明上述依赖；app 依赖 main.o。
- 预期：无 MD、无 RD。
- 程序预期输出：1；退出码：0。

## C1
- SHA：3d272ac863c07570b2f1f189085103f85fb3793c
- 相对 C0：新增 extra.h，并在 main.c 中包含它。
- 编译选项与 C0 相同。
- main.o 所需项目文件：main.c、config.h、extra.h。
- Makefile 仍只声明 main.c、config.h。
- 预期：MD 为 main.o 缺少 extra.h；无 RD。
- 程序预期输出：2；退出码：0。
- main.c 的修改触发了本次重编译，不能据此认为依赖声明完整。

## C2
- SHA：746c642bec52c86b2b965b42b5e0c0bf2b22890a
- 相对 C1：仅将编译选项 -O0 改为 -O2，源码不变。
- 预期：仍有 main.o 缺少 extra.h 的 MD；无 RD。
- 增量检测应识别配置变化，按接口约定拒绝旧配置基线或重新计算。
- 普通 make 未触发重编译；之后已执行清理并用 -O2 重建。
- 重建后程序预期输出：2；退出码：0。

## 证据
- c0/c1/c2-build.log：实际编译命令。
- c0/c1/c2-build.exit：构建退出码。
- c0/c1/c2-output.txt：程序输出。
- c0/c1/c2-app.exit：程序退出码。
- c2-incremental-build.log：仅修改编译选项后的普通 make 结果。
- c0-compiler.txt、c0-make-version.txt：C0 的工具版本。
- 各版本的 Makefile 和 SHA 均分别保存。
