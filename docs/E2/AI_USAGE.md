# AI_USAGE

## 2026-09-26：E2 配对契约整理

### 工具/模型
ChatGPT，用于资料归纳、契约草案、样例和验证代码辅助生成。

### 输入依据
E2 课件；四篇论文中与跨服务输入输出有关的内容；B13 固定 commit `af194c40ffd1394fb56cc9f5b2367b7feffb5a3b`；B13 的 A13_MESSAGE.md。

### AI 建议
接受 B13 公共 Job；补齐 A13 FULL/INCREMENTAL 字段；baseline 绑定 commit+configuration；finding 保留 location/evidence；使用 repository-backed Artifact locator；candidate patch 验证前不视为正式 commit；不在 E2 虚构服务部署和论文运行结果。

### 人工仍需确认
ptrace 最终容器参数需实测；B13 对新字段需可追溯确认；Artifact 双向互读需实际执行；成员需用自己的 GitHub 身份审查和留下真实贡献。

### 关联
Issue #1、B13_DELIVERY.md、A13_E2_INTERNAL_GUIDE.md、contracts/、scripts/validate_e2.py。

### 验证边界
validator/tests 通过只表示契约样例自洽，不表示 BuildChecker/EChecker 已实现。
