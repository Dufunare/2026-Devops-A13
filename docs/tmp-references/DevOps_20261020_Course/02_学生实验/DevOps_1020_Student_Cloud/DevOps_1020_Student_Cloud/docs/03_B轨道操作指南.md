# B：DRAFT 云主机操作指南

在云服务器上依次完成以下步骤。每个代码框整块执行；重跑时更换 `--out` 目录名。

## 1. 初始化与构建

整块复制，按提示输入本人学号与邮箱：

```bash
cd ~/devops-course/DevOps_1020_Student_Cloud/labs/B-draft
git init -b main
read -r -p "输入学号: " sid
read -r -p "输入提交邮箱: " mail
git config --local user.name "$sid"
git config --local user.email "$mail"
git add .
git commit -m "Initialize B teaching reference lab"
python3 scripts/lab_cloud.py doctor
```

整块复制：

```bash
python3 scripts/lab_cloud.py build --out work/build-01 --build-timeout 1200
echo "BUILD_AND_TEST_EXIT_CODE=$?"
```

预期：`24 passed`，退出码为 `0`。服务容器通过宿主机的 Docker socket 执行构建。

## 2. E5：真实失败与提示

整块复制：

```bash
python3 scripts/lab_cloud.py e5 --out work/e5-01 --build-timeout 600
echo "E5_EVIDENCE_EXIT_CODE=$?"
cat work/e5-01/iter-01/result-retry.json
cat work/e5-01/iter-01/prompt-error-driven.txt
```

预期：构建在 `RUN make` 处失败，日志出现 `make: not found`，`build_exit_code` 为 `1`。脚本保存这次失败并生成提示文件，脚本自身退出码为 `0`。

将 `prompt-error-driven.txt` 全文发送给对话模型，取得修复后的 Dockerfile。再使用 `prompt-context-driven.txt`，比较加入项目说明后得到的候选。保存两次提示和原始回复。

## 3. 保存自己的模型候选

整块复制，进入编辑器：

```bash
mkdir -p work/candidate
nano work/candidate/Dockerfile
```

未安装 nano 时，执行 `sudo apt-get install -y nano`。将 Dockerfile 正文粘贴到编辑器，去掉 Markdown 围栏。按 Ctrl+O、Enter 保存，Ctrl+X 退出。

修复要求：保留 FROM 摘要、WORKDIR、COPY、RUN make 和 CMD，增加安装构建依赖的命令。

也可用 SFTP 上传 Dockerfile。将原始回复保存为 `work/candidate/model-response.txt`，填写候选来源记录。多个候选按 candidate-01、candidate-02 编号，并记录最终选择原因。

## 4. E6：构建与验证

使用自己保存的候选，整块执行：

```bash
python3 scripts/lab_cloud.py e6 --candidate work/candidate/Dockerfile --out work/e6-own --build-timeout 600
echo "AUTO_BUILD_EXIT_CODE=$?"
python3 scripts/verify_e6_b_evidence.py --run-dir work/e6-own/evidence
```

也可使用包内已保存的 DeepSeek 候选，整块执行：

```bash
python3 scripts/lab_cloud.py e6 --replay --out work/e6-replay --build-timeout 600
echo "REPLAY_EXIT_CODE=$?"
python3 scripts/verify_e6_b_evidence.py --run-dir work/e6-replay/evidence
```

两种方式选一种，在报告中记录候选来源。

|检查项|预期结果|
|---|---|
|第一轮构建|MISSING_MAKE|
|第二轮构建|build_exit_code=0|
|镜像|保存 image_id，并运行该镜像|
|程序运行|退出码 0，输出 `hello E3`|
|输出校验|output_matches=true|

## 5. E7：五个真实场景

使用包内候选运行全部测试，整块执行：

```bash
python3 scripts/lab_cloud.py gate --replay --out work/e7-01 --build-timeout 600
echo "E7_GATE_EXIT_CODE=$?"
cat work/e7-01/gate/gate-result.json
```

预期：门禁退出码为 `0`，服务单元测试和以下五个场景全部 `passed=true`。

|场景|预期行为|
|---|---|
|正常候选|构建成功，程序输出匹配|
|输出不符|验证失败|
|无效候选|在构建前拒绝|
|候选构建失败|停止程序验证|
|运行超时|返回 TIMED_OUT，清理运行容器|

使用自己的候选时，将 `--replay` 换为 `--candidate work/candidate/Dockerfile`。测试脚本通过修改 `CMD` 和 `RUN make` 注入故障；候选需保留这两项指令。

超时场景在 CMD 中加入 10 秒延迟，验证预算为 1 秒。查看 `fault-injection.json` 和清理结果。

## 6. 自主任务与提交

1. 补充一项失败测试，重新构建镜像并运行门禁。
2. 按 04 指南完成 CI、失败拦截和修复恢复。CI 使用仓库中保存的候选文件。
3. 按 05 清单提交报告、代码和运行结果。
