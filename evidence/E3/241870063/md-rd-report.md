# E3 MD/RD 实验记录

本记录来自人工检查源码和实际执行 make、app 的结果。
尚未代表 BuildChecker/EChecker 的检测输出。

## 源码与依赖声明
- 实验目录：md-rd/
- main.c 包含 config.h，程序打印其中的 VALUE。
- main.c 未包含 unused.h。
- Makefile 声明：main.o 依赖 main.c、unused.h。
- 因此，main.o 缺少 config.h 依赖，并冗余声明了 unused.h。

## MD：遗漏 config.h
1. 初始 VALUE 为 1，构建后的程序输出 1。
2. 将 config.h 中的 VALUE 改成 2。
3. 普通 make 显示 Nothing to be done，退出码为 0。
4. 程序仍输出 1，退出码为 0。
5. 清理并重新构建后，程序输出 2，退出码为 0。
结论：修改真实依赖未触发重编译，导致使用旧产物。

证据：
- md-after-config-change-build.log / .exit
- md-after-config-change-output.txt
- md-after-config-change-app.exit
- md-clean-rebuild-clean.log / .exit
- md-clean-rebuild-build.log / .exit
- md-clean-rebuild-output.txt
- md-clean-rebuild-app.exit

## RD：冗余声明 unused.h
1. 完成上述重建后，程序输出为 2。
2. 执行 touch unused.h，仅更新该文件的时间戳。
3. make 再次编译 main.c 并链接 app，退出码为 0。
4. 程序仍输出 2，退出码为 0。
结论：未使用的头文件时间戳变化触发了多余构建。

证据：
- rd-build.log / .exit
- rd-output.txt
- rd-app.exit

## 操作失误补记
以下根据实验时的终端输出补记：
- 曾将退出码误写到 ..baseline-build.exit，随后误保存了 cat 失败的退出码。
  该次记录的 1 不能作为 make 构建失败的依据。
- 曾将 printf 与 ./app 粘在同一行，造成重定向路径错误，程序未运行。
  后来单独重新运行程序，已得到输出 2、退出码 0。
