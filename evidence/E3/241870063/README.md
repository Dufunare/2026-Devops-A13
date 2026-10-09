# A13 E3 实验材料

成员：241870063

## 文件说明
- md-rd/：MD/RD 实验源码。
- md-rd-report.md：人工判断依据、实际现象及操作失误记录。
- md-、rd- 开头的文件：对应实验日志、输出和退出码。
- c012/：最后一个补充提交的源码导出；本汇总目录不包含嵌套 `.git`，版本历史通过 bundle 恢复。
- c012.bundle：完整 Git 历史，可恢复三个提交。
- c012-evidence/：各版本 SHA、Makefile、构建及运行证据。
- c012-evidence/expected-results.md：人工预期检测报告。
- delivery/：原始新版压缩包及使用相对文件名的 SHA256 校验文件。
- repository-audit.json：整理进 A13 仓库时的材料一致性检查结果。

本页的实验 SHA 属于 bundle 内的实验仓库，并非 A13 仓库的提交 SHA。
日志中的 `/app/work/...` 是实际运行时的历史路径，其他机器请按下方说明新建副本。

本材料验证了样例构建行为，未声称已经运行 BuildChecker/EChecker。

## 实验版本
C0：f72547c269a6fbdd5c5b143c3c2af0bd2765aef0
依赖声明正确，使用 -O0，程序输出 1。

C1：3d272ac863c07570b2f1f189085103f85fb3793c
新增 extra.h 的 include，但未声明该依赖，程序输出 2。

C2：746c642bec52c86b2b965b42b5e0c0bf2b22890a
仅将 -O0 改为 -O2，仍保留 C1 的遗漏依赖，程序输出 2。

## 复现 C0/C1/C2
使用带有 Git、GNU Make 和 C 编译器的 Linux 环境。
原始工具版本见 c012-evidence/c0-compiler.txt 和 c0-make-version.txt。

从本 README 所在目录开始，按顺序执行：

    E3_PACKAGE="$PWD"
    E3_REPLAY=$(mktemp -d)
    git clone "$E3_PACKAGE/c012.bundle" "$E3_REPLAY/c012"
    cd "$E3_REPLAY/c012"

    git checkout f72547c269a6fbdd5c5b143c3c2af0bd2765aef0
    make clean && make && ./app

C0 预期输出 1。继续：

    git checkout 3d272ac863c07570b2f1f189085103f85fb3793c
    make && ./app

C1 的 main.c 修改触发重编译，预期输出 2。继续：

    git checkout 746c642bec52c86b2b965b42b5e0c0bf2b22890a
    make

C2 仅改变编译选项，普通 make 预期不重建。继续：

    make clean && make && ./app

编译日志应使用 -O2，程序输出 2。

## 复现 MD/RD
接着在同一终端执行，使用独立副本：

    cp -R "$E3_PACKAGE/md-rd" "$E3_REPLAY/md-rd"
    cd "$E3_REPLAY/md-rd"
    sed -i 's/^#define VALUE .*/#define VALUE 1/' config.h
    make clean && make && ./app

初始预期输出 1。修改实际依赖：

    sed -i 's/^#define VALUE 1$/#define VALUE 2/' config.h
    make && ./app

make 不重建，程序仍输出 1，体现遗漏依赖。继续：

    make clean && make && ./app

重新构建后输出 2。再验证冗余依赖：

    sleep 1
    touch unused.h
    make && ./app

预期触发编译和链接，但程序仍输出 2。

## 证据解读
程序打印内容与退出码是不同的记录。
make 返回 0 不代表它已经重编译，也不代表依赖声明正确。
历史操作失误见 md-rd-report.md，不应将误录退出码当作构建失败。

## 补充实验
补充材料见 supplement-evidence/README.md。
包含 MODE 命令变化对照、容器环境、Linux 原始跟踪和固定人工报告。
原 c012.bundle 保留三个原始提交；
c012-with-supplement.bundle 包含追加后的五个提交。
