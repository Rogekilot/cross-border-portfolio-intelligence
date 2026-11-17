/** The Quant ids each item carries, per variant. Mirrors `claim_render.S_ITEMS`, `C_ITEMS`, `WITHHELD_S_ITEMS` and `WITHHELD_C_ITEMS`; a vitest pin compares the two. */
export const QUANT_IDS: Record<Variant, Record<string, string[]>> = {
  normal: { S1: ['C-1'], S2: ['C-1'], S3: ['C-2', 'C-3', 'C-4'], S4: ['C-5'], S5: ['C-6'],
    C1: ['N-1', 'N-2', 'N-3'], C2: ['N-4'], C3: ['N-5'], C4: ['N-6'], C5: ['N-7'], C6: ['N-8'], C7: ['N-9'] },
  withheld: { S1: ['C-1X'], S2: [], S3: ['C-2X'], S4: ['C-5'], S5: ['C-6X'],
    C1: ['N-1X'], C2: ['N-4X'], C3: ['N-5X'], C4: ['N-6'], C5: ['N-7'], C6: ['N-8'], C7: ['N-9'] },
};
export const NORMAL_STATES = ['AVAILABLE', 'LIMITED'];
export const WITHHELD_STATE = 'INSUFFICIENT_DATA';

/** F1 R7: the claim-limit text of a real-source result (design 7.4), as a PURE function of the slots, the locale and the depth.
 *
 * It computes no number, reads no clock and makes no request. The slot values come from the stored lineage fields, filled by the server
 * (`marketdata/claim_render.py`, `SLOT_FIELDS`); `slotsFromLineage` repeats that mapping so that a test can feed a lineage fixture. A template names
 * its slot values explicitly (`{S3.state}`); a slot that is absent or empty is refused, not rendered with a hole (a caveat that cannot be filled is not
 * softened). The English professional wording is the Quant's own (`marketdata/claim_limits.py`); the shorter depths drop prose, never a caveat or a
 * slot value, and the zh strings are a translation in which a status word (RAW, UNVERIFIABLE, SINGLE_SOURCE, V1, V4) stays as it is (P3).
 * The simple and quick English tables and the whole Chinese table are the Quant's replacement text of
 * `methodology/CP7_F1_R7_CLAIM_WORDING_CHECK_2026-11-07.md` (blocks R7-EN and R7-ZH), applied verbatim, EXCEPT the items the O-7 ruling of 2026-11-10 re-slotted
 * (S1, S3, S4 and S5 at every depth and in both locales) and the whole WITHHELD variant (`TEMPLATES_WITHHELD`): those strings are the Engineer's wording of the
 * ruling's server text and are open to the Quant's new wording check (PD-0082 consequence 5). Two variants, picked by the shape of the block's slots.
 */
export type Locale = 'en' | 'zh-CN';
export type Depth = 'quick' | 'simple' | 'professional';
export const LOCALES: Locale[] = ['en', 'zh-CN'];
export const DEPTHS: Depth[] = ['quick', 'simple', 'professional'];

/** slot group -> { slot name -> lineage field }, the NORMAL variant. Mirrors `claim_render.SLOT_FIELDS`; a Python test pins the two together. The valuation date and
 * the price session are two slots (the Quant's ruling of 2026-11-10, section 4). */
export const SLOT_FIELDS: Record<string, Record<string, string>> = {
  S1: { valuation_date: 'valuation_date', price_session_date: 'price_session_date', missed_sessions: 'missed_sessions', quantity: 'ledger_quantity',
    source: 'source_name', exchange: 'exchange_mic', call: 'vendor_call', documentation_reference: 'documentation_reference', label_source: 'adjustment_label_source' },
  S2: { label_source: 'adjustment_label_source' },
  S3: { reporting_currency: 'reporting_currency', valuation_date: 'valuation_date', quantity: 'ledger_quantity', cash: 'opening_cash', state: 'metric_state',
    freshness: 'freshness', delay: 'delay_status', reconciliation: 'reconciliation_status' },
  S4: { file_hashes: 'file_hashes', ledger_version: 'ledger_version', convention_ids: 'convention_ids' },
  S5: { label_status: 'adjustment_label_status', label_source: 'adjustment_label_source', price_session_date: 'price_session_date', retrieval_time: 'retrieval_time',
    v1_statement: 'v1_statement' },
};
/** The WITHHELD variant (a real NAV in state INSUFFICIENT_DATA). Mirrors `claim_render.WITHHELD_SLOT_FIELDS`: S2 and S5 hold no slot. */
export const WITHHELD_SLOT_FIELDS: Record<string, Record<string, string>> = {
  S1: { valuation_date: 'valuation_date', quantity: 'ledger_quantity', state: 'metric_state' },
  S2: {},
  S3: { reporting_currency: 'reporting_currency', valuation_date: 'valuation_date', state: 'metric_state', nav_cause: 'nav_cause', freshness: 'freshness', delay: 'delay_status' },
  S4: { file_hashes: 'file_hashes', ledger_version: 'ledger_version', convention_ids: 'convention_ids' },
  S5: {},
};
export const S_SLOTS = ['S1', 'S2', 'S3', 'S4', 'S5'] as const;
export const C_ITEMS = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'] as const;
export const ITEM_IDS: string[] = [...S_SLOTS, ...C_ITEMS];
export type Slots = Record<string, Record<string, string>>;
export type Lineage = Record<string, string>;
export type Variant = 'normal' | 'withheld';

export class ClaimTextError extends Error {
  constructor(public code: string, detail = '') { super(detail ? `${code}: ${detail}` : code); }
}

/** The variant a block's slots are shaped for: the withheld one is the one whose S3 group holds the cause of the withheld NAV (as `claim_render` decides). */
export function variantOfSlots(slots: unknown): Variant {
  const s3 = slots !== null && typeof slots === 'object' ? (slots as Record<string, unknown>).S3 : undefined;
  return s3 !== null && typeof s3 === 'object' && !Array.isArray(s3) && 'nav_cause' in (s3 as object) ? 'withheld' : 'normal';
}
const mappingOf = (variant: Variant) => (variant === 'withheld' ? WITHHELD_SLOT_FIELDS : SLOT_FIELDS);

/** The slots a lineage fills (a test helper: the server fills the real ones). The lineage's `metric_state` picks the variant, as on the server. Every field must be
 * a non-empty string; a lineage that lacks one is refused. */
export function slotsFromLineage(lineage: Lineage): Slots {
  const out: Slots = {};
  for (const [group, mapping] of Object.entries(mappingOf(lineage.metric_state === 'INSUFFICIENT_DATA' ? 'withheld' : 'normal'))) {
    out[group] = {};
    for (const [slot, field] of Object.entries(mapping)) {
      const value = lineage[field];
      if (typeof value !== 'string' || value.trim() === '') throw new ClaimTextError('CLAIM_LINEAGE_FIELD', field);
      out[group][slot] = value;
    }
  }
  return out;
}

/** Slots must have exactly the groups of `SLOT_FIELDS` and, for their variant, exactly the names of its mapping, each a non-empty string. */
export function assertSlots(slots: unknown): asserts slots is Slots {
  if (slots === null || typeof slots !== 'object' || Array.isArray(slots)) throw new ClaimTextError('CLAIM_SLOTS_SHAPE');
  const groups = slots as Record<string, unknown>;
  if (Object.keys(groups).sort().join() !== Object.keys(SLOT_FIELDS).sort().join()) throw new ClaimTextError('CLAIM_SLOTS_SHAPE');
  const seen = new Map<string, string>();
  for (const [group, mapping] of Object.entries(mappingOf(variantOfSlots(slots)))) {
    const values = groups[group];
    if (values === null || typeof values !== 'object' || Array.isArray(values)
      || Object.keys(values).sort().join() !== Object.keys(mapping).sort().join()) throw new ClaimTextError('CLAIM_SLOTS_SHAPE', group);
    for (const [name, value] of Object.entries(values as Record<string, unknown>)) {
      if (typeof value !== 'string' || value.trim() === '') throw new ClaimTextError('CLAIM_LINEAGE_FIELD', `${group}.${name}`);
      // TR-O7C-L-1: a lineage field that fills more than one slot holds ONE value across them, as the server's `lineage_from_slots` requires
      const field = mapping[name];
      if (seen.has(field) && seen.get(field) !== value) throw new ClaimTextError('CLAIM_SLOTS_DISAGREE', field);
      seen.set(field, value);
    }
  }
}

type Table = Record<string, string>;
const SEAL_EN = 'The seal that stores the result checks the ledger by its pin (the ledger version), not by its content; the staging and the reproduce of the result are what catch a different ledger. The seal does not verify the instrument identity facts the computation used (trading currency, exchange and security type), and it does not verify the origin recorded in the engine\'s manifest.';

const EN: Record<Depth, Table> = {
  professional: {
    S1: 'The market value of the holding on {S1.valuation_date} is {S1.quantity} x p. Here p is the close {S1.source} delivered for the {S1.price_session_date} {S1.exchange} session through {S1.call}; {S1.missed_sessions} sessions of that exchange lie after that close, up to {S1.valuation_date} inclusive. p is read as as-traded (RAW) on the strength of the vendor\'s documentation of that call, as the owner read it ({S1.documentation_reference}). The label source is {S1.label_source}. That is the vendor\'s declaration, not a verification: no V1 event and no V4 record exists for this file.',
    S2: 'The label source is {S2.label_source}. The series is read as as-traded (RAW) on the vendor\'s declaration of it, which is not a verification (V1 and V4 have not checked it).',
    S3: 'The NAV in {S3.reporting_currency} on {S3.valuation_date} is {S3.quantity} x p + {S3.cash}. The state is {S3.state}, freshness {S3.freshness}, delay {S3.delay}. The reconciliation status is {S3.reconciliation}.',
    S4: `The inputs are named: the files of M with their hashes ({S4.file_hashes}), L (the ledger version {S4.ledger_version}) and the convention sets {S4.convention_ids}. ${SEAL_EN}`,
    S5: 'The stored record of this result states the label status ({S5.label_status}) and the label source ({S5.label_source}) of the reading used, the exposure window E({S5.price_session_date}, {S5.retrieval_time}), whose second argument is the file\'s retrieval time, and the statement of V1 events in M ({S5.v1_statement}). The session list of that window is not stated: market-data/1.16 Ruling 3.2 item 5 is not built in the engine.',
    C1: 'That the series\' split label is verified. It is UNVERIFIABLE. That the dividend component is verified. It is UNVERIFIABLE. M holds no corporate-action record either way, so nothing is known about such a dividend, and nothing is claimed about it. That the series is verified as-traded, or that the vendor\'s declaration has been checked against the exchange or a filing.',
    C2: 'That p is the exchange\'s official closing-cross price as checked. It is single-source and unchecked, unless a Test V4 record exists.',
    C3: 'That the close was compared with any other source. There is none for this market.',
    C4: 'That the listing had no split, or that its split history is complete or verified, in any period.',
    C5: 'That an empty split response, if one exists, shows anything beyond \'zero records at R\'.',
    C6: 'That the quantity {S1.quantity} is verified, or that it is the owner\'s holding. It is the ledger fact the project entered.',
    C7: 'Anything about another date, a return, or any performance or risk figure.',
  },
  simple: {
    S1: 'On {S1.valuation_date} the holding is worth {S1.quantity} x p, where p is the close from {S1.source} for the {S1.price_session_date} {S1.exchange} session ({S1.call}); {S1.missed_sessions} sessions of that exchange lie after it, up to {S1.valuation_date}. It is read as RAW as-traded on the vendor\'s documentation as the owner read it ({S1.documentation_reference}). Label source: {S1.label_source}. This is the vendor\'s declaration, not a verification.',
    S2: 'Label source: {S2.label_source}. RAW as-traded is the vendor\'s declaration, not a verification.',
    S3: 'NAV in {S3.reporting_currency} on {S3.valuation_date}: {S3.quantity} x p + {S3.cash}. State {S3.state}, freshness {S3.freshness}, delay {S3.delay}, reconciliation {S3.reconciliation}.',
    S4: 'Inputs: file hashes ({S4.file_hashes}), ledger version {S4.ledger_version}, convention sets {S4.convention_ids}. The storage seal checks the ledger by its version, not its content, and does not verify the instrument identity facts or the origin in the engine\'s manifest.',
    S5: 'Label status {S5.label_status}, label source {S5.label_source}, exposure window E({S5.price_session_date}, {S5.retrieval_time}) (the second argument is the file\'s retrieval time; the session list is not stated), V1 events in M: {S5.v1_statement}.',
    C1: 'That the split label is verified (it is UNVERIFIABLE); that the dividend component is verified (it is UNVERIFIABLE, and nothing is known about any such dividend); or that the series is verified as-traded, or the vendor\'s declaration checked against the exchange or a filing.',
    C2: 'That p is the exchange\'s official closing-cross price as checked: it is single-source and unchecked.',
    C3: 'That the close was compared with any other source: there is none for this market.',
    C4: 'That the listing had no split, or that its split history is complete or verified, in any period.',
    C5: 'That an empty split response, if one exists, shows more than zero records at the retrieval time R.',
    C6: 'That the quantity {S1.quantity} is verified or is the owner\'s holding: it is a ledger fact the project entered.',
    C7: 'Anything about another date, a return, or any performance or risk figure.',
  },
  quick: {
    S1: '{S1.valuation_date}: {S1.quantity} x p; p = {S1.source} close for {S1.price_session_date} ({S1.call}, {S1.exchange}), {S1.missed_sessions} sessions missed since; RAW per the vendor\'s documentation, read by the owner ({S1.documentation_reference}); label source {S1.label_source}; not a verification.',
    S2: 'Label source {S2.label_source}; RAW is the vendor\'s declaration, not a verification.',
    S3: 'NAV ({S3.reporting_currency}, {S3.valuation_date}) {S3.quantity} x p + {S3.cash}; state {S3.state}, freshness {S3.freshness}, delay {S3.delay}, reconciliation {S3.reconciliation}.',
    S4: 'Inputs: hashes {S4.file_hashes}; ledger version {S4.ledger_version}; convention sets {S4.convention_ids}. Seal: checks the ledger by version, not content; does not verify the instrument identity facts or the engine-manifest origin.',
    S5: 'Label status {S5.label_status}, source {S5.label_source}; exposure window E({S5.price_session_date}, {S5.retrieval_time}), session list not stated; V1 events in M: {S5.v1_statement}.',
    C1: 'That the series is verified: split label UNVERIFIABLE, dividend component UNVERIFIABLE; RAW is the vendor\'s declaration, unchecked.',
    C2: 'That p is the official closing-cross price as checked: it is single-source, unchecked.',
    C3: 'That the close was compared with any other source (there is none).',
    C4: 'That the listing had no split, or that its split history is complete or verified.',
    C5: 'That an empty split response, if one exists, shows more than zero records at R.',
    C6: 'That the quantity {S1.quantity} is verified or is the owner\'s holding: it is a ledger fact.',
    C7: 'Anything about another date, a return, performance or risk.',
  },
};

const ZH: Record<Depth, Table> = {
  professional: {
    S1: '{S1.valuation_date} 当日该持仓的市值为 {S1.quantity} x p。其中 p 为 {S1.source} 通过 {S1.call} 就 {S1.price_session_date} {S1.exchange} 交易日提供的收盘价；自该收盘之后至 {S1.valuation_date}（含），该交易所另有 {S1.missed_sessions} 个交易日。p 依据供应商对该调用的文档说明按不复权口径（RAW，即实际成交价）读取，该文档由所有者阅读（{S1.documentation_reference}）。标签来源为 {S1.label_source}。这是供应商的声明，并非核实：该文件不存在 V1 事件，也不存在 V4 记录。',
    S2: '标签来源为 {S2.label_source}。该序列依据供应商的声明按不复权口径（RAW）读取，并非核实（V1 与 V4 均未检查）。',
    S3: '{S3.valuation_date} 的资产净值（{S3.reporting_currency}）为 {S3.quantity} x p + {S3.cash}。状态为 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}。对账状态为 {S3.reconciliation}。',
    S4: '已列明输入：M 的各文件及其哈希（{S4.file_hashes}）、L（账本版本 {S4.ledger_version}）以及约定集 {S4.convention_ids}。存储该结果的封印按账本的版本号（账本版本）而非账本内容核对账本；能发现账本不同的是该结果的暂存与复现。封印不核实计算所用的标的身份事实（交易币种、交易所和证券类型），也不核实引擎清单中记录的来源。',
    S5: '该结果的存储记录载明所用读数的标签状态（{S5.label_status}）与标签来源（{S5.label_source}）、暴露窗口 E({S5.price_session_date}, {S5.retrieval_time})（其第二个参数为文件的检索时间），以及 M 中 V1 事件的声明（{S5.v1_statement}）。该窗口的交易日列表未予陈述：market-data/1.16 Ruling 3.2 item 5 尚未在引擎中实现。',
    C1: '不声称序列的拆股调整标签已核实：它是 UNVERIFIABLE。不声称股息调整部分已核实：它是 UNVERIFIABLE。M 中没有任何公司行动记录，因此对此类股息一无所知，也不作任何声称。不声称该序列已核实为不复权（实际成交价）序列，也不声称供应商的声明已对照交易所或监管申报文件核对。',
    C2: '不声称 p 是经核对的交易所官方收盘集合竞价价格。它来自单一来源，未经核对，除非存在 V4 检验记录。',
    C3: '不声称该收盘价曾与任何其他来源比较。该市场没有其他来源。',
    C4: '不声称该上市标的在任何时期未发生拆股，也不声称其拆股历史完整或已核实。',
    C5: '不声称空的拆股响应（若存在）能说明“R 时刻零条记录”以外的任何事。',
    C6: '不声称数量 {S1.quantity} 已核实，也不声称它是所有者的持仓。它是项目录入的账本事实。',
    C7: '不声称任何关于其他日期、收益，或任何业绩或风险数字的内容。',
  },
  simple: {
    S1: '{S1.valuation_date} 该持仓的市值为 {S1.quantity} x p，p 为 {S1.source} 就 {S1.price_session_date} {S1.exchange} 交易日提供的收盘价（{S1.call}），其后至 {S1.valuation_date} 该交易所另有 {S1.missed_sessions} 个交易日；依据供应商文档（所有者阅读：{S1.documentation_reference}）按不复权口径（RAW）读取。标签来源：{S1.label_source}。这是供应商的声明，并非核实。',
    S2: '标签来源：{S2.label_source}。不复权（RAW）口径是供应商的声明，并非核实。',
    S3: '{S3.valuation_date} 资产净值（{S3.reporting_currency}）：{S3.quantity} x p + {S3.cash}。状态 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}，对账 {S3.reconciliation}。',
    S4: '输入：文件哈希（{S4.file_hashes}）、账本版本 {S4.ledger_version}、约定集 {S4.convention_ids}。封印按账本版本而非内容核对账本，不核实标的身份事实，也不核实引擎清单中的来源。',
    S5: '标签状态 {S5.label_status}，标签来源 {S5.label_source}，暴露窗口 E({S5.price_session_date}, {S5.retrieval_time})（第二个参数为文件的检索时间，交易日列表未予陈述），M 中的 V1 事件：{S5.v1_statement}。',
    C1: '不声称拆股调整标签已核实（它是 UNVERIFIABLE），不声称股息调整部分已核实（它是 UNVERIFIABLE，对任何此类股息一无所知），也不声称该序列已核实为不复权序列，或供应商的声明已对照交易所或监管申报文件核对。',
    C2: '不声称 p 是经核对的交易所官方收盘集合竞价价格：它来自单一来源，未经核对。',
    C3: '不声称该收盘价与任何其他来源比较过：该市场没有其他来源。',
    C4: '不声称该上市标的在任何时期未发生拆股，也不声称其拆股历史完整或已核实。',
    C5: '不声称空的拆股响应（若存在）能说明检索时刻 R 零条记录以外的任何事。',
    C6: '不声称数量 {S1.quantity} 已核实或是所有者的持仓：它是项目录入的账本事实。',
    C7: '不声称任何关于其他日期、收益，或任何业绩或风险数字的内容。',
  },
  quick: {
    S1: '{S1.valuation_date}：{S1.quantity} x p；p = {S1.source} {S1.price_session_date} 收盘价（{S1.call}，{S1.exchange}），其后已有 {S1.missed_sessions} 个交易日；不复权（RAW），依据供应商文档（所有者阅读：{S1.documentation_reference}）；标签来源 {S1.label_source}；并非核实。',
    S2: '标签来源 {S2.label_source}；不复权（RAW）是供应商的声明，并非核实。',
    S3: '资产净值（{S3.reporting_currency}，{S3.valuation_date}）{S3.quantity} x p + {S3.cash}；状态 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}，对账 {S3.reconciliation}。',
    S4: '输入：哈希 {S4.file_hashes}；账本版本 {S4.ledger_version}；约定集 {S4.convention_ids}。封印：按版本而非内容核对账本；不核实标的身份事实与引擎清单中的来源。',
    S5: '标签状态 {S5.label_status}，来源 {S5.label_source}；暴露窗口 E({S5.price_session_date}, {S5.retrieval_time})，交易日列表未予陈述；M 中的 V1 事件：{S5.v1_statement}。',
    C1: '不声称已核实：拆股调整标签 UNVERIFIABLE，股息调整部分 UNVERIFIABLE；不复权口径为供应商声明，未经核对。',
    C2: '不声称 p 是经核对的收盘集合竞价价格：单一来源，未经核对。',
    C3: '不声称与其他来源比较过（没有其他来源）。',
    C4: '不声称未发生拆股，或拆股历史完整、已核实。',
    C5: '不声称空的拆股响应（若存在）说明 R 时刻零条记录以外的事。',
    C6: '不声称数量 {S1.quantity} 已核实或是所有者的持仓：它是账本事实。',
    C7: '不声称其他日期、收益、业绩或风险方面的任何内容。',
  },
};

/** The WITHHELD variant (a real NAV in state INSUFFICIENT_DATA; the Quant's ruling of 2026-11-10, section 6; PD-0082 Q4). The same twelve ids. S4 and C4 to C7 are the
 * normal ones (spread); the others say that nothing is stated and why, and state no price, label, window or reconciliation status. The English professional entries
 * are the server's text (`claim_limits.WITHHELD_LIMITS`); the other depths and the whole Chinese table are the client's own wording and go to the Quant's wording check. */
const EN_WITHHELD: Record<Depth, Table> = {
  professional: {
    ...EN.professional,
    S1: 'No holding value on {S1.valuation_date} is stated: no close values the holding, and the NAV\'s state is {S1.state}.',
    S2: 'No label source is stated: no reading values the holding.',
    S3: 'No NAV in {S3.reporting_currency} on {S3.valuation_date} is stated. The state is {S3.state}, cause {S3.nav_cause}, freshness {S3.freshness}, delay {S3.delay}.',
    S5: 'No label status, exposure window or V1 statement is stated: no reading values the holding.',
    C1: 'That any price series is verified as-traded, or that any of its labels, split or dividend component, is verified.',
    C2: 'That any close was used, or that any close is the exchange\'s official closing-cross price.',
    C3: 'That any close was compared with any other source. There is none for this market.',
  },
  simple: {
    ...EN.simple,
    S1: 'No holding value is stated for {S1.valuation_date}: no close values the holding, and the NAV\'s state is {S1.state}.',
    S2: 'No label source is stated: no reading values the holding.',
    S3: 'No NAV in {S3.reporting_currency} is stated for {S3.valuation_date}. State {S3.state}, cause {S3.nav_cause}, freshness {S3.freshness}, delay {S3.delay}.',
    S5: 'No label status, exposure window or V1 statement is stated: no reading values the holding.',
    C1: 'That any price series is verified as-traded, or that any of its labels (split or dividend component) is verified.',
    C2: 'That any close was used, or that any close is the exchange\'s official closing-cross price.',
    C3: 'That any close was compared with any other source: there is none for this market.',
  },
  quick: {
    ...EN.quick,
    S1: 'No holding value stated for {S1.valuation_date}: no close values the holding; NAV state {S1.state}.',
    S2: 'No label source stated: no reading values the holding.',
    S3: 'No NAV ({S3.reporting_currency}, {S3.valuation_date}) stated; state {S3.state}, cause {S3.nav_cause}, freshness {S3.freshness}, delay {S3.delay}.',
    S5: 'No label status, exposure window or V1 statement stated: no reading values the holding.',
    C1: 'That any price series is verified as-traded, or any label (split, dividend component) is verified.',
    C2: 'That any close was used, or is the official closing-cross price.',
    C3: 'That any close was compared with any other source (there is none).',
  },
};

const ZH_WITHHELD: Record<Depth, Table> = {
  professional: {
    ...ZH.professional,
    S1: '{S1.valuation_date} 的持仓市值未予陈述：没有任何收盘价对该持仓估值，资产净值的状态为 {S1.state}。',
    S2: '未陈述标签来源：没有任何读数对该持仓估值。',
    S3: '{S3.valuation_date} 的资产净值（{S3.reporting_currency}）未予陈述。状态为 {S3.state}，原因 {S3.nav_cause}，新鲜度 {S3.freshness}，延迟 {S3.delay}。',
    S5: '未陈述标签状态、暴露窗口或 V1 声明：没有任何读数对该持仓估值。',
    C1: '不声称任何价格序列已核实为不复权（实际成交价）序列，也不声称其任何标签（拆股调整标签或股息调整部分）已核实。',
    C2: '不声称曾使用任何收盘价，也不声称任何收盘价是交易所官方收盘集合竞价价格。',
    C3: '不声称任何收盘价曾与任何其他来源比较。该市场没有其他来源。',
  },
  simple: {
    ...ZH.simple,
    S1: '{S1.valuation_date} 的持仓市值未予陈述：没有任何收盘价对该持仓估值，资产净值的状态为 {S1.state}。',
    S2: '未陈述标签来源：没有任何读数对该持仓估值。',
    S3: '{S3.valuation_date} 的资产净值（{S3.reporting_currency}）未予陈述。状态 {S3.state}，原因 {S3.nav_cause}，新鲜度 {S3.freshness}，延迟 {S3.delay}。',
    S5: '未陈述标签状态、暴露窗口或 V1 声明：没有任何读数对该持仓估值。',
    C1: '不声称任何价格序列已核实为不复权序列，也不声称其任何标签（拆股调整标签或股息调整部分）已核实。',
    C2: '不声称曾使用任何收盘价，也不声称任何收盘价是交易所官方收盘集合竞价价格。',
    C3: '不声称任何收盘价与任何其他来源比较过：该市场没有其他来源。',
  },
  quick: {
    ...ZH.quick,
    S1: '{S1.valuation_date} 持仓市值未予陈述：无收盘价对该持仓估值；资产净值状态 {S1.state}。',
    S2: '未陈述标签来源：无读数对该持仓估值。',
    S3: '资产净值（{S3.reporting_currency}，{S3.valuation_date}）未予陈述；状态 {S3.state}，原因 {S3.nav_cause}，新鲜度 {S3.freshness}，延迟 {S3.delay}。',
    S5: '未陈述标签状态、暴露窗口或 V1 声明：无读数对该持仓估值。',
    C1: '不声称任何价格序列已核实为不复权序列，或其任何标签（拆股调整标签、股息调整部分）已核实。',
    C2: '不声称曾使用任何收盘价，或任何收盘价是官方收盘集合竞价价格。',
    C3: '不声称任何收盘价与其他来源比较过（没有其他来源）。',
  },
};

export const TEMPLATES: Record<Locale, Record<Depth, Table>> = { en: EN, 'zh-CN': ZH };
export const TEMPLATES_WITHHELD: Record<Locale, Record<Depth, Table>> = { en: EN_WITHHELD, 'zh-CN': ZH_WITHHELD };
const PLACEHOLDER = /\{(S[1-5])\.([a-z_0-9]+)\}/g;

export interface ClaimText { id: string; kind: 'MAY_CLAIM' | 'MAY_NOT_CLAIM'; text: string }

function fill(template: string, slots: Slots): string {
  return template.replace(PLACEHOLDER, (_whole, group: string, name: string) => {
    const value = slots[group]?.[name];
    if (typeof value !== 'string' || value.trim() === '') throw new ClaimTextError('CLAIM_LINEAGE_FIELD', `${group}.${name}`);
    return value;
  });
}

/** The twelve items (S1 to S5, C1 to C7) for one locale and depth, every slot filled. Throws `ClaimTextError` for a slot that is absent or empty. */
export function claimLimitText(slots: Slots, locale: Locale, depth: Depth): ClaimText[] {
  assertSlots(slots);
  const table = (variantOfSlots(slots) === 'withheld' ? TEMPLATES_WITHHELD : TEMPLATES)[locale]?.[depth];
  if (!table) throw new ClaimTextError('CLAIM_LOCALE_OR_DEPTH');
  return ITEM_IDS.map((id) => ({ id, kind: (S_SLOTS as readonly string[]).includes(id) ? 'MAY_CLAIM' : 'MAY_NOT_CLAIM', text: fill(table[id], slots) }));
}
