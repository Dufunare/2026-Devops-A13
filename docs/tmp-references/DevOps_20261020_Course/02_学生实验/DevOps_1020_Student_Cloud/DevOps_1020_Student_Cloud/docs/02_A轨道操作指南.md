# A：BuildChecker 云主机操作指南

在云服务器上依次完成以下步骤。每个代码框整块执行；重跑时更换 `--out` 目录名。

## 1. 初始化自己的实验仓库

整块执行，按提示输入学号和提交邮箱：

```bash
cd ~/devops-course/DevOps_1020_Student_Cloud/labs/A-buildchecker
git init -b main
read -r -p "输入学号: " sid
read -r -p "输入提交邮箱: " mail
git config --local user.name "$sid"
git config --local user.email "$mail"
git add .
git commit -m "Initialize A teaching reference lab"
python3 scripts/lab_cloud.py doctor
```

预期：环境自检通过。

## 2. 构建与单元测试

整块复制，镜像构建可能需数分钟：

```bash
python3 scripts/lab_cloud.py build --out work/build-01 --build-timeout 1200
echo "BUILD_AND_TEST_EXIT_CODE=$?"
```

预期：`15 passed`，退出码为 `0`。

## 3. E5：从原始证据理解 MD/RD

整块复制：

```bash
python3 scripts/lab_cloud.py e5 --out work/e5-01
echo "E5_EXIT_CODE=$?"
cat work/e5-01/evidence/program-output.txt
grep -n '^main.o:' work/e5-01/evidence/make-db.txt
grep -n 'config.h' work/e5-01/evidence/trace/t.*
```

预期结果：

|检查项|结果|
|---|---|
|程序输出|`1`|
|Makefile 声明|`main.o: main.c unused.h`|
|实际读取|trace 中存在成功打开 `config.h` 的记录|
|缺失依赖 MD|`main.o → config.h`|
|冗余依赖 RD|`main.o → unused.h`|

打开 trace，找到读取 `config.h` 的进程，再与 `main.o` 的声明对照。

## 4. E6：自动检测、修复副本、复检

第一段整块复制。缺陷样例启用 --fail-on-findings，预期退出码为 1：

```bash
python3 scripts/lab_cloud.py e6 --out work/e6-before
echo "BEFORE_EXIT_CODE=$?"
cat work/e6-before/evidence/findings.json
```

第二段整块复制。--fixed 只修改独立副本中的 Makefile，原始 fixtures 保留：

```bash
python3 scripts/lab_cloud.py e6 --fixed --out work/e6-after
echo "AFTER_EXIT_CODE=$?"
python3 scripts/verify_e6_evidence.py --before work/e6-before/evidence/findings.json --after work/e6-after/evidence/findings.json
```

预期：修复前有两条错误，修复后 `findings=[]`、退出码为 `0`，输入哈希仅 Makefile 发生变化。

保存 `actual-graph.json`、`declared-graph.json`、`processes.json`、`make-db.txt`、`trace/` 和构建日志。

## 5. E7：完整门禁

整块复制：

```bash
python3 -m unittest discover -s tests/e7 -v
python3 scripts/lab_cloud.py gate --out work/e7-01
echo "E7_GATE_EXIT_CODE=$?"
cat work/e7-01/gate/gate-result.json
```

预期：独立判定测试 `6 tests OK`；完整门禁退出码为 `0`，八项检查全部 `passed=true`。

|检查项|预期行为|
|---|---|
|服务单元测试|全部通过|
|原始样例运行三次|每次得到相同的 MD/RD 集合|
|修复后的样例|错误集合为空|
|构建失败|返回 FAILED|
|多输出任务|返回 UNSUPPORTED|
|运行超时|返回 TIMED_OUT|

故障场景中，程序返回 `1`、测试结果为 PASS，表示程序按预期识别了故障。

## 6. 自主任务与提交

1. 阅读 `fullcheck.py`，说明进程归属和路径过滤的处理方式。
2. 补充至少一项测试，重新构建镜像并运行门禁。
3. 按 04 指南完成 CI、失败拦截和修复恢复。
4. 按 05 清单提交报告、代码和运行结果。
