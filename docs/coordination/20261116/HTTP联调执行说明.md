# HTTP 新任务联调执行说明（241830088，2026-11-16）

代码：labs/e11e12/http_evidence_241830088.py；仅Python标准库，旁边需要handoff.py。支持e11-a/e11-b/e12。三者使用e11e12-1 API；E2的finding-report 2.0是另一条互读契约。

## B13先给出的条件

授权SSH用户名、确认宿主回环端口、最终执行代码40位SHA、成功DRAFT镜像不可变sha256、工具链、服务器/course/data下的repo/candidate/fixed_report实际路径，以及可恢复的完整C0/C1。真实项目还需双方确认profile与验收范围。不要将本地Mac路径传给远端API。若仍用旧编排器版本，回执明确draft_image_reused=false。

本目录的B13_E12_输入模板.json只是已知include样例SHA的待填模板，路径包含B13_CONFIRM，确认后另存为实际请求；不是可直接运行的真实项目或已就绪B13路径。

## 授权后执行

在本机终端保持隧道，SSH_USERNAME替换为B13实际回复的用户名：

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18080:127.0.0.1:8081 SSH_USERNAME@47.110.38.55
```

另一终端从仓库根目录运行，input-confirmed.json填写已确认的服务器路径/完整SHA，OUT必须全新：

```sh
python3 labs/e11e12/http_evidence_241830088.py --base-url http://127.0.0.1:18080 --request input-confirmed.json --out work/b13-http-NEW-RUN --timeout 1200 --context server-context.json
```

server-context.json是双方另行提供的源码/镜像/工具链和项目来源记录；它是操作方陈述，客户端不会把它当服务器自动证明。客户端每次生成新的随机幂等键；不要为凑证据复制旧job或改写响应。

## 验收与回传

成功输出含job_id、trace_id、downloaded_count。保存input.original.json、http/下请求原字节、响应头/体、每次轮询、terminal-state、artifact-index、downloads、summary和SHA256SUMS。E12下载件应含candidate.patch、repair/recheck和报告；不是只有artifacts清单。

客户端核对新提交请求hash、完整base/target、job/trace、阶段身份、每个引用SHA/bytes与响应头。它只做传输与引用校验；成功不自动证明检测语义正确、补丁合理、真实项目范围成立或DRAFT镜像被使用。

B13另保留同一job/trace的服务器请求、原始result/状态、容器inspect、镜像摘要、执行命令、退出码和工具链。双方对照相同下载件SHA，并在正式HTTP回执中填写双方记录路径/归档SHA及验收结论，再更新formal_pair_acceptance。客户端不会擅自将该字段改为true。

失败目录保留，先修复原因再换全新OUT重跑。完成后关闭SSH隧道。

## A13已完成的预验边界

2026-11-16 Mac经SSH访问A13本人云端临时API：全新E11-A job，85次HTTP交换、81文件实下载并核验，原件归档。course-generated，不含补丁，不是B13正式E12或真实项目验收。首次默认用户启动失败及重试成功记录均保留；临时服务与隧道已关闭。
