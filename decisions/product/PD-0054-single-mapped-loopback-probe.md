# PD-0054：一次 mapped-loopback 本地监听探针

2026-10-20 Asia/Shanghai。用户对本对话单次授权弹窗直接回答：

> 批准一次监听探针（推荐）

问题明确绑定冻结《PROBE_ONLY_DECISION_PACKET》推荐 A：仅一次 AF_INET6 / SOCK_STREAM 监听探针，固定 ::ffff:127.0.0.1:5180，设置 IPV6_V6ONLY=0，bind/listen 各最多一次，2秒协作预算及 socket timeout，随后关闭。协作预算不是内核或文件操作的硬截止；IPV6_V6ONLY 字段只代表请求设置，不冒充读回值。

不 accept/connect/HTTP/DNS，不读取 cookie、凭证或数据库，不改网络配置、不重试、不回退。冻结源码、清单和独立 GO_TO_ASK_ONLY 复核保持原字节。root 先保存本决定和精确 GO，再在官方工具许可范围执行一次；O_EXCL attempt 文件消耗本次逻辑调用，即使尚未 bind 也不能自动再试。失败或收据不完整如实保留。

即使 PASS，也仅证明当次本地 bind/listen/close，不保留端口，不证明 Node/Vite、浏览器 canonical host 或 host-only cookie 隔离。通过后只准备后续浏览器隔离验证方案并另报用户决定；本次不创建第三个候选/stage/数据库，不启动 API/UI，不导航或开展 cookie 实验。

正常 zz3 / R1虚构试用继续运行；已确认的虚构主线体验接受范围不扩大。原环境和 zz2/TT1 UNKNOWN 不查询、不刷新、不重试、不放弃、不替换；既有受保护源码、历史证据与未提交工作保留。最终 V3/V4 仍未完成。夜间任务保持暂停，不启用 caffeinate、不使用额度重置；不含安装、外部/真实数据、付费、消息、提交、推送、部署或 HG4 等人类关口。

冻结包：reviews/CP7_F3_FINAL_UI_R1_2026-10-20/a3-proposal/GO_TO_ASK_PACKET_V2.json
SHA256 6ae2d6fca40c61a9e7460411dd6f3a3a6e5a125064dd0f46da666998e2c9bd44。
独立复核：reviewer/GO_TO_ASK_REVIEW_V2.md
SHA256 ce6cacdc6374d100b2ff752ea7e7d17aa95bda068013a9cf46543cd587eda073。
