/** F1 R7: the strings of the real-mode screen. Its own i18next instance: the fictional screens' resources are not loaded here (design 1 item 6).
 *
 * TWO tables. `common` carries every string a real root's screen may show; none of them contains the wording `fictional`, `sandbox`, `synthetic` or
 * `invented` (case-insensitive; the widened-wording test checks this, English and Chinese). `testOrigin` carries the strings that only a root with a
 * non-real origin shows (the invented-data mark); a real-origin root never reads that table.
 */
import i18next, { type i18n } from 'i18next';
import type { Locale } from './real-mode-claims';

export const common = {
  en: {
    title: 'Stored results', brand: 'Meridian', brandSub: 'PORTFOLIO INTELLIGENCE', language: 'Interface language', depth: 'Explanation depth',
    quick: 'Quick', simple: 'Simple', professional: 'Professional',
    authHeading: 'Local account', username: 'Username', password: 'Password', signIn: 'Sign in', signUp: 'Create local account', signOut: 'Sign out',
    signedInAs: 'Signed in as', signInRequired: 'Sign in to see your roots.',
    // DR-R8-3: the rule as the server enforces it (web_api/auth.py `password`): at least 15 characters, at most 128 UTF-8 bytes.
    passwordHint: 'At least 15 characters, at most 128 UTF-8 bytes.',
    usernameHint: 'Username: 3 to 32 ASCII characters (letters, digits, dot, underscore or hyphen), starting with a letter.',
    credentialsInvalid: 'The username or the password does not meet the rules. Username: 3 to 32 ASCII characters (letters, digits, dot, underscore or hyphen), starting with a letter. Password: at least 15 characters and at most 128 UTF-8 bytes. The password field was cleared.',
    rootsHeading: 'Your roots', noRoots: 'No root has been created yet.', refreshList: 'Refresh list', rootId: 'Root', contextId: 'Context',
    contextGenerationNow: 'Context now at generation', createdUnderGeneration: 'Created under generation',
    generationNote: "Generation is the context's permission version, not a property of a root. A renew or a withdrawal changes the generation shown for every root in that context. It does not create, re-bind or change a stored root. The generation a root was created under is shown when you open it.",
    createdAt: 'Created', refusedEntry: 'Not readable now',
    createHeading: 'Create a root', createHint: 'The identifiers below name the stored context, release and listing. They are typed by you; the page does not choose them.',
    fieldContext: 'Context ID', fieldRelease: 'Release ID', fieldListing: 'Listing ID', fieldName: 'Name', fieldAsOf: 'As-of date (YYYY-MM-DD)',
    fieldQuantity: 'Quantity', fieldCash: 'Opening cash', fieldCurrency: 'Reporting currency',
    fieldAck: 'I understand the ledger is constructed by the project for testing and is not my holding.',
    create: 'Create', creating: 'Creating…', openRoot: 'Open', reproduce: 'Reproduce', reproducing: 'Reproducing…',
    detailHeading: 'Stored result', operation: 'Operation', revision: 'Revision', ledgerPin: 'Ledger version', replayed: 'Replayed: an identical earlier command was returned.',
    responseDigest: 'Stored response digest', issuedDigest: 'Issued result digest', resultJson: 'Issued result, as stored',
    reproduceHeading: 'Reproduction', reproduceStatus: 'Status', reproduceDetail: 'Detail',
    claimsHeading: 'What this result does and does not claim', claimsMay: 'May say', claimsMayNot: 'Does not claim',
    unknownOutcome: 'The outcome is not known. Nothing was retried. Repeat the identical command to find out.', repeatCommand: 'Repeat the identical command',
    errorHeading: 'Request refused', networkError: 'The local API is unavailable.', invalidResponse: 'The response did not match the contract and was not shown.',
    closedRoute: 'This route is closed in real mode.',
    readHeading: 'Read a stored result', fieldOperation: 'Operation ID', readStored: 'Read',
    // PD-0079 (key figures and the label of the raw document). Plain labels; the figures themselves are the stored values.
    figuresHeading: 'Key figures',
    // The Quant's ruling (methodology/CP7_F1_PD0079_FIGURES_WORDING_CHECK_2026-11-09.md, block PD79-EN), applied verbatim.
    figuresNote: 'A fixed selection of the stored figures, in a fixed order; the complete set is in the document below. Each value is shown as the engine stored it: nothing is rounded, converted or summed here. Where the total has a number, its parts are the engine\'s apportioned values, which add up to it exactly. The claim limits above govern these figures.',
    figureNav: 'Portfolio value (NAV), reporting view', figureHolding: 'Holding value, reporting view', figureCash: 'Cash value, reporting view',
    figureState: 'State', figureReason: 'Reason', figureNoValue: 'No number is shown for this state.',
    figureReceivable: 'Dividend receivable value, reporting view',
    figureAbsent: 'Not in this result. That is not a stated zero.',
    figureLimited: 'Limited: computed on a weak basis, so this number does not stand alone; read it with what is stated beside it.',
    figureUnreadable: 'State or value not readable; no number is shown.',
    figureStaleWeight: 'Stale weight (share of the components\' gross value, as a decimal fraction)',
    figureStaleNotStated: 'Stale weight not stated by the engine.',
    figureDetail: 'Detail',
    figurePartial: 'Value of priced holdings (partial), reporting view',
    figurePartialNotNav: 'Partial: this is never the portfolio total or NAV.',
    figureExcludedHoldings: 'Holdings excluded because they cannot be valued',
    figureExcludedComponents: 'Components excluded in total (holdings, cash, receivables)',
    // PD-0080 (engineer's wording, for the Quant's ruling): a real result with no portfolio value row at all.
    figureNoNav: 'This result stores no portfolio value (NAV). That is not a suppressed value and not a stated zero; no portfolio total is shown. A valuation always stores this figure, so this is a defect in the document: do not take a total from the figures below.',
    rawNote: 'The engine\'s document exactly as issued, with only line breaks and indentation added for reading. Its notes are in English and are not interpreted. The claim limits above govern it.',
  },
  'zh-CN': {
    title: '已存结果', brand: 'Meridian', brandSub: '组合洞察', language: '界面语言', depth: '说明深度', quick: '速览', simple: '简明', professional: '专业',
    authHeading: '本地账户', username: '用户名', password: '密码', signIn: '登录', signUp: '创建本地账户', signOut: '退出登录',
    signedInAs: '当前登录', signInRequired: '登录后查看你的根记录。',
    passwordHint: '至少 15 个字符，最多 128 个 UTF-8 字节。',
    usernameHint: '用户名：3 至 32 个 ASCII 字符（字母、数字、点、下划线或连字符），以字母开头。',
    credentialsInvalid: '用户名或密码不符合规则。用户名：3 至 32 个 ASCII 字符（字母、数字、点、下划线或连字符），以字母开头。密码：至少 15 个字符，最多 128 个 UTF-8 字节。密码栏已清空。',
    rootsHeading: '你的根记录', noRoots: '尚未创建任何根记录。', refreshList: '刷新列表', rootId: '根记录', contextId: '上下文',
    contextGenerationNow: '上下文当前代次', createdUnderGeneration: '创建时所在代次',
    generationNote: '代次是上下文的授权版本，不是根的属性。续期或撤回会改变该上下文下每个根所显示的代次，但不会创建、重新绑定或更改已保存的根。每个根创建时所在的代次在打开后显示。',
    createdAt: '创建时间', refusedEntry: '当前无法读取',
    createHeading: '创建根记录', createHint: '下列标识指向已存储的上下文、版本和上市标的，由你输入；页面不会替你选择。',
    fieldContext: '上下文 ID', fieldRelease: '版本 ID', fieldListing: '上市标的 ID', fieldName: '名称', fieldAsOf: '截止日期（YYYY-MM-DD）',
    fieldQuantity: '数量', fieldCash: '期初现金', fieldCurrency: '报告币种',
    fieldAck: '我理解该账本由项目为测试而构造，并非我的持仓。',
    create: '创建', creating: '正在创建…', openRoot: '打开', reproduce: '复现', reproducing: '正在复现…',
    detailHeading: '已存储的结果', operation: '操作', revision: '修订', ledgerPin: '账本版本', replayed: '重放：返回了此前完全相同的命令的结果。',
    responseDigest: '已存储响应摘要', issuedDigest: '已签发结果摘要', resultJson: '已签发结果（按存储原样）',
    reproduceHeading: '复现', reproduceStatus: '状态', reproduceDetail: '详情',
    claimsHeading: '该结果声称与不声称的内容', claimsMay: '可以陈述', claimsMayNot: '不声称',
    unknownOutcome: '结果未知，未做任何重试。请重复发送完全相同的命令以确认。', repeatCommand: '重复发送相同命令',
    errorHeading: '请求被拒绝', networkError: '本地 API 不可用。', invalidResponse: '响应与契约不符，未予显示。',
    closedRoute: '该路由在真实模式下已关闭。',
    readHeading: '读取已存储的结果', fieldOperation: '操作 ID', readStored: '读取',
    figuresHeading: '关键数字',
    // The Quant's ruling, block PD79-ZH, applied verbatim.
    figuresNote: '这里按固定顺序列出部分已存储数字；完整内容见下方文档。每个数值均按引擎存储的原样显示：此处不做舍入、换算或求和。总额有数值时，其组成项为引擎分摊后的数值，合计恰等于总额。以上的声明限制适用于这些数字。',
    figureNav: '组合价值（资产净值），报告币种视图',
    figureHolding: '持仓市值，报告币种视图',
    figureCash: '现金余额，报告币种视图',
    figureReceivable: '应收股息价值，报告币种视图',
    figureAbsent: '此结果未包含此项，这并不表示数值为零。',
    figureState: '状态', figureReason: '原因', figureNoValue: '该状态下不显示数值。',
    figureLimited: '受限：计算依据较弱，此数字不能单独理解；请结合旁边列明的内容阅读。',
    figureUnreadable: '状态或数值无法读取，不显示数值。',
    figureStaleWeight: '陈旧权重（占各组成项绝对值之和的比例，以小数表示）',
    figureStaleNotStated: '引擎未给出陈旧权重。',
    figureDetail: '详情',
    figurePartial: '已定价持仓价值（部分），报告币种视图',
    figurePartialNotNav: '部分金额：绝非组合总值或资产净值。',
    figureExcludedHoldings: '因无法估值而被排除的持仓数',
    figureExcludedComponents: '被排除的组成项总数（持仓、现金、应收股息）',
    figureNoNav: '该结果未存储组合价值（资产净值）。这既不是被抑制的数值，也不是明确给出的零；此处不显示任何组合总值。估值结果总会存储此数字，因此这是该文档的缺陷：请勿根据下列数字得出总值。',
    rawNote: '引擎原样签发的文档，仅为便于阅读添加了换行和缩进。其中的说明为英文，未作解读。以上的声明限制适用于该文档。',
  },
} as const;

/** Shown only for a root whose stored origin is not the real source. */
export const testOrigin = {
  en: {
    banner: 'INVENTED TEST DATA', mark: 'Invented test data; no claim about any real source.',
    // The Quant's ruling, block PD79-TEST, applied verbatim: the notes over a non-real origin point at the mark, not at claim limits that do not render.
    figuresNote: 'A fixed selection of the stored figures, in a fixed order; the complete set is in the document below. Each value is shown as the engine stored it: nothing is rounded, converted or summed here. Where the total has a number, its parts are the engine\'s apportioned values, which add up to it exactly. These figures come from invented test data, as the mark above says.',
    rawNote: 'The engine\'s document exactly as issued, with only line breaks and indentation added for reading. Its notes are in English and are not interpreted. It comes from invented test data, as the marks above say.',
    // PD-0080 (engineer's wording, for the Quant's ruling): over invented test data the figure list is replaced by this statement.
    figuresNone: 'This document stores none of the listed figures (portfolio, holding, cash or dividend receivable value): it is not a valuation result. Any amounts in it are not these figures, and none of these figures is derived from them. It comes from invented test data. A figure that is not here is not a stated zero.',
  },
  'zh-CN': {
    banner: '测试用虚构数据', mark: '测试用虚构数据；不对任何真实来源作出声明。',
    figuresNote: '这里按固定顺序列出部分已存储数字；完整内容见下方文档。每个数值均按引擎存储的原样显示：此处不做舍入、换算或求和。总额有数值时，其组成项为引擎分摊后的数值，合计恰等于总额。这些数字来自测试用虚构数据，如上方标记所示。',
    rawNote: '引擎原样签发的文档，仅为便于阅读添加了换行和缩进。其中的说明为英文，未作解读。该文档来自测试用虚构数据，如上方标记所示。',
    figuresNone: '本文档未存储所列的任何数字（组合价值、持仓市值、现金余额或应收股息价值）：它不是估值结果。其中的金额并非这些数字，这些数字也不由其得出。它来自测试用虚构数据。此处没有的数字并不表示为零。',
  },
} as const;

/** The server's origin statements, in Chinese, keyed by the stored `origin_kind`. English shows the server's own label text. */
export const realOriginZh = {
  REAL_SOURCE_CONSTRUCTED_ACCOUNT: { origin_statement: '市场数据来自真实来源；账户由项目为测试而构造。', holding_statement: '项目构造的测试账户，并非所有者的持仓。' },
} as const;
export const testOriginZh = {
  INVENTED_TEST_DATA: { origin_statement: '测试用虚构数据，没有真实来源。', holding_statement: '虚构的测试账本，并非持仓。' },
} as const;

/** The refusal codes of the contract (`ERRORS`) in Chinese. English shows the server's fixed detail. A code that this table lacks shows its code and the
 * server's English detail in either language. One code is left out on purpose: the stored-market-data read refusal. Its name matches the S2-object
 * pattern of the source audit (`test_real_labels`), and a client file that spells it would join the audit's pinned set of object readers. */
export const refusalZh: Record<string, string> = {
  REAL_REQUEST_INVALID: '请求无效', REAL_UNAVAILABLE: '真实数据工作区当前不可用', RW_NOT_FOUND: '该所有者名下没有这个上下文、根记录或操作',
  RW_GENERATION_DIFFERS: '上下文已变更，请用当前代次重试', RW_LAPSED: '上下文已失效', RW_WITHDRAWN: '上下文已撤回', RW_WITHDRAWAL_PENDING: '上下文的撤回尚在处理',
  RW_RIGHT_REFUSED: '上下文不授予此项权利', RW_DEADLINE: '操作未在时限内完成', RW_IDEMPOTENCY_CONFLICT: '该操作 ID 已用于不同的命令',
  RW_CONTEXT_BINDING_DIFFERS: '所请求的版本与上下文的版本不同', RW_WORLD_DIFFERS: '输入与上下文的快照不同', RW_SEAL_REFUSED: '结果未被接受存储', RW_CLAIM_RECORD_REFUSED: '无法陈述该结果的声明限制，因此未存储',
  RW_RELEASE_REFUSED: '已存储的版本未通过完整性检查',
  SYNTHETIC_MARKET_DATA_REFUSED: '金融服务拒绝对非真实来源的市场数据估值', RW_LOCK_TIMEOUT: '操作未能及时取得锁', RW_STATEMENT_FAILED: '操作失败并已回滚',
  REAL_MODE_ROUTE_CLOSED: '该路由在真实模式下已关闭', AUTHENTICATION_REQUIRED: '需要登录', INVALID_CREDENTIALS: '用户名或密码不正确',
};

export function createTranslator(): i18n {
  const instance = i18next.createInstance();
  void instance.init({
    lng: 'en', fallbackLng: false, initAsync: false, interpolation: { escapeValue: false },
    resources: { en: { translation: common.en }, 'zh-CN': { translation: common['zh-CN'] } },
  });
  return instance;
}

export type Translate = (key: keyof typeof common.en) => string;
export function translator(locale: Locale, instance: i18n = createTranslator()): Translate {
  const t = instance.getFixedT(locale);
  return (key) => t(key) as string;
}
