# GitHub CI 与合并门禁

目标：每次提交自动构建和测试；测试失败时阻止合并，修复后恢复通过。

## 1. 仓库和登录

每组新建一个空 GitHub 仓库，关闭 README、LICENSE 和 .gitignore 初始化选项。使用免费个人账号时，选择公开仓库以启用分支保护。

在已经初始化的 A 或 B 仓库中，整块复制：

```bash
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git --hostname github.com
```

出现 device code 后，在电脑浏览器打开 https://github.com/login/device，输入验证码完成授权。

整块执行，按提示输入本组仓库的 HTTPS Git 地址：

```bash
read -r -p "自己的空仓库 HTTPS Git 地址: " repo_url
git remote add origin "$repo_url"
git push -u origin main
gh repo view --json nameWithOwner,visibility,url
```

## 2. 正常 CI 和保护

第一次 push 自动触发已包含的 workflow。整块复制：

```bash
gh run list --limit 5
```

从输出中找到运行 ID，整块执行并按提示输入：

```bash
read -r -p "本次运行 ID: " run_id
gh run watch "$run_id" --exit-status
echo "CI_EXIT_CODE=$?"
```

通过后配置 main 分支保护：

|设置|取值|
|---|---|
|必需检查|A：e7-a-quality-gate；B：e7-b-quality-gate|
|分支需保持最新|strict=true|
|管理员受同样约束|enforce_admins=true|
|合并方式|通过 PR|
|审批人数|required_approvals=0|

先核对实际 App ID。整块复制：

```bash
repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
sha=$(git rev-parse HEAD)
gh api "repos/$repo/commits/$sha/check-runs" --jq '.check_runs[] | {name, conclusion, app_id: .app.id, app_slug: .app.slug}'
```

配置文件使用 App ID `15368`，与输出核对；如有不同，修改 JSON 中的 `app_id`。A 组执行：

```bash
gh api --method PUT "repos/$repo/branches/main/protection" --input ../../ci/A-main-protection.json --jq '{checks: .required_status_checks.checks, strict: .required_status_checks.strict, enforce_admins: .enforce_admins.enabled}'
```

B 轨道整块复制：

```bash
gh api --method PUT "repos/$repo/branches/main/protection" --input ../../ci/B-main-protection.json --jq '{checks: .required_status_checks.checks, strict: .required_status_checks.strict, enforce_admins: .enforce_admins.enabled}'
```

配置成功后，输出应包含对应检查名称，且 `strict`、`enforce_admins` 均为 `true`。

## 3. 创建故意失败 PR

两轨道均先整块复制：

```bash
git switch -c e7-gate-reject-demo
```

A 仅执行：

```bash
cp ../../ci/rejection-demo/A/test_ci_reject_demo.py services/buildchecker/tests/
git add services/buildchecker/tests/test_ci_reject_demo.py
```

B 仅执行：

```bash
cp ../../ci/rejection-demo/B/test_ci_reject_demo.py services/draft/tests/
git add services/draft/tests/test_ci_reject_demo.py
```

两轨道均整块复制：

```bash
git commit -m "Demonstrate CI rejection with wrong test oracle"
git push -u origin e7-gate-reject-demo
gh pr create --base main --head e7-gate-reject-demo --title "Demonstrate E7 merge rejection" --body "故意写错版本返回值预期，验证 CI 失败与禁止合并，保存证据后修复。"
read -r -p "刚创建的 PR 编号: " pr_num
gh pr checks "$pr_num" --watch
```

预期：CI 失败。打开测试日志，找到 `version` 预期返回 `1`、实际返回 `0` 的断言。

## 4. 实际验证禁止合并

整块复制，预期合并命令退出码非零：

```bash
mkdir -p work/ci-rejection
gh pr merge "$pr_num" --merge > work/ci-rejection/merge-rejection.log 2>&1
merge_code=$?
cat work/ci-rejection/merge-rejection.log
echo "MERGE_ATTEMPT_EXIT_CODE=$merge_code"
gh pr view "$pr_num" --json state,mergeStateStatus,headRefOid,url > work/ci-rejection/PR.json
gh api "repos/$repo/branches/main/protection" > work/ci-rejection/protection.json
gh run list --branch e7-gate-reject-demo --event pull_request --limit 3
```

预期：PR 状态为 `OPEN / BLOCKED`，合并命令被主分支策略拒绝，退出码为 `1`。

选择失败的 PR 运行 ID 后整块复制：

```bash
read -r -p "失败的 PR 运行 ID: " fail_run
gh run view "$fail_run" --log-failed > work/ci-rejection/failed-check.log
gh run download "$fail_run" --dir "work/ci-rejection/artifacts-$fail_run"
```

## 5. 修复后恢复

A 仅执行：

```bash
cp ../../ci/rejection-demo/A/fixed/test_ci_reject_demo.py services/buildchecker/tests/
git add services/buildchecker/tests/test_ci_reject_demo.py
```

B 仅执行：

```bash
cp ../../ci/rejection-demo/B/fixed/test_ci_reject_demo.py services/draft/tests/
git add services/draft/tests/test_ci_reject_demo.py
```

两轨道均整块复制：

```bash
git commit -m "Correct version success oracle"
git push
gh pr checks "$pr_num" --watch
gh pr view "$pr_num" --json state,mergeStateStatus,headRefOid,url
```

如果刚 push 还显示旧检查，等十几秒重查。确认是最新提交全部通过后：

```bash
mkdir -p work/ci-recovery
gh run list --branch e7-gate-reject-demo --event pull_request --limit 3
read -r -p "最新通过的 PR 运行 ID: " pass_run
gh run download "$pass_run" --dir "work/ci-recovery/artifacts-$pass_run"
gh pr view "$pr_num" --json state,mergeStateStatus,headRefOid,url > work/ci-recovery/PR-before-merge.json
gh pr merge "$pr_num" --merge
gh pr view "$pr_num" --json state,mergedAt,mergeCommit,url > work/ci-recovery/PR-merged.json
git fetch origin
```

预期：CI 恢复通过，PR 合并成功。A 组 `16 passed`，B 组 `25 passed`，均增加了一项门禁测试。

保存失败和恢复两次的 artifact、合并拒绝日志及最终合并记录。artifact 保留 14 天，下载后用 SFTP 备份到电脑。

重新登录 SSH 后，重新设置 `repo` 和 `pr_num`。已有远程仓库时，用 `git remote -v` 查看地址。
