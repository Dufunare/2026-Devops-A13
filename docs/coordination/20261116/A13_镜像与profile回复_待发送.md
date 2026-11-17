# A13 → B13：回签确认后的镜像与 profile 回复（待发送）

> 后续进展（2026-11-17）：B13 #32 已合并启用；本人正式教学 E12 及原 de2 镜像签收核验已完成。请以 `../20261117/` 的新报告、待发送回包说明与最新待办为准；下文保留 11/16 当时快照。

已收到B13_给A13_回签确认与余项_20261116.zip（SHA256 b23d13fadf238d6d9a416c48fd37ff493d2e0623b58264c53405bdc565ee0ff4），16份清单全部核验。确认新消费回签、本人连通预验及v2归档回签三项已收口，不重做已通过的预验。C0/C1源码已恢复接收，A13也对你方恢复ZIP独立fsck并比对原tar：上游/C0/C1为152/152/154文件，C0/C1的152/154字节全匹配，保留浅边界；不再以公开fork或另发bundle阻塞。

## 原 E12 成品镜像

已从A13课程服务器原镜像按完整ID docker save导出，未重建、未安装工具：

- 文件：A13_E12_real03_DRAFT_de2ea79e_20261116.tar.gz
- 字节：156689439
- SHA256：3417910047ff2192172745ab5880e7bf09413f9241cfe8bbb4feff49f3006bd2
- image ID：sha256:de2ea79e001d88ce6e40f38cd9d73025af12aeda21269ec6d9170738c36258e3，linux/amd64。
- 对应e12-real-03，job-ad419a2431ee402b9f04babd9be60e57 / trace-1a694e497826474689c53575e441000f；C0/C1保持原592fc6…/b2dda5…，原证据076db4…不变。

**实测工具链：Python 3.13.14、GCC 14.2.0、Make 4.4.1；git和strace均不存在（127）。** 探测在该不可变镜像的只读、禁网、无能力、UID65534容器执行，只查询版本，原ID不变。请先复算文件SHA、实际load、inspect核对ID与工具；不能沿用a84编排器工具链。镜像文件单独私下交付，不进Git。

这意味着原成品不能直接满足当前需git/strace的worker前提。请B13确认明确的新工具齐备DRAFT构建/执行版本：如果补工具，须保留本原件、记录新Dockerfile/依赖/构建及输出验收并生成新ID，作为新一轮运行；不能静默修改旧环境或宣称仍使用原de2 ID，也不能fallback到编排器。尚未记录B13 load结果。

## 旧运行源码绑定边界

进一步找到原overlay和server_run.py：脚本在读取Git HEAD后复制overlay覆盖工作树，image record只写HEAD，没有源码文件hash。当前overlay的4文件与PR17 13f61c…一致；pipeline.py/lab.py/测试与52222b3不同。保存的run2-1931.log是教学job，不是两个真实job，仍不足以证明旧两次真实运行的确切字节。

因此保留历史成功及这一来源边界，不回填为52222b3或13f61c已证明。附两固定Git提交的7份代码候选快照及哈希供阅读，明确不是旧job的运行证明。后续双方新固定版本复跑时，应在执行前后记录真实检出SHA、dirty状态、代码文件hash、输入/profile、实际镜像、argv、job/trace。请241870063补充如有的原始绑定，或在报告中接受该历史边界并以新版本补跑。

## Profile与完整flags

确认分析/修复toml.o←toml.c、make toml_json/make clean、./toml_json空输入stdout严格{}+LF、exit0；向toml.h追加原注释并验证toml.o重新编译，输出不变。仅声明toml.o范围MD消除，完整结果继续单列toml_json→toml.h；注释探针后的目标二进制hash可能相同，不能仅靠hash变化证明是否重编译。strict_sources=false/recursive_scan=false维持原意，补丁只改独立副本Makefile。

原flags_allowed字符串对应旧简化扫描器只读取CFLAGS=的口径；它未解析ifdef下的+=。原GNU Make数据库明确完整CFLAGS为-std=c99 -Wall -Wextra -fpic -O2 -DNDEBUG。旧JSON保持原件不改，不能将旧结果写成完整flags校验。新执行profile需在DEBUG未设、无CFLAGS/CC覆盖条件下，显式使用/校验这一完整有序flags，记录真实编译argv、编译器版本与缓存键。不同DEBUG/覆盖配置应拒绝或单独版本化。

详细语义在A13_tomlc99_profile确认与完整flags.json；该文件是对接口径，不是可直接POST的请求。请B13映射到其版本化profile并回确认，再冻结新版输入。C1变化包括Dockerfile.broken，已与toml.c/toml_extra.h一并登记。

B13#32当前1d041eb…仍Draft（6CI成功）、main1600b59…；正式E12仍等正常Review/最终部署及input-confirmed/server-context。A13不向旧服务提交新版任务。正式时只创建一次正常新job，随后同input/key重放和约定有效差异的同key409，双方保留同job/trace与下载哈希。时间仍暂未确定。本回复及附件供用户转发，未代发。
