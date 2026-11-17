# F3 本地虚构版 API 接入契约 v1.1

2026-10-20 Asia/Shanghai。独立设计复核 `883b0799…45ec` 已通过，F3D01 在设计层关闭；实际实现和测试另行验收。

本契约的完整端点、严格字段和错误码由以下两份冻结文本共同定义；补充 A 优先于首稿中被它替换的读取实现：

- [API、权限、传输与运行方案](../reviews/CP7_F3_EVIDENCE/design-v1/CP7_F3_API_TECH_PLAN.md)，SHA `ade38e74…ccb67`。
- [纯读取与操作溯源补充 A](../reviews/CP7_F3_EVIDENCE/design-v2/API_PURE_READ_ADDENDUM_A.md)，SHA `4e3cb696…482f5`。

显式 F3 profile 替换整个保存组合路由集；缺省应用仍使用原模式。身份来自原有 HttpOnly 会话，POST 保留 Origin、CSRF、严格模型及请求大小限制。上下文、当前代次、权限、CP5 服务选择和连接由服务端持有；浏览器不能提供发行者权限或回调。

| 类别 | 约定 |
| --- | --- |
| 能力 | `finweb.guarded_profile/1`、`F3_FICTIONAL_CP5`；要求显式期初日期，估值日来自固定虚构来源。 |
| 已提交写入 | HTTP200，`finweb.guarded_http/1` / COMMITTED；规范载荷是精确 UTF-8 `response_json` 及其 SHA，按原 Snapshot/Workspace/Csv 模型再验证。 |
| 不确定结果 | HTTP202 / UNKNOWN；只有组合/操作/核对元数据，不含金融结果、暂存值或“已回滚”断言；仅手动原操作重试或对账。 |
| 读取/导出 | 当前 READ/EXPORT 租约，验证原归档和保存快照；使用原生流水/持仓/FIFO/CSV 来源投影，不调用 World、金融服务或 insight 重算。 |
| 归档 | `finweb.guarded_archive/1`；保留 issued/response/envelope 精确 JSON 字符串与 SHA。`generation` 为原签发代次，`admission_generation` 为当前访问代次。 |
| 重现 | POST 空对象；`finweb.guarded_reproduce/1`，固定 `portfolio_id/operation_id/status/detail/issued_sha256`，只有 REPRODUCED 可显示成功；需当前独立重现权限。 |
| 创建响应丢失 | GET `/api/v1/creation-operations/{operation_id}/reconcile`，服务端据会话身份推导根，验证 CREATE 类型；缺失仍 UNKNOWN。 |
| 未支持功能 | 历史分析、旧 packet、真实数据、访客在 F3 profile 下明确不可用；不回落到旧 composer 或旧存储。 |

创建、流水、偏好、CSV 解析/预览/提交/报告与导出，以及归档读/导出/重现/核对的全部路由见冻结端点表。当前 READ 代次可高于原签发代次，不改写历史原文。列表不宣称跨根原子性；元数据枚举不等于载荷权限。

客户端对规范原文字节作 WebCrypto 校验，身份/根/版本/视图切换后再检查请求有效性。金融数值继续由现有引擎签发，界面不计算替代结果。内存中的未提交草稿在刷新后丢失，已经提交的结果从当前账户元数据重新发现。

本契约仅用于新私有 PostgreSQL、`127.0.0.1:8003` API 和 `127.0.0.1:5174` UI 的虚构版接线与试用准备。既有数据、安装、提交、部署及人工关口条件有效；夜间任务保持关闭。

## F3D02：实际 API 暴露的策略范围兼容修正

作者 A1 实际创建被 F2_POLICY_DIFFERS 拒绝，1项失败、7项未运行。主代理随后只读核验新库 portfolio、gw_operation、gw_artifact、ledger_event 均为0行。原 F2 SQL 只接受绑定具体根的 PORTFOLIO 虚构策略，与本契约固定 GLOBAL_PRODUCT 虚构上下文不兼容；不能通过修改 Python 参数或伪造每组合发行权限解决。

原方案“F3 SQL 仅增加三个元数据函数”在此明确修正：仅在本轮新私有 F3 实例，安装器还须对实际 gw_check_artifact 的一个策略范围谓词作精确扩展。原 F2 文件、其源哈希及旧实例保持不变。先核对完整旧 SQL 哈希、已安装函数签名、owner、security、search_path、prosrc和单次替换位置；差异即停止。保留旧 PORTFOLIO/根匹配分支、策略与上下文完整相等、SYNTHETIC_CANDIDATE 来源及所有原生问题、金融载荷、根、流水、发行、哈希和当前权限检查。

新增分支只接受完全相等的八字段固定对象：FULL_NAV、SYNTHETIC_CANDIDATE、F3 fictional local trial only、f3-fictional:1、GLOBAL_PRODUCT、项目固定 product_id，以及 null portfolio_id/account_id；不接受任意产品级策略，不记为用户确认的真实资本策略。应用没有安装或发行权限。安装前后函数定义、哈希及实际执行者须保存。

此为已授权本地虚构接线中的兼容实现修正，需独立源差异复核与实际 API/PG 复测后才能记为关闭；不扩大真实数据或人工关口授权。
