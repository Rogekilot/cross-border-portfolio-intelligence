# HG4 真实数据可用性准备草案

**DRAFT / NOT_READY — 2026-10-19，Asia/Shanghai。**

本文件由独立 Designer 在 PD-0045 允许的后续只读准备范围内编写。它是 PM
后续正式关口包的输入，不是 Gate Review Package、产品决定或 HG4 通过请求。
本次只核对现有文档与代码；未读取真实持仓或真实数据文件内容，未访问数据库、
HTTP、浏览器或外部来源，未下载、准入、安装、运行模型或修改产品。

**建议先批准一个有界的真实来源 web 接入增量及其数据使用范围，再取得实际
真实数据 UAT 证据，最后请求 HG4 决定。现在可以决定下一项工作的范围，不能
把 CP7 的虚构数据技术退出直接签成 HG4 通过。**

## 1. 关口究竟要回答什么

[PD-0013](../decisions/product/PD-0013-hg1-absorbs-hg4-ux-prototype-approval.md)
明确覆盖原 PRD §38.5 的 HG4 UX 映射：HG1 已吸收 IA、可用性与渐进解释的原型
审批；HG4 保留的是**真实市场数据、导入和计算链条存在后，虚构原型无法回答的
可用性验证**。不再要求主人重选已批准的设计方向，也不重复 HG1。

沿用 [PD-0041](../decisions/product/PD-0041-hg3-approved-with-conditions-and-cp6-start.md)
已批准的 FULL_NAV/GLOBAL_PRODUCT、现阶段 US-only 真实验证、明确标注的
SPY/USD 总回报 ETF 代理路线。它们不是待决定项。真实来源/历史准入、每个组合的
有日期主基准选择、CN/HK 日历条件及 66 项历史 HG3 支持证据缺口仍各自成立。

本稿采用的当前完成依据是 [CP7-D PM 验收](../reviews/CP7_D_PM_ACCEPTANCE.md)
与 [CP7 synthetic exit](../reviews/CP7_SYNTHETIC_EXIT.md)。旧 HG4 UX 标题按
[关口语义勘误](../reviews/CP7_D_GATE_AUTHORITY_RECONCILIATION.md)解读，不改写
已封存的历史证据。HG4 判断属于主人；独立技术/设计结论与 PM 技术验收不能替代它。

## 2. 当前已完成什么，尚缺什么

| 项目 | 当前可核对事实 | HG4 尚不能据此证明的事 |
|---|---|---|
| CP7 A–D | 人工输入、登录隔离、私有 PG 持久化、不可变流水/策略/基准状态、CSV 导入报告和导出、四 surface 框架中的核心可用视图与证据路径在本地虚构范围技术接受；Scenario/AI 明确 deferred | 真实标的、真实行情/行动/日历、实际历史统计和真实来源下的任务可用性 |
| 最终版本 | D 最终 53 路径清单 SHA256 为 `5a57190d41bdf8df7c6286e765bb1f3865a2934ed995aa35443169d3ce411ca8`；PM 最终 2618 run / 2616 pass / 2 E0 opt-in skip / 0 fail | 这些是既有执行者的已记录结果；本稿未重跑，也不新增真实数据测试通过数 |
| 当前 web 模式 | `SavedPortfolioRequest.mode` 仅接受 `LOCAL_SYNTHETIC_ACCOUNT`；本地启动器明确启用 saved synthetic；Analytics context 固定核验虚构 quotes/calendar，输出标注 synthetic | 还没有真实来源组合的 web 模式；仅准入 SPY 或修改 banner 不能补齐这个接入层 |
| 数据覆盖 | D 验收明确：虚构价格/日历仅 2026-01-02，真实 benchmark/risk-free catalogs 为空；本稿未打开其数据文件核验内容 | 多日期收益、完整期间八线归因、真实风险统计、真实收益曲线的正向 web 展示 |
| 证据/历史 | 旧保存对象、CSV 报告和证据保持各自版本；D 有真实本地进程重启和重现证据 | 新 Analytics 为按需计算，不是跨未来引擎/来源替换的持久化结果档案；真实来源保留及重放策略仍需契约和执行证明 |
| 设计复核 | 最新独立复核 PASS_WITH_LIMITS，UX01/02/03 在实测范围关闭，EN/zh、三深度、390px、证据/焦点等有独立实图 | 没有真实数据的新一轮设计 UAT；完整无障碍审计及记录的工具限制没有被抹去 |
| OCR | PD-0009 和规范 addendum 将 OCR 列为 V1 第三条导入路线 | 当前 A–D 接受清单没有可据以认证的实际 OCR 管线/UAT 证据；CSV 完成不等于 OCR 完成 |

代码依据：[account_routes.py](../src/web_api/account_routes.py)、
[account_dev.py](../src/web_api/account_dev.py)、
[analytics_context.py](../src/web_api/analytics_context.py)、
[analytics_composer.py](../src/web_api/analytics_composer.py)。
这些是代码/验收记录的只读观察，不是本次运行时探测。

## 3. 推荐的第一段真实数据验证范围

**建议：本地、内部、US 标的、USD 报告币种，采用项目构造的非敏感测试流水与
经过准入的真实市场数据。** 它沿用已批准地区路线，不请求主人上传个人持仓，
也不把“真实行情”混称为“主人的真实资产”。测试流水来源与市场数据来源应分别
标记；不能把一个总 `synthetic` 标志改成 false 就宣称整条链条真实。

先复用合格的既有 admitted release 是候选顺序，**不是本稿已证实存在足够的
合格 release**。需要在另行授权后核对指定版本、权利/用途、区间、来源确认、
日历和历史覆盖。旧 HG2 的“构造 AAPL 流水＋真实 US/ECB 数据”只能作为候选
样例方向，不证明当前 web 已可使用，也不证明其历史足够。

短区间可以先验证真实估值、现金流、行动处理、拒绝状态和解释路径；正向风险
统计必须另有达到现行方法充分性要求的历史。不得因为短样例无法算出数值而
降低阈值、虚标 3Y、改用常数利率或裁掉缺失日期。
[既有数据决策包 §4](../reviews/HG3_DATA_DECISION_PACKET.md)已明确其短样例
不能建立数值 Sharpe/beta 就绪性。

这里建议的是**先期验证增量**，不是删除跨境 V1、OCR 或其他未实现要求。若主人
未来仅审一段 US 非敏感真实数据 UAT，正式包必须明确该段能支持的判断与仍未
完成项；未经主人明确限定/条件化的关口决定，不将局部结果报为完整 HG4 或 V1。

## 4. 主人早晨可以决定的具体事项

下表均为提议，未记录新的选择。建议按 1 → 2 → 3 → 4 顺序处理；不把这些
准备决定合并成一次 HG4 签字。

| 待决定事项 | 选项 | 推荐及确认后的可开工边界 |
|---|---|---|
| 1. 下一实施增量 | A：授权本地真实来源 web 接入、测试与独立复核；B：暂缓实施，仅查看已接受的虚构版本 | **A**。先冻结小范围技术/验收契约，接入现有真实服务门控。授权须明确允许哪些数据/元数据读取；代码授权不自动授权下载、源准入、采购或个人文件读取 |
| 2. 首轮 UAT 输入 | A：项目构造非敏感流水＋合格真实市场数据；B：主人真实组合/脱敏账单试点；C：只有市场数据研究，暂不跑完整任务 | **A**。先隔离产品接入问题。B 后置，另明确文件名单、读取人、脱敏、保存/删除、是否允许截图/日志及外发；不请求券商密码或线上账户访问 |
| 3. 真实市场数据取得方式 | A：仅核验并复用指定既有准入版本，缺项停；B：批准逐来源清单的新增获取/准入；C：暂不使用真实数据 | **先 A，缺什么再列 B 的具体请求**。每项写来源/文件、版本、日期区间、行情/行动/利率语义、许可用途、联网/下载动作与预算。未核验前不承诺现有源够用；不把公开可访问等同使用权通过 |
| 4. 统计样例与验证长度 | A：短期真实交互验收先行，另补合格长历史统计样例；B：等全套统计历史满足后再一起验收 | **A 作为推进顺序**，但短样例仅能获得其实际覆盖的证据；在正向风险/历史曲线缺口未补前不能据此请求无条件 HG4 通过。方法阈值沿用 registry，用户只决定允许的数据覆盖/获取范围 |
| 5. UAT 组合的主基准 | A：合格目录中由主人明确选 SPY/USD gross-TR 代理并确定生效日期；B：明确无基准；C：暂不选择 | 对需要相对统计的**指定测试组合**推荐 **A（以目录合格为前提）**。这不是重选已定 SPY 路线，也不替所有组合默认选择。B/C 合法，但对应依赖结果保持拒绝，不能声称正向相对统计已验收 |
| 6. OCR 的后续实施范围 | A：单独规划/授权 OCR 实施增量，落实已定隐私与 confirmed-input 要求；B：先做上述真实来源人工/CSV 增量，保留 OCR V1 缺口 | **先 B，再 A**，以避免把个人图片和第三方识别权限混进首个真实来源接入。B 是实施顺序建议，不是豁免 OCR，也不重问是否应有图片政策；本稿不提出供应商、模型或安装授权 |

已有 FULL_NAV、US-only 和 SPY 路线均不在此重问。USD Treasury 13-week coupon
equivalent、HKMA/ChinaBond 候选方向也已有决定；需要补的是适用语义、条款、
发布日历、真实历史及正式准入，而非重新选择利率方向。
[PD-0039](../decisions/product/PD-0039-cp4-benchmarks-risk-free-scope-selection.md)、
[PD-0040](../decisions/product/PD-0040-cp4-short-history-fallback-and-hkd-cny-risk-free.md)。

## 5. 新真实来源 web 通路必须保留的契约

1. **服务端模式与来源绑定。** 定义与本地虚构模式清楚分开的接入契约，明确
   测试流水/真实市场输入的不同来源属性。每个结果绑定拥有者、组合/账户 scope、
   不可变流水版本、as-of、reporting currency、准入 release、calendar、来源及
   文件摘要、方法/策略与基准选择版本。旧虚构对象不自动升级，不用当前 head
   替换历史对象的来源。具体接口/存储设计由实施增量审定，本稿不创造新 API 枚举。
2. **复用真实服务的门控。** 不绕过价格/公司行动确认、F8B 检测、合成来源拒绝、
   registry 和数据充分性检查。`performance_service` 的 synthetic refusal 与
   `risk_service` 默认 `allow_synthetic=False` 保持；不能用测试 opt-in、空
   suppressions 或纯引擎直连冒充真实服务合格。
3. **来源生命周期与重放。** 明确 admitted release 不可变/可取回的保证、缺失或
   摘要变化的拒绝、未来引擎变化的重现能力边界；若需持久化新 Analytics，另有
   加性设计、权限与迁移复核。不得让页面“重现成功”暗含不存在的长期档案。
4. **身份与输入纪律。** 继续先判拥有者与版本可见性，再读取来源/解码/计算；
   他人/不存在资源等价拒绝、CSRF/Origin、幂等确认、历史隔离及旧证据兼容性继续
   测试。真实证券必须明确解析，不能让 SYN-A/SYN-B 的输入限制变成猜 ticker。
5. **呈现保持诚实。** 同时显示实际区间、币种、scope、状态/缺口、来源与新鲜度；
   首次真实标的长名称、来源标签、行动说明和长历史证据应再次实测，而非引用旧图。

门控代码依据：[performance service](../src/performance_service/service.py)、
[risk service](../src/risk_service/service.py)。现有实现可复用与“真实 web 接入已完成”
是两件事；上述全部仍是待实施/待执行条件。

## 6. 真实数据依赖与验收矩阵（提议，全部待执行）

`BLOCKED` 表示前置数据/接入未满足；`NOT_EXECUTED` 表示未执行该真实数据
验收。它们不是失败，也不是通过。当前 synthetic 证据可以保留为回归基线，不能
填入本表的真实执行栏。

| ID / 任务 | 真实数据或实现前置 | 要收集的实际验收证据，含正向与拒绝 | 当前真实执行状态 |
|---|---|---|---|
| R01 模式/来源识别 | 新真实来源 web 契约、合格 release、非敏感测试流水 | 主人能区分真实行情、构造输入和旧虚构版本；旧对象不迁移；来源不匹配/摘要变化拒绝；API 与 UI 证据相符 | BLOCKED / NOT_EXECUTED |
| R02 导入与校正 | 实际 US identity/reference、允许的测试 CSV/人工流水、来源 namespace | 解析真实证券与账户/币种/时间；歧义/缺字段不猜；预览、校正、整批隔离、明确确认、幂等与导出；旧版本仍可查 | BLOCKED / NOT_EXECUTED |
| R03 估值及 partial | 指定日期 RAW 价格、现金/应收、需要时合格 FX | FULL_NAV 与 priced-holdings partial 分开；缺价/FX 不变零；排除 holdings/components 数量、CASH/币种/金额/原因与单位可见；unknown basis 不变收益 0 | BLOCKED / NOT_EXECUTED |
| R04 真实 freshness | 按市场价格与 FX 各自的 observation/retrieval 信息、交易/发布日历 | 市场休市、较旧报价、缺历史、未知抓取时间分别表达；刷新页面时间不替来源时间；真实节假日/非同步收盘不会被总“最新”标签掩盖 | BLOCKED / NOT_EXECUTED |
| R05 收益与现金流 | 连续合格历史、交易/结算、费用/税/分红/拆股证据及确认策略 | 指定区间收益、现金流影响、现行 FIFO 收益/基础；缺 before-snapshot、未确认行动或来源角色不匹配拒绝且无虚假数值；保留非税务/broker lot 差异说明 | BLOCKED / NOT_EXECUTED |
| R06 归因 | 实际多日期价格、FX/行动、必要期前快照 | 精确每日八线与期间归因/自购入分解区分；Local price effect 与 Price–FX interaction 独立；引擎分摊值、恒等关系及原始证据由 Quant/独立测试核验 | BLOCKED / NOT_EXECUTED |
| R07 主基准/相对结果 | 合格 SPY/USD gross-TR 代理历史、RAW closes/分红/行动、明确 dated primary selection | 代理费率/跟踪差异说明；从未选择/明确无基准/已选择三态；变更后旧结果仍保留旧选择；缺基准不触发偷换窗口或默认 SPY | BLOCKED / NOT_EXECUTED |
| R08 绝对/相对风险 | 足够真实回报/基准历史、现行频率/日历与方法 registry | 实际区间/频率/样本数/阈值；3Y 拒绝与 MAX_AVAILABLE 的 X/Y 独立证据，真实状态可仍不足；too young/gap/zero capital 与 missing benchmark 分开 | BLOCKED / NOT_EXECUTED |
| R09 利率依赖风险 | 已准入 USD Treasury 13-week coupon-equivalent 序列及适配语义、发布日历/覆盖 | Sharpe/Sortino/downside/alpha 的实际所用 rate 引用、缺日/语义不合格拒绝；无常数替代；HKD/CNY 源未满足时对应结果仍 unavailable | BLOCKED / NOT_EXECUTED |
| R10 暴露与 Insights | 真实 security metadata、FULL_NAV policy 引用、CP5/CP6 输入证据 | 最大证券与 listing/cash bucket 区分；分类未知不补齐；无 ETF look-through 假象；未填个人策略不生成个人越限；对应历史 66 缺口逐 claim 查覆盖再补独立预期 | BLOCKED / NOT_EXECUTED |
| R11 真实历史图 | 另立结构化 series/evidence/replay 契约、足够可用历史 | 点值/日期/币种/缺口/调整基准可追溯；曲线不插造，区间不静默裁剪；鼠标/键盘定位和窄屏日期/数值有真实数据证据 | BLOCKED / NOT_EXECUTED |
| R12 语言/深度/证据 | 新候选的实际长名称、来源与正向/拒绝结果 | Overview/Portfolio/Analytics 按 Value→Performance→Exposure→Risk/Insights 完成任务，Scenario/AI 仍明确 deferred；EN/zh × 三深度 × per-claim 切换，common caveat 适用范围清楚、局部限制保留、Professional pins/完整绑定/Evidence 可达 | BLOCKED / NOT_EXECUTED |
| R13 窄屏/键盘/可恢复性 | 同一冻结候选、授权新本地测试身份、390px 与桌面 | metric 标题/scope/值/状态/关键限制同屏可读；Tab/Enter/Escape/焦点返回；日期输入、资源拒绝、恢复、下载分别实际操作；不以 DOM 设置值或旧截图替代 | BLOCKED / NOT_EXECUTED |
| R14 身份/持久化/历史 | 新模式的 owner scope/存储设计、私有授权环境 | 两用户越权/不存在等价拒绝、退出私有事实清除、物理重启、旧 synthetic/新 real-market 对象不混、不可变历史/导出/复现实际相同；新迁移若有独立审阅 | BLOCKED / NOT_EXECUTED |
| R15 OCR 第三导入路线 | 独立 OCR 增量及 PD-0009 的隐私/证据/确认前置 | Upload→Extract→Resolve→Stage→Review→Confirm→Commit；低置信/歧义/缺失/冲突/重复有独立提取词汇；只有确认后的 staged batch 可写/可重放；取消不改账本 | 无当前可认证的实际管线/UAT 证据；NOT_EXECUTED |

此矩阵不要求为 US-only 首轮样例强行引入 CN/HK 真实源或 CNY 报告币种。需要
这些能力时另满足既有 FX、来源与日历条件；不能把 US 真实验证写成跨境真实
验证完成。无障碍的屏幕阅读器、缩放/对比度等若未实际检查，也应单独列
NOT_EXECUTED；当前设计通过不自动扩展到全套认证。

## 7. OCR 与个人数据不能隐含处理

[PD-0009](../decisions/product/PD-0009-ocr-assisted-portfolio-ingestion-added-to-v1.md)
和 [OCR 规范](../specs/OCR_INGESTION_ADDENDUM.md)是已批准 V1 要求。旧原型允许
模拟提取，这不构成真实 OCR 成功。当前短期路线应将它作为明确未完成工作保留，
由 PM 在正式范围/退出条件中处理，不能用“HG1 已通过”或“CSV 已完成”消除。

**已决定的方向不能重问。**
[PD-0011 §4](../decisions/product/PD-0011-hg1-round-3-supersedes-round-2.md)
已经要求 Priority C 的实施计划包含 **source-image retention、redaction/access
及 deletion policy**，并实质回应旧 OCR-OQ-2/3；同一决定确认了提取置信度与
metric sufficiency 分离、confirmed staged batch 才是确定性重放输入。
PD-0011 完整替代 PD-0010；其后
[PD-0020 §7.1](../decisions/product/PD-0020-phase-b-architecture-and-sequencing.md)
保留这些实质要求，[B0b 实施计划 §15.3](../reviews/gates/PHASE_B0B_IMPLEMENTATION_PLAN.md)
将 OCR 架构与该政策列为后续专门技术规划。不得把旧 addendum 的全部 OQ 原样
重列为“主人尚未决定”，也不得拿旧 PD-0010 的授权状态覆盖后续决定。

**尚不能认证的是具体落实与执行。** 本次核对的当前 CP7 计划/验收和 web 路径
没有提供可据以认证的实际 OCR 管线或执行证据。后续专门增量应查明已有政策的
具体版本与落实状况，再只针对仍缺的保存时限/位置、访问角色与脱敏规则、删除
范围/机制及日志证明、凭据区域隔离、第三方识别/跨境权限、来源区域/置信度/
确认人记录、identity resolution 与 confirmed-batch 重放逐项补证；本稿不
声称这些细项全部从未设计，也不把已有方向当作新授权。需要主人决定的是仍缺的
具体保管/访问方案、文件与服务使用权限，而非是否应遵守上述政策。

未经明确授权不读取任何主人图片/账单，不把真实截图上传外部识别服务。
提取置信度与 AVAILABLE/LIMITED/INSUFFICIENT_DATA 不是同一词汇；未确认候选
不进入账本。实际隐私政策符合性与 OCR UAT 目前均为 NOT_EXECUTED。

## 8. 建议证据采集与主人 UAT 条件

以下仅为后续执行计划，**本次没有新建或执行测试脚本**：

- **开始前冻结：** 获得第 4 节明确授权；记载候选 source/test/config 清单、既有
  synthetic 原始证据清单与数据许可/准入范围；仅将允许的非敏感数据加入新证据。
- **独立数值基线：** Quant 为 R03–R10 各可展示 claim 选实际样例、手推/独立
  预期、精确 tolerance 和拒绝条件；沿用方法，不由界面编写者临时定阈值。
  与 66 项旧 inventory 逐项关联，新增覆盖只关闭实际复核的项目。
- **实际技术执行：** 作者与独立复核者分开；用现有测试工具覆盖新 mode 的
  request→owned revision→source release→服务门控→输出→evidence/reproduce；
  PG、进程重启和共享浏览器串行。保存原始失败/跳过、执行者、版本与新候选 hash。
- **实际设计执行：** 独立 Designer 使用自己新建的授权本地 tab/session；每个
  观察步骤先捕获、保存、打开检查原字节截图，再下 UX 结论。保存实际 MIME、
  视口/语言/深度、scope/日期、步骤和发现。工具不可执行就注明具体
  NOT_EXECUTED，不用旧图、作者图或日志代替自己的视觉证据。
- **证据目录：** 建议另建新的 real-data UAT evidence 目录、run manifest 与
  README，记录候选/data release/原始文件摘要/方法/基准/策略/修订号及截图引用；
  不覆盖本夜 D 的 28 张 HOLD、17 张复核图或旧 proof。避免把会话/token/个人
  账户信息写进截图或报告；真实个人样例如后续获准须另有受控证据方案。
- **主人实际任务：** 明确辨认数据模式/日期与测试组合；完成一次输入或 CSV
  校正并确认；辨认 NAV 与 partial/unknown；读取一条收益、一条风险及其限制；
  找到所用主基准/政策/数据窗口；打开证据并重现；切换语言/深度；查历史并退出。
  任务记录实际完成、误解、阻塞和主人原话，不以设计者解释代替主人操作。
- **未覆盖的主人能力：** 若真实 broker 文件/OCR、跨币种或长历史统计不在本轮
  可执行范围，正式包逐项展示，不能预先记录“主人接受此残余”。可提出条件化
  审查范围，最终由主人决定是否足够，未答不视为批准。

## 9. 推荐推进顺序与停止条件

1. **先由主人决定范围与读取/执行权限。** 当前夜间授权只允许本稿，不启动真实
   来源接入、数据检查/下载或 UAT。
2. 在获准的指定元数据/文件范围内核验真实 source/rights/release、calendar、
   action confirmation、基准/利率语义与覆盖清单；不足项给具体补件/获取请求。
3. 实现并独立审阅真实来源 web 契约及不可变证据/服务门控；保留旧虚构路径和历史。
4. 用非敏感 US/USD 样例先跑 R01–R06、R10、R12–R14；合格长历史/基准/利率齐备
   后补 R07–R09、R11 的正向结果及拒绝，OCR R15 保持单列实施与验证状态。
5. 冻结同一候选，完成实际 PG/API/浏览器/设计与主人 UAT，形成正式 HG4 包；
   主人明确决定前 HG4 保持未批准。若关键样例被数据或工具阻塞，保存证据，
   不把不足视为通过，继续可独立完成的已授权事项。
6. CP8/CP9 只按各自依赖和后续明确授权推进；本稿不改变其关口，也不把夜间
   “准备接口/测试矩阵”延伸为正式实现。部署、外部展示/商业权利、生产身份与
   安全验收及后续 human gates 分开处理。

## 10. 何时才适合请求 HG4 决定

目前不能请求 HG4 通过，至少还缺：

1. 主人明确的真实来源接入/UAT 范围与数据使用授权。
2. 能实际服务所选 claim 的合格真实 release、来源/行动确认、日历、历史、
   基准选择和利率语义/覆盖证据；未满足的依赖有准确拒绝与残余清单。
3. 已实现并独立复核的真实来源 web 通路；不是将虚构对象改名，也不是只有数据源。
4. 真实数据的正向/拒绝/恢复、独立数值预期、历史重放与当前界面实际证据；
   曲线及 OCR 等未完成 V1 要求明确列出，不冒称被原型或 CSV 覆盖。
5. 主人在真实数据任务上的实际 UAT 记录，以及 PM 按既定规范组织的正式
   14 项关口包。局部范围/未完成能力是否可条件接受必须由主人明确决定。

**当前结论：虚构范围 CP7 技术退出已接受；真实来源 web 接入、真实数据依赖与
真实 UAT 尚未就绪。推荐批准下一有界工作范围，HG4 审批随后单独进行。**
