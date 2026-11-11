# ADR：独立交付采用原字节离线包，执行和签收分开记录

日期：2026-11-11；241830088；状态：A13本轮采用，待B13确认。

问题：共享编排器内部调用不能证明独立A→B报告交接；B13暂未给本用户开通访问。需确保消费者拿到精确目标项目和未改写的报告，避免旧commit、同数量错边或bool/数值混淆被误接受。

选择：在A13本人云端生产三个独立E11-A运行；不改课程算法，另用独立完整图审计和严格JSON导出。离线包原字节保留 envelope/payload、完整引用、项目Git bundle、源SHA、镜像ID、工具链及哈希。包状态为READY_FOR_DELIVERY_NOT_ACKNOWLEDGED，B13消费输出另行回传并对照，不将B新产物注册到A原job API。

替代方案：仅共享API能先验证编排，却不足以证明独立报告消费；复制并重写JSON容易丢失原哈希和上游标识；假定B拥有项目commit会导致克隆或STALE_REPORT错误。因此选择可恢复base/target的离线包，不要求A13登录B服务器。

校验：原报告schema/kind/status、base/target、job/trace、data与payload严格一致、唯一同任务payload URI、所有sha/整数bytes；导出前拒绝错误或已有输出。审计另核对真实actual/declared图与findings和增量变化。兼容预验固定B13源head和原文件hash，禁网运行、记录orchestrator和draft_image_reused=false。

代价：完整引用和bundle带来较大文件；包内自带hash只能证明一致性，外层归档hash须通过独立交接渠道交换，不能当作来源认证。平面双C源和受限Make规则仍是覆盖边界。外部真实项目、DRAFT环境实际复用和跨机API另验收，不包含在本轮交付准备的PASS中。

验证：本人云端40项测试通过；三场景完整图/引用审计通过；冻结B脚本在A13容器中消费三包并修复重检通过，最终无MD。具体版本、OUT和哈希见个人报告与evidence/E11-E12/241830088。
