# PR #8：修复恢复与最终合并

日期：2026-10-27（Asia/Shanghai）。同一 PR 的失败及真实拒绝见 ../pr8-rejection-20261027/。

- 修复源码：`9d1712ae5a4feb57afe81943276492262307b1c0`；仅将演示测试预期恢复为0，没有修改版本命令实现。
- 成功 PR Run：[40372248900](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40372248900)。对应 push Run 40372238651 也成功。
- PR CI 实际 checkout：`0ff02f5033b9b71a7d3863a512f8ca21aa64c4db`，是包含修复 head 的临时合并提交，父提交记录见 checked-out-commit.json。与 run head 身份分别保存，不混写。
- 服务测试17/17、独立测试17/17、八门禁8/8；下载后本机重新审计 passed=true，7个唯一trace_id，修复只改变Makefile。
- 原始 Artifact ID12673855568，ZIP SHA256 `7e30da85c4f4b80d50c6d452aa69102e2229bea7c06f58acaf90446e757a1121`；完整ZIP含二进制已另存本机，本目录artifact/保存原字节文本快照。
- [PR #8](https://github.com/Dufunare/2026-Devops-A13/pull/8) 已普通合并：`99cc7e01d4562d2357470ed14585c0d587fb76df`，2026-10-26T17:51:48Z（北京时间2026-10-27 01:51:48）。pr-merged.json 中 merged=true、state=closed；主分支仍受保护。

SHA256SUMS.json 覆盖本目录所有其他文件。原始失败Artifact的历史提交材料仍保持失败时状态；成功Artifact内的报告也保留其触发时状态，之后完成的最终合并证据见本目录pr-merged.json，不能倒填旧Artifact。
