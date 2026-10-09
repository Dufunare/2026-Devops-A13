# E3 补充实验说明

成员：241870063
本补充沿用原有项目，保留原 C0/C1/C2 及其证据。

## 命令变化的行为对照

基线提交：
3d7d36aca7487c2668ae56c7f4ee9242fe257a3b

该提交让程序支持 MODE，默认 MODE=0。
编译选项：-O2 -Wall -Wextra。
实际程序输出为 2，退出码为 0。

仅修改编译选项的提交：
5a94d5c0d9aa65f07cb7e8cbbfc0af30a8dc7d67

相对基线仅增加 -DMODE=7。
保留旧产物运行普通 make：未重建，程序输出 2。
清理并重新构建：程序输出 9。
两次程序退出码均为 0。

人工预期来源：MANUAL_ORACLE。
上述实际观察分别保存在 mode-baseline、mode-incremental、
mode-clean 开头的日志、输出和退出码文件中。
两个 command.log 是 make -n -B main.o 的命令快照。

该补充保留了 main.o 缺少 extra.h 依赖的人工预期。

## 环境与 Linux 原始跟踪

environment.txt：实际采集时的容器系统、架构与工具版本。
linux-trace-2UnSx0/source/：跟踪构建使用的源码快照。
linux-trace-2UnSx0/trace.log.*：各进程的原始跟踪。
linux-trace-2UnSx0/make-database.txt：Make 解析出的规则。
linux-trace-2UnSx0/relevant-accesses.txt：相关访问摘录。
md-rd-oracle.json：带源码快照哈希的人工固定发现报告。

本次记录中，Make 查询 unused.h 的属性；
编译器 cc1 成功打开 config.h。
这些是原始观察，尚未代表完整的自动依赖推断结果。

## 复现补充实验

从实验包根目录开始，按顺序执行：

    E3_PACKAGE="$PWD"
    MODE_REPLAY=$(mktemp -d)
    git clone "$E3_PACKAGE/c012-with-supplement.bundle" "$MODE_REPLAY/c012"
    cd "$MODE_REPLAY/c012"

    git checkout 3d7d36aca7487c2668ae56c7f4ee9242fe257a3b
    make clean && make && ./app

预期输出 2。保留产物，继续：

    git checkout 5a94d5c0d9aa65f07cb7e8cbbfc0af30a8dc7d67
    make && ./app

预期不重编译，仍输出 2。继续：

    make clean && make && ./app

预期使用 -DMODE=7 编译，输出 9。

## 独立副本复跑记录
已从 c012-with-supplement.bundle 克隆到新的临时目录进行自检：
- MODE=0 基线：输出 2，退出码 0。
- 切换到仅增加 -DMODE=7 的提交，保留产物：输出 2，退出码 0。
- 同一提交清理重建：输出 9，退出码 0。

证据见 replay-baseline、replay-incremental、replay-clean 的日志和退出码；
版本见 replay-baseline.sha、replay-change.sha。
这是本人在独立副本中的复现自检，不是另一位组员的验收记录。
