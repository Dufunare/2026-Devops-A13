# E11 E12 最终组合与全项目补充验收

执行源码：`dadcc74ad13c3460644486a5b1411318d6b1c9c9`。基于 PR18，并整合 PR17 的 real08 head `b3d9c733de7f624b0844eb26acb146a40f91b910`，保留 PR15/16/17 历史。后续文档提交不替换实际运行 SHA。

## 已完成

- 课程 Linux 云主机独立目录：67/67 E11/E12 单测通过。首次64项中一项旧 mock 未生成新扫描输出而失败，原日志保留；组合分支修正模拟边界并断言 `scan_in_image` 的镜像与标签，未改成员检测算法。
- `work/full-project-02`：用真实 C1 `b2dda5513fe4a7d250493528800fe425cae459a5` 和 real08 DRAFT `sha256:da792170afbe9cdf3075f3973ac4746c723a285cf2976992b6f29ce65141da23` 执行 make all，观察6个目标。修复前5条MD，修复后完整 findings=[]。只有副本 Makefile 改变。
- 修改 toml.h 后，6个输出的mtime均增长；strace包含4个源文件的成功compiler exec，完整六项flags与程序输出{}加LF均核验。前后全量与头文件探测3次实际容器操作的CID、不可变镜像、inspect、退出及清理均核验。
- 原始完整包：15,858,611 bytes，SHA256 `198e103d58908f1269acde4564a90a6c63eae9ccc3e44caf3bc30eff9db1b252`，688项manifest全部通过，包含完整trace/Make数据库/源码bundle/失败与成功日志。大包留在本地课程证据目录，不重复塞入Git历史。
- B13部署方成员一已对241830088原API任务 `job-123a2b27e494473586a2c5a984ab914f` / `trace-67a686ea138b46ae9d7cbf1c16e3b4db` 正式回签；2216产物逐字节与客户端相同，无需重跑。原API任务仍是toml.o范围，不回填成此次make all结果。
- 实际CI：E7、E8–E10、E11/E12、v2互读在dadcc74全部通过；E11/E12 run https://github.com/Dufunare/2026-Devops-A13/actions/runs/44131848306 。

## 复现补充验收

在已有课程编排容器中，仓库挂载为/course、宿主docker socket已按课程入口挂载，并使用有该目录权限的宿主UID执行：

```sh
python3 labs/e11e12/accept_full_project_241830088.py \
  --repo /course/data/real-project \
  --out /course/work/whole-project-new-output \
  --image sha256:da792170afbe9cdf3075f3973ac4746c723a285cf2976992b6f29ce65141da23
```

OUT必须不存在，代码须先提交。源码bundle和完整C0/C1项目bundle在原件包内。此脚本复用已有DRAFT，属于独立全项目验收，不是新建API任务，也不更改双方冻结profile。

## 待协作完成

1. 241870063继续负责自己已承诺的profile报告绑定与A→B原始报告实际消费，当前双profile文件SHA一致不能替代正式消费通过。
2. PR19最终组合需独立Review与正常合并，随后按依赖顺序将集成基线合入main。本人不批准自己的PR，不绕过保护。
3. B13成员二、三个人核对可沿用已成功的同job/trace分开登记；不因此要求重复运行本人任务。

## AI辅助说明

Codex辅助整合冲突解决、补充验收脚本、测试、云端命令、证据审计及报告整理。成员241870063的real08实现和B13服务端运行不计为241830088独立原创；原件失败、局部范围和历史dirty状态均保留。没有代发B13消息或修改其服务。
