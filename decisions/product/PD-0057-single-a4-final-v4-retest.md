# PD-0057：一次 A4 剩余异常界面连续补测

2026-10-20 Asia/Shanghai。用户对具体弹窗明确回复：

> 批准 A：按 V2 做这一次连续补测（推荐）

批准范围为 reviews/CP7_F3_FINAL_UI_R1_2026-10-20/a3/NEXT_V4_DECISION_PACKET_V2.md，SHA256 a116e0811994c34c63b4b2105d224752a6a659a3cd03c8fa00f9c9e57d254812，独立范围复核 a01fd0940d9f89390be7bd14edacdc811766068f7097e0dfd81a6c00cc879215。

这是 PD-0056 禁止自动第四实例的一次明确例外。新 base /private/tmp/finweb-final-ui-r1-a4-20261020，candidate/runtime；私有 Unix PG55443/TCPoff，DB finweb_final_ui_r1a4/schema final_ui_r1a4；API127.0.0.1:8012，UI127.0.0.1:5181。现有依赖及最终449产品源原样，七控制源仅 A3→A4 身份/授权/pin字面替换，复用已执行的cleanup_once，不改产品/SQL/金融方法/旧迁移/原fixture。新源、最小权限和命令先冻结并独立复核，root唯一运行/浏览器执行者，最多3子代理。

一次初始化/启动，六次既有虚构API seed，一个新账号/root，固定71B项目CSV，现金100→105。恰两次报告操作：op1实际提交后ACK丢失→UNKNOWN→一次同操作查询恢复真实全局成功，作为V4必要前提，不计新增覆盖；同一活App继续op2真实提交前故障→settled UNKNOWN且旧全局成功消失，中英文只渲染，再一次同操作查询缺失仍UNKNOWN。12表/原金融版本/现金105不变、报告0→1→1，允许合法READONLY租约。不得第三操作、自动重试、替代操作、隐藏上传或DOM/React注入。

浏览器固定用户指定 FinWeb-Test Chrome4/ext a8fbbf89-3d57-422b-842c-a1e79005a9d4，一个新代理技术页；两次仅用户手动选项目CSV，期间不刷新/导航/退出/换组合。无自动chooser或扩展文件权限变化。新技术登录可正常设置或替换此测试profile的127host会话；换端口不等cookie隔离，不读取旧cookie或用户密码。新生成技术凭据仅runtime0600，通过工具变量填同loopback登录，不打印/写项目证据。

保留V1/A2/A3数据和原证据，原IAB/正常::1/其他profile/旧UNKNOWN不触。成功或中断都按身份回收仅本轮UI/API/PG并保存缺失，不盲kill、不自动第五实例。普通业务/个人虚构版仍保留；无真实数据、依赖安装、提交/发布、外部联系、夜间任务/caffeinate/reset恢复或人类关口代批。唯一剩余只指这两项异常UI slice，非全CP7/FullF1/D3/HG4。
