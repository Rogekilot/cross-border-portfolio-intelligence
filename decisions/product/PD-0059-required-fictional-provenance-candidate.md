# PD-0059：批准新的隔离虚构强制来源候选

2026-10-20 Asia/Shanghai，用户对已完成独立复核的 NEXT_ACTION_DECISION_PACKET_V1 明确回答：

> 批准 A：新隔离候选实现与验证（推荐）

该批准绑定：

- `reviews/FULL_F1_REMAINING_2026-10-20/NEXT_ACTION_DECISION_PACKET_V1.md`
- `inventory/C02_C03_DECISION_DESIGN_V2.md`，SHA `bbef5698b3382a94234b364e8727736f340ed3ccd94b210ecca7c0d9c339bb0a`
- `inventory/C02_C03_V2_ENTRY_ORDER_ADDENDUM_V1.md`，SHA `4d6565b68dbda1dbbfded14184b801eb39ccbd8695e4d561a7700781936e242e`
- 独立决策准备复核 `8d054176160c52ab8965c9f8d65388b735a69fabc34e634dcb60a2978eef476e`。

批准仅在**全新隔离虚构候选副本**应用三处已列明的 F2 最小差异，并新增两个产品模块、两个测试文件，实现固定组合/固定上下文的强制来源关联、同事务完整提交与当前权限契约。三个现有逻辑路径是 `guarded_workspace_store.py`、`guarded_workspace_context.py`、`guarded_workspace_v1.sql`，不得扩至第四处保护修改。原工作区和封存原件、全部现有实例及旧UNKNOWN均保持不动。

新增四路径为 `src/persistence/required_synthetic_provenance_store.py`、`src/persistence/required_synthetic_provenance_v1.sql`、`tests/product/test_required_synthetic_provenance_contract.py`、`tests/product/test_postgres_required_synthetic_provenance.py`。保留原N2a/N2b/E11、旧19迁移/CHECKSUMS、金融方法、原fixture与历史证据。若需要新的保护路径/实质范围，保存具体差异再问用户。

批准使用现有依赖和项目虚构数据，在新私有Unix PostgreSQL完成必要增量、定向兼容、一次新对象专门重启及新进程耐久验证，并独立复核。源图、对象/角色/权限、执行者、方法选择、控制文件、命令/预算和清理方案先内部精确冻结/独立复核；主执行者串行操作数据库/进程，最多3子代理，作者与复核者分开。必要测试支持修正保存前版及真实失败后，只补受影响用例，不循环重复全绿。

完整提交顺序、动态 self._admit 的所有存在root入口校验与缺root早UNKNOWN边界以已批准附录为准。保持 READ 与请求purpose的原权限语义，不引入全四权利同时为真；FINITE/UNKNOWN仍HOLD。只做虚构、单固定上下文，promotable/source_admitted保持false。

不批准真实数据取得/准入、个人文件/旧raw新用途、新依赖/费用/外部联系、原环境查询/切换/备份恢复、旧UNKNOWN处置、提交推送部署、HG4或恢复夜间任务/caffeinate/reset。本次局部原型即使通过也不等于FullF1所有actor/context完成、D3合格或真实UAT准入。
