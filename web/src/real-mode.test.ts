/** F1 R7 client tests: the claim-limit text (design 7.4), the origin presentation, the strict readers and the transport. Node environment; components are
 * rendered to static markup with `createElement`. Every lineage value here is a placeholder: no market number, nothing stored, nothing served. */
import { readFileSync } from 'node:fs';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './transport';
import { assertSlots, claimLimitText, ClaimTextError, DEPTHS, ITEM_IDS, LOCALES, SLOT_FIELDS, slotsFromLineage, TEMPLATES, TEMPLATES_WITHHELD, variantOfSlots,
  QUANT_IDS, WITHHELD_SLOT_FIELDS, type Depth, type Lineage, type Locale } from './real-mode-claims';
import { common, createTranslator, realOriginZh, refusalZh, testOrigin, testOriginZh, translator } from './real-mode-i18n';
import { createBody, newOperationId, readClaimBlock, readLabels, readOrigin, readReproduction, readRoot, readRootList, readSession, RealModeApi, UnknownOutcome,
  type Origin } from './real-mode';
import { REAL_SENTENCES } from '../e2e/real-mode-phrases';
import RealModeApp, { ClaimLimits, KeyFigures, OriginBanner, RootDetail, RootEntries, refusalText } from './RealModeApp';
import { FIGURE_LIST, keyFigures, navStatus, partialBlock } from './real-mode';

const REAL: Origin = { market_origin: 'REAL_SOURCE', ledger_origin: 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT', personal_holdings: false, synthetic: false };
const TEST: Origin = { market_origin: 'SYNTHETIC_TEST', ledger_origin: 'INVENTED_TEST_LEDGER', personal_holdings: false, synthetic: true };
const REAL_LABELS = { origin_kind: 'REAL_SOURCE_CONSTRUCTED_ACCOUNT', origin_statement: 'Market data from a real source; the account was constructed by the project for testing.',
  holding_statement: 'A project-constructed test account. It is not the owner\'s holding.' };
const TEST_LABELS = { origin_kind: 'INVENTED_TEST_DATA', origin_statement: 'Invented test data; no real source.', holding_statement: 'An invented test ledger. It is not a holding.' };
const MARK = 'Invented test data; no claim about any real source.';
const UUID_A = '11111111-1111-4111-8111-111111111111';
const UUID_B = '22222222-2222-4222-8222-222222222222';
const HEX = (c: string) => c.repeat(64);

/** The lineage fields, each with a value that names its field, so a slot can be traced to the field that filled it. */
const FIELDS = Array.from(new Set(Object.values(SLOT_FIELDS).flatMap((mapping) => Object.values(mapping))));
const traced = (): Lineage => Object.fromEntries(FIELDS.map((field) => [field, `LV<${field}>`]));
/** A lineage with realistic words in the status fields (placeholders for every number). */
const lineage = (): Lineage => ({ ...traced(), reconciliation_status: 'SINGLE_SOURCE', metric_state: 'AVAILABLE', freshness: 'CURRENT', delay_status: 'END_OF_DAY',
  adjustment_label_status: 'UNVERIFIABLE', adjustment_label_source: 'DECLARED', v1_statement: 'no V1 event in M' });
/** The withheld variant's lineage (a real NAV in state INSUFFICIENT_DATA): only the fields its slots name, with the state and the cause of the withheld NAV. */
const WITHHELD_FIELDS = Array.from(new Set(Object.values(WITHHELD_SLOT_FIELDS).flatMap((mapping) => Object.values(mapping))));
const withheldTraced = (): Lineage => Object.fromEntries(WITHHELD_FIELDS.map((field) => [field, `LV<${field}>`]));
const withheldLineage = (): Lineage => ({ ...withheldTraced(), metric_state: 'INSUFFICIENT_DATA', nav_cause: 'MISSING_PRICE_HISTORY', freshness: 'UNKNOWN',
  delay_status: 'UNKNOWN' });

const PHRASES: Record<Locale, Record<string, string[]>> = {
  en: { S1: ['RAW', 'not a verification'], S2: ['RAW', 'not a verification'], S3: ['freshness', 'delay', 'reconciliation'],
    S4: ['hashes', 'convention', 'content', 'identity facts', 'manifest'], S5: ['exposure window', 'V1'],
    C1: ['split label', 'dividend component', 'UNVERIFIABLE', 'verified', 'declaration'], C2: ['closing-cross', 'single-source', 'unchecked'],
    C3: ['compared', 'other source'], C4: ['no split', 'split history'], C5: ['if one exists', 'zero records'],
    C6: ['verified', 'ledger fact', 'owner\'s holding'], C7: ['another date', 'return', 'performance', 'risk'] },
  'zh-CN': { S1: ['RAW', '不复权', '并非核实'], S2: ['RAW', '并非核实'], S3: ['新鲜度', '延迟', '对账'],
    S4: ['哈希', '约定', '内容', '标的身份事实', '清单'], S5: ['暴露窗口', 'V1'],
    C1: ['拆股调整标签', '股息调整部分', 'UNVERIFIABLE', '已核实', '不复权', '声明'], C2: ['收盘集合竞价价格', '单一来源', '未经核对'],
    C3: ['比较', '其他来源'], C4: ['未发生拆股', '拆股历史'], C5: ['若存在', '零条记录'],
    C6: ['已核实', '账本事实', '所有者的持仓'], C7: ['其他日期', '收益', '业绩', '风险'] },
};
const BANNED = { en: /fictional|sandbox|synthetic|invented/i, 'zh-CN': /虚构|沙盒|合成|模拟|发明/ };

function missing(items: { id: string; text: string }[], locale: Locale): string[] {
  const problems: string[] = [];
  for (const id of ITEM_IDS) {
    const item = items.find((candidate) => candidate.id === id);
    if (!item) { problems.push(`missing ${id}`); continue; }
    for (const phrase of PHRASES[locale][id]) if (!item.text.includes(phrase)) problems.push(`${id} lacks ${phrase}`);
  }
  return problems;
}

function block(locale: Locale = 'en') {
  const slots = slotsFromLineage(lineage());
  const items = claimLimitText(slots, locale, 'professional').map((item) => ({ id: item.id, kind: item.kind, quant_ids: QUANT_IDS.normal[item.id], text: item.text }));
  return { items, slots, invented_data_mark: null };
}
function withheldBlock(locale: Locale = 'en') {
  const slots = slotsFromLineage(withheldLineage());
  const items = claimLimitText(slots, locale, 'professional').map((item) => ({ id: item.id, kind: item.kind, quant_ids: QUANT_IDS.withheld[item.id], text: item.text }));
  return { items, slots, invented_data_mark: null };
}
const testBlock = () => ({ items: [], slots: Object.fromEntries(['S1', 'S2', 'S3', 'S4', 'S5'].map((s) => [s, MARK])), invented_data_mark: MARK });

describe('claim-limit text over an in-memory REAL_SOURCE lineage fixture (design 7.4, R7)', () => {
  for (const locale of LOCALES) for (const depth of DEPTHS) {
    const items = () => claimLimitText(slotsFromLineage(lineage()), locale, depth);
    describe(`${locale} / ${depth}`, () => {
      it('carries S1 to S5 and every C-item, each with its required phrases', () => {
        const rendered = items();
        expect(rendered.map((item) => item.id)).toEqual(ITEM_IDS);
        expect(rendered.map((item) => item.id)).toEqual(['S1', 'S2', 'S3', 'S4', 'S5', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']);
        expect(missing(rendered, locale)).toEqual([]);
      });
      it('states the dividend component as UNVERIFIABLE in C1 and the single-source, no-comparison caveat (C2, C3 and S3\'s SINGLE_SOURCE)', () => {
        const by = Object.fromEntries(items().map((item) => [item.id, item.text]));
        expect(by.C1).toContain('UNVERIFIABLE');
        expect(by.C1).toContain(locale === 'en' ? 'dividend component' : '股息调整部分');
        expect(by.C2).toContain(locale === 'en' ? 'single-source' : '单一来源');
        expect(by.C3).toContain(locale === 'en' ? 'other source' : '其他来源');
        expect(by.S3).toContain('SINGLE_SOURCE');
      });
      it('fills every slot of every S-item from the lineage field that the slot maps to', () => {
        const traces = slotsFromLineage(traced());
        const by = Object.fromEntries(claimLimitText(traces, locale, depth).map((item) => [item.id, item.text]));
        for (const [group, mapping] of Object.entries(SLOT_FIELDS)) {
          for (const [slot, field] of Object.entries(mapping)) {
            expect(traces[group][slot]).toBe(`LV<${field}>`);
            expect(by[group], `${group}.${slot} from ${field}`).toContain(`LV<${field}>`);
          }
        }
        expect(by.C6).toContain('LV<ledger_quantity>');
        for (const text of Object.values(by)) expect(text).not.toMatch(/[{}]/);       // no placeholder is left unfilled
      });
      it('states two UNVERIFIABLE labels in C1 (split and dividend component), and phrases every C-item as a claim not made', () => {
        const by = Object.fromEntries(items().map((item) => [item.id, item.text]));
        expect(by.C1.split('UNVERIFIABLE').length - 1).toBeGreaterThanOrEqual(2);
        for (const id of ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']) {
          if (locale === 'en') expect(by[id], id).toMatch(/^(That|Anything) /);
          else expect(by[id].startsWith('不声称'), id).toBe(true);
        }
        expect(by.S4).not.toMatch(locale === 'en' ? /seal (verifies|checks the (instrument )?identity)/i : /封印核实|封印已核实/);
      });
      it('says what the storage seal does not verify at this depth', () => {
        const s4 = items().find((item) => item.id === 'S4')!.text;
        expect(s4).toContain(locale === 'en' ? 'identity facts' : '标的身份事实');
      });
      it('fails the phrase check when any one item, or any one required phrase, is removed', () => {
        const all = items();
        for (const id of ITEM_IDS) {
          expect(missing(all.filter((item) => item.id !== id), locale)).toContain(`missing ${id}`);
          for (const phrase of PHRASES[locale][id]) {
            const without = all.map((item) => (item.id === id ? { ...item, text: item.text.split(phrase).join('') } : item));
            expect(missing(without, locale)).toContain(`${id} lacks ${phrase}`);
          }
        }
      });
      it('uses no fictional, sandbox, synthetic or invented wording', () => {
        for (const item of items()) expect(item.text).not.toMatch(BANNED[locale]);
      });
    });
  }

  it('refuses a missing, empty or surplus slot instead of rendering a hole', () => {
    const full = slotsFromLineage(lineage());
    const dropped = JSON.parse(JSON.stringify(full)); delete dropped.S3.reconciliation;
    const blank = JSON.parse(JSON.stringify(full)); blank.S5.v1_statement = '  ';
    const extra = JSON.parse(JSON.stringify(full)); extra.S1.price = '1';
    const group = JSON.parse(JSON.stringify(full)); delete group.S4;
    for (const slots of [dropped, blank, extra, group, null, [], 'x']) {
      expect(() => claimLimitText(slots as never, 'en', 'quick')).toThrow(ClaimTextError);
      expect(() => assertSlots(slots)).toThrow(ClaimTextError);
    }
    const lacking = lineage(); delete lacking.retrieval_time;
    expect(() => slotsFromLineage(lacking)).toThrow(ClaimTextError);
    expect(() => slotsFromLineage({ ...lineage(), retrieval_time: '' })).toThrow(ClaimTextError);
  });

  it('has a template for every item at every depth in both locales, and every placeholder names a real slot', () => {
    for (const locale of LOCALES) for (const depth of DEPTHS) {
      expect(Object.keys(TEMPLATES[locale][depth as Depth]).sort()).toEqual([...ITEM_IDS].sort());
      for (const template of Object.values(TEMPLATES[locale][depth])) {
        for (const match of template.matchAll(/\{([^}]*)\}/g)) {
          const [group, slot] = match[1].split('.');
          expect(SLOT_FIELDS[group]?.[slot], match[1]).toBeDefined();
        }
      }
    }
  });

  it('keeps the Quant ids per item equal to the server\'s (claim_render S_ITEMS, C_ITEMS, WITHHELD_S_ITEMS, WITHHELD_C_ITEMS)', () => {
    const source = readFileSync(new URL('../../src/marketdata/claim_render.py', import.meta.url), 'utf8');
    const printed = (name: string): Record<string, string[]> => {
      const body = source.split(`\n${name} = {`, 2)[1].split('}\n', 1)[0];
      return Object.fromEntries([...body.matchAll(/"(S\d|C\d)": \(([^)]*)\)/g)].map((m) => [m[1], [...m[2].matchAll(/"([^"]+)"/g)].map((q) => q[1])]));
    };
    expect({ ...printed('S_ITEMS'), ...printed('C_ITEMS') }).toEqual(QUANT_IDS.normal);
    expect({ ...printed('WITHHELD_S_ITEMS'), ...printed('WITHHELD_C_ITEMS') }).toEqual(QUANT_IDS.withheld);
  });

  it('refuses a block the server\'s contract refuses (TR-O7-L-3): a state that does not match the variant, two state slots that differ, other Quant ids', () => {
    expect(readClaimBlock(block(), REAL).items).toHaveLength(12);
    expect(readClaimBlock(withheldBlock(), REAL).items).toHaveLength(12);
    // the reviewer's two crafted blocks
    const normalOverInsufficient = block(); (normalOverInsufficient.slots as Record<string, Record<string, string>>).S3.state = 'INSUFFICIENT_DATA';
    expect(() => readClaimBlock(normalOverInsufficient, REAL)).toThrow(ApiError);
    const withheldMixed = withheldBlock(); (withheldMixed.slots as Record<string, Record<string, string>>).S1.state = 'AVAILABLE';
    (withheldMixed.slots as Record<string, Record<string, string>>).S3.state = 'BOGUS';
    expect(() => readClaimBlock(withheldMixed, REAL)).toThrow(ApiError);
    // the two state slots of the withheld variant must agree, and each be INSUFFICIENT_DATA
    const oneDiffers = withheldBlock(); (oneDiffers.slots as Record<string, Record<string, string>>).S1.state = 'LIMITED';
    expect(() => readClaimBlock(oneDiffers, REAL)).toThrow(ApiError);
    const otherDiffers = withheldBlock(); (otherDiffers.slots as Record<string, Record<string, string>>).S3.state = 'LIMITED';
    expect(() => readClaimBlock(otherDiffers, REAL)).toThrow(ApiError);
    // an unknown state in the normal variant
    const unknown = block(); (unknown.slots as Record<string, Record<string, string>>).S3.state = 'BOGUS';
    expect(() => readClaimBlock(unknown, REAL)).toThrow(ApiError);
    // the Quant ids of another variant, or an empty list, are refused
    const wrongIds = block(); wrongIds.items[0] = { ...wrongIds.items[0], quant_ids: ['C-1X'] };
    expect(() => readClaimBlock(wrongIds, REAL)).toThrow(ApiError);
    const withheldNormalIds = withheldBlock(); withheldNormalIds.items[2] = { ...withheldNormalIds.items[2], quant_ids: ['C-2', 'C-3', 'C-4'] };
    expect(() => readClaimBlock(withheldNormalIds, REAL)).toThrow(ApiError);
    const noIds = block(); noIds.items[3] = { ...noIds.items[3], quant_ids: [] };
    expect(() => readClaimBlock(noIds, REAL)).toThrow(ApiError);
  });

  it('TR-O7C-L-1: refuses slots that share one lineage field but disagree, and an item whose text or kind differs from the rendering; no partial render', () => {
    type S = Record<string, Record<string, string>>;
    const crafted: Array<[string, () => { slots: unknown }, (b: { slots: S; items: Array<Record<string, unknown>> }) => void]> = [
      ['normal S3.valuation_date', block, (b) => { b.slots.S3.valuation_date = '2025-04-03'; }],
      ['normal S1.valuation_date', block, (b) => { b.slots.S1.valuation_date = '2025-04-03'; }],
      ['normal S5.price_session_date', block, (b) => { b.slots.S5.price_session_date = '2025-04-01'; }],
      ['normal S1.price_session_date', block, (b) => { b.slots.S1.price_session_date = '2025-04-01'; }],
      ['normal S2.label_source', block, (b) => { b.slots.S2.label_source = 'OTHER'; }],
      ['normal S5.label_source', block, (b) => { b.slots.S5.label_source = 'OTHER'; }],
      ['normal S1.label_source', block, (b) => { b.slots.S1.label_source = 'OTHER'; }],
      ['normal S3.quantity', block, (b) => { b.slots.S3.quantity = '99'; }],
      ['normal S1.quantity', block, (b) => { b.slots.S1.quantity = '99'; }],
      ['withheld S3.valuation_date', withheldBlock, (b) => { b.slots.S3.valuation_date = '2025-04-03'; }],
      ['withheld S1.valuation_date', withheldBlock, (b) => { b.slots.S1.valuation_date = '2025-04-03'; }],
      ['normal item text replaced', block, (b) => { b.items[0].text = 'Something else entirely.'; }],
      ['normal item text with a trailing space', block, (b) => { b.items[4].text = `${b.items[4].text} `; }],
      ['normal C item text replaced', block, (b) => { b.items[9].text = 'That nothing is claimed.'; }],
      ['withheld item text replaced', withheldBlock, (b) => { b.items[2].text = 'Something else entirely.'; }],
      ['normal S item kind swapped', block, (b) => { b.items[0].kind = 'MAY_NOT_CLAIM'; }],
      ['normal C item kind swapped', block, (b) => { b.items[7].kind = 'MAY_CLAIM'; }],
      ['withheld item kind swapped', withheldBlock, (b) => { b.items[5].kind = 'MAY_CLAIM'; }],
      ['kind not a string', block, (b) => { b.items[1].kind = null; }],
    ];
    for (const [label, make, edit] of crafted) {
      const changed = make(); edit(changed as never);
      expect(() => readClaimBlock(changed, REAL), label).toThrow(ApiError);
      expect(() => readClaimBlock(changed, REAL), label).toThrow(expect.objectContaining({ code: 'INVALID_RESPONSE' }));
    }
    // assertSlots itself refuses the disagreeing slots, with the server's reason
    const disagree = block(); disagree.slots.S3.valuation_date = '2025-04-03';
    expect(() => assertSlots(disagree.slots)).toThrow(expect.objectContaining({ code: 'CLAIM_SLOTS_DISAGREE' }));
    // every block the server can produce still renders: both variants, each normal state, several withheld causes, and values that differ across FIELDS (not slots)
    const normalStates = ['AVAILABLE', 'LIMITED'];
    const causes = ['MISSING_PRICE_HISTORY', 'MISSING_FX_HISTORY', 'STALE_PRICE'];
    const slotsOf = (lin: Lineage) => slotsFromLineage(lin);
    const asBlock = (lin: Lineage, ids: Record<string, string[]>) => {
      const slots = slotsOf(lin);
      return { items: claimLimitText(slots, 'en', 'professional').map((item) => ({ id: item.id, kind: item.kind, quant_ids: ids[item.id], text: item.text })), slots, invented_data_mark: null };
    };
    for (const state of normalStates) {
      const lin = { ...lineage(), metric_state: state, valuation_date: '2025-04-04', price_session_date: '2025-04-03', ledger_quantity: '7', opening_cash: '100.5' };
      expect(readClaimBlock(asBlock(lin, QUANT_IDS.normal), REAL).items).toHaveLength(12);
    }
    expect(readClaimBlock(block(), REAL).items).toHaveLength(12);
    for (const cause of causes) {
      const lin = { ...withheldLineage(), nav_cause: cause, valuation_date: '2025-04-04', ledger_quantity: '7' };
      expect(readClaimBlock(asBlock(lin, QUANT_IDS.withheld), REAL).items).toHaveLength(12);
    }
    expect(readClaimBlock(withheldBlock(), REAL).items).toHaveLength(12);
    // a test-origin block is unaffected
    expect(readClaimBlock(testBlock(), TEST).items).toHaveLength(0);
  });

  it('TR8C-L-2: each check fires on its own: slots that disagree under item text consistent with them, and a truncated item text under agreeing slots', () => {
    type B = { slots: Record<string, Record<string, string>>; items: Array<{ id: string; text: string }> };
    const reText = (b: B, id: string, from: string, to: string) => {
      const item = b.items.find((candidate) => candidate.id === id)!;
      expect(item.text, `${id} names ${from}`).toContain(from);
      item.text = item.text.split(from).join(to);
    };
    // withheld: S1.valuation_date differs from S3's, and S1's own text follows its own slot (only the slot rule can refuse this)
    const withheld = withheldBlock() as unknown as B;
    const wFrom = withheld.slots.S1.valuation_date;
    withheld.slots.S1.valuation_date = '2025-04-03'; reText(withheld, 'S1', wFrom, '2025-04-03');
    expect(() => readClaimBlock(withheld, REAL)).toThrow(ApiError);
    expect(() => assertSlots(withheld.slots)).toThrow(expect.objectContaining({ code: 'CLAIM_SLOTS_DISAGREE' }));
    // normal: S1.price_session_date differs from S5's, with S1's text consistent
    const normal = block() as unknown as B;
    const nFrom = normal.slots.S1.price_session_date;
    normal.slots.S1.price_session_date = '2025-04-01'; reText(normal, 'S1', nFrom, '2025-04-01');
    expect(() => readClaimBlock(normal, REAL)).toThrow(ApiError);
    expect(() => assertSlots(normal.slots)).toThrow(expect.objectContaining({ code: 'CLAIM_SLOTS_DISAGREE' }));
    // an S4 item that dropped the seal-limit sentence, slots agreeing: refused by the text rule alone
    for (const make of [block, withheldBlock]) {
      const cut = make() as unknown as B;
      const s4 = cut.items.find((item) => item.id === 'S4')!;
      const at = s4.text.indexOf(' The seal that stores');
      expect(at).toBeGreaterThan(0);
      s4.text = s4.text.slice(0, at);
      expect(() => assertSlots(cut.slots)).not.toThrow();
      expect(() => readClaimBlock(cut, REAL)).toThrow(ApiError);
    }
  });

  it('keeps the slot tables equal to the server\'s (claim_render.SLOT_FIELDS and WITHHELD_SLOT_FIELDS) by the mapping it prints', () => {
    const source = readFileSync(new URL('../../src/marketdata/claim_render.py', import.meta.url), 'utf8');
    const printed = (name: string) => source.split(`${name} = {`, 2)[1].split('\n}\n', 1)[0];
    for (const [name, table] of [['SLOT_FIELDS', SLOT_FIELDS], ['WITHHELD_SLOT_FIELDS', WITHHELD_SLOT_FIELDS]] as const) {
      const body = printed(name);
      for (const [group, mapping] of Object.entries(table)) for (const [slot, field] of Object.entries(mapping)) {
        if (name === 'WITHHELD_SLOT_FIELDS' && group === 'S4') continue;                                  // the server's WITHHELD S4 IS its normal S4 (a reference)
        expect(body, `${name} ${group}.${slot}`).toContain(`"${slot}": "${field}"`);
      }
      // the server's table has no slot that the client's lacks (counted by the printed pairs of each group)
      expect((body.match(/"[a-z_0-9]+": "[a-z_0-9]+"/g) ?? []).length, name).toBe(
        Object.entries(table).filter(([group]) => !(name === 'WITHHELD_SLOT_FIELDS' && group === 'S4')).reduce((n, [, mapping]) => n + Object.keys(mapping).length, 0));
    }
    expect(WITHHELD_SLOT_FIELDS.S4).toEqual(SLOT_FIELDS.S4);
    expect(source).toContain('"S4": SLOT_FIELDS["S4"]');
  });

  describe('the WITHHELD variant (a real NAV in state INSUFFICIENT_DATA)', () => {
    const WITHHELD_PHRASES: Record<Locale, Record<string, string[]>> = {
      en: { ...PHRASES.en, S1: ['No holding value'], S2: ['No label source'], S3: ['No NAV', 'freshness', 'delay'], S5: ['No label status'],
        C1: ['split', 'dividend component', 'verified'], C2: ['closing-cross'], C3: ['compared', 'other source'] },
      'zh-CN': { ...PHRASES['zh-CN'], S1: ['持仓市值', '未予陈述', '资产净值'], S2: ['未陈述标签来源'], S3: ['资产净值', '未予陈述', '新鲜度', '延迟'], S5: ['未陈述标签状态'],
        C1: ['拆股调整标签', '股息调整部分', '已核实'], C2: ['收盘集合竞价价格'], C3: ['比较', '其他来源'] },
    };
    const lacking = (items: { id: string; text: string }[], locale: Locale): string[] => ITEM_IDS.flatMap((id) => {
      const item = items.find((candidate) => candidate.id === id);
      return item ? WITHHELD_PHRASES[locale][id].filter((phrase) => !item.text.includes(phrase)).map((phrase) => `${id} lacks ${phrase}`) : [`missing ${id}`];
    });

    it('is picked by the shape of the slots, and the slots are the withheld mapping\'s', () => {
      const slots = slotsFromLineage(withheldLineage());
      expect(variantOfSlots(slots)).toBe('withheld');
      expect(variantOfSlots(slotsFromLineage(lineage()))).toBe('normal');
      expect(Object.keys(slots).sort()).toEqual(['S1', 'S2', 'S3', 'S4', 'S5']);
      expect(slots.S2).toEqual({});
      expect(slots.S5).toEqual({});
      expect(slots.S3.nav_cause).toBe('MISSING_PRICE_HISTORY');
      expect(() => assertSlots(slots)).not.toThrow();
    });

    for (const locale of LOCALES) for (const depth of DEPTHS) {
      it(`${locale} / ${depth}: carries the twelve ids, its own required phrases, and no price, label, window or reconciliation sentence`, () => {
        const items = claimLimitText(slotsFromLineage(withheldLineage()), locale, depth);
        expect(items.map((item) => item.id)).toEqual(ITEM_IDS);
        expect(lacking(items, locale)).toEqual([]);
        const by = Object.fromEntries(items.map((item) => [item.id, item.text]));
        expect(by.S3).toContain('INSUFFICIENT_DATA');
        expect(by.S3).toContain('MISSING_PRICE_HISTORY');
        for (const id of ['S1', 'S2', 'S3', 'S5']) {
          expect(by[id], id).not.toMatch(/ x p|\bRAW\b|SINGLE_SOURCE|reconciliation|对账|E\(/);                // no number formula, no label, no window, no reconciliation
          expect(by[id], id).not.toMatch(/[{}]/);
        }
        expect(by.S4).toContain('LV<file_hashes>');
        expect(by.C6).toContain('LV<ledger_quantity>');
      });
    }

    it('fails the phrase check when an item or one of its phrases is removed', () => {
      const items = claimLimitText(slotsFromLineage(withheldLineage()), 'en', 'professional');
      for (const id of ITEM_IDS) {
        expect(lacking(items.filter((item) => item.id !== id), 'en')).toContain(`missing ${id}`);
        for (const phrase of WITHHELD_PHRASES.en[id]) {
          const without = items.map((item) => (item.id === id ? { ...item, text: item.text.split(phrase).join('') } : item));
          expect(lacking(without, 'en')).toContain(`${id} lacks ${phrase}`);
        }
      }
    });

    it('zh templates of both variants use the R-10 and F-7 terms at every depth', () => {
      for (const tables of [TEMPLATES['zh-CN'], TEMPLATES_WITHHELD['zh-CN']]) for (const depth of DEPTHS) {
        for (const [id, text] of Object.entries(tables[depth])) expect(text, `${depth} ${id}`).not.toMatch(/净资产|(?<!资产)净值|持仓价值/);
      }
    });

    it('has a template for every item at every depth, and every placeholder names a slot of the withheld mapping', () => {
      for (const locale of LOCALES) for (const depth of DEPTHS) {
        expect(Object.keys(TEMPLATES_WITHHELD[locale][depth]).sort()).toEqual([...ITEM_IDS].sort());
        for (const template of Object.values(TEMPLATES_WITHHELD[locale][depth])) {
          for (const match of template.matchAll(/\{([^}]*)\}/g)) {
            const [group, slot] = match[1].split('.');
            expect(WITHHELD_SLOT_FIELDS[group]?.[slot], match[1]).toBeDefined();
          }
        }
      }
    });

    it('refuses slots that mix the two variants, and a slot that is absent or empty', () => {
      const withheld = slotsFromLineage(withheldLineage());
      const normal = slotsFromLineage(lineage());
      const mixed = JSON.parse(JSON.stringify(normal)); mixed.S3.nav_cause = 'MISSING_PRICE_HISTORY';              // a normal S3 that also names a cause
      const surplus = JSON.parse(JSON.stringify(withheld)); surplus.S2.label_source = 'DECLARED';                  // a withheld S2 that names a label source
      const noCause = JSON.parse(JSON.stringify(withheld)); delete noCause.S3.nav_cause;                            // no cause: the shape of no variant but normal's, which lacks S3 slots
      const blank = JSON.parse(JSON.stringify(withheld)); blank.S3.nav_cause = ' ';
      for (const slots of [mixed, surplus, noCause, blank]) expect(() => claimLimitText(slots, 'en', 'quick')).toThrow(ClaimTextError);
      expect(() => slotsFromLineage({ ...withheldLineage(), nav_cause: '' })).toThrow(ClaimTextError);
    });
  });
});

describe('what the screen shows, by the stored origin', () => {
  const t = translator('en', createTranslator());
  const html = (element: Parameters<typeof renderToStaticMarkup>[0]) => renderToStaticMarkup(element);

  it('over a real origin shows the real labels and the claim text, and never the invented-data mark', () => {
    for (const locale of LOCALES) {
      const tr = translator(locale, createTranslator());
      const banner = html(createElement(OriginBanner, { origin: REAL, labels: REAL_LABELS, locale, t: tr }));
      expect(banner).toContain('data-origin-kind="REAL_SOURCE_CONSTRUCTED_ACCOUNT"');
      expect(banner).toContain(locale === 'en' ? REAL_LABELS.origin_statement : realOriginZh.REAL_SOURCE_CONSTRUCTED_ACCOUNT.origin_statement);
      expect(banner).not.toMatch(BANNED[locale]);
      for (const depth of DEPTHS) {
        const claims = html(createElement(ClaimLimits, { block: block(locale), origin: REAL, locale, depth, t: tr }));
        expect(claims).toContain('data-claim-id="C1"');
        expect(claims).toContain('UNVERIFIABLE');
        expect(claims).not.toContain('invented-data-mark');
        expect(claims).not.toMatch(BANNED[locale]);
      }
    }
  });

  it('over test data shows the invented-data mark, no real-source sentence and no real-origin label', () => {
    for (const locale of LOCALES) {
      const tr = translator(locale, createTranslator());
      const banner = html(createElement(OriginBanner, { origin: TEST, labels: TEST_LABELS, locale, t: tr }));
      expect(banner).toContain('data-origin-kind="INVENTED_TEST_DATA"');
      expect(banner).toContain(testOrigin[locale].banner);
      expect(banner).not.toContain('real-origin');
      expect(banner).not.toContain(REAL_LABELS.origin_statement);
      expect(banner).not.toContain(realOriginZh.REAL_SOURCE_CONSTRUCTED_ACCOUNT.origin_statement);
      expect(banner).not.toContain('REAL_SOURCE_CONSTRUCTED_ACCOUNT');
      for (const depth of DEPTHS) {
        const claims = html(createElement(ClaimLimits, { block: testBlock(), origin: TEST, locale, depth, t: tr }));
        expect(claims).toContain(locale === 'en' ? MARK : testOrigin['zh-CN'].mark);
        for (const sentence of ['RAW', 'closing-cross', 'UNVERIFIABLE', 'SINGLE_SOURCE', 'dividend', 'Alpha', 'XNAS', '收盘集合竞价', '股息', '供应商']) {
          expect(claims, sentence).not.toContain(sentence);
        }
        expect(claims).not.toContain('data-claim-id');
      }
    }
    expect(html(createElement(RootEntries, { entries: [{ root_id: UUID_A, context_id: HEX('c'), generation: 1, created_at: 'x', origin: TEST }], locale: 'en', t, busy: false })))
      .not.toContain('Real source');
  });

  it('fails closed when a real block\'s slots cannot fill the text: an alert and no claim text', () => {
    const broken = { ...block(), slots: { ...block().slots, S3: { ...block().slots.S3, reconciliation: '' } } };
    const out = html(createElement(ClaimLimits, { block: broken as never, origin: REAL, locale: 'en', depth: 'quick', t }));
    expect(out).toContain('role="alert"');
    expect(out).not.toContain('data-claim-id');
  });

  it('shows the claim block of a stored real root in the detail view at each depth', () => {
    const root = readRoot(createdFixture(REAL, REAL_LABELS, block()), 'created');
    for (const depth of DEPTHS) {
      const out = html(createElement(RootDetail, { root, locale: 'zh-CN', depth, t: translator('zh-CN', createTranslator()) }));
      expect(out).toContain('data-depth="' + depth + '"');
      expect(out).toContain(root.issued_sha256);
    }
  });

  describe('the root\'s generation (HG4 condition 2, PD-0089; design G3, G5)', () => {
    const RAW_NOTE = { en: common.en.generationNote, 'zh-CN': common['zh-CN'].generationNote };
    const NOTE = { en: RAW_NOTE.en.replace(/'/g, '&#x27;'), 'zh-CN': RAW_NOTE['zh-CN'] };       // as rendered (React escapes the apostrophe)
    const NOW = { en: 'Context now at generation', 'zh-CN': '上下文当前代次' };
    const CREATED = { en: 'Created under generation', 'zh-CN': '创建时所在代次' };
    const stripNote = (out: string) => out.replace(/<p class="generation-note">.*?<\/p>/, '');
    const readable = { root_id: UUID_A, context_id: HEX('c'), generation: 3, created_at: '2026-11-16T00:00:00+00:00', origin: REAL };
    const listHtml = (entries: never[] | object[], locale: Locale) => html(createElement(RootEntries, { entries: entries as never, locale, t: translator(locale, createTranslator()), busy: false }));

    it('names the list\'s number as the context\'s current generation, beside the unchanged creation time, and never as bare "Generation"', () => {
      for (const locale of LOCALES) {
        const out = listHtml([readable], locale);
        expect(out).toContain(`${NOW[locale]} 3 · ${locale === 'en' ? 'Created' : '创建时间'} 2026-11-16T00:00:00+00:00`);
        const withoutNote = stripNote(out);
        // Outside the note, the only mention is the one labelled "now" (no bare "Generation" next to a root).
        expect(withoutNote.replace(NOW[locale], '')).not.toMatch(/[Gg]eneration|代次/);
        expect(withoutNote.split(NOW[locale])).toHaveLength(2);
      }
    });
    it('shows the explanatory note once above the list, in both locales, and not in the empty state', () => {
      for (const locale of LOCALES) {
        const out = listHtml([readable, { ...readable, root_id: UUID_B, generation: 3 }], locale);
        expect(out.split(NOTE[locale])).toHaveLength(2);
        expect(out.indexOf(NOTE[locale])).toBeLessThan(out.indexOf('<ul'));
        const empty = listHtml([], locale);
        expect(empty).not.toContain(NOTE[locale]);
        expect(empty).not.toContain(NOW[locale]);
      }
      expect(NOTE.en).toMatch(/not a property of a root/);
      expect(NOTE.en).toMatch(/does not create, re-bind or change a stored root/);
      expect(NOTE['zh-CN']).toMatch(/不是根的属性/);
      expect(NOTE['zh-CN']).toMatch(/不会创建、重新绑定或更改已保存的根/);
    });
    it('keeps a refused entry as it was: the code, and no generation', () => {
      for (const locale of LOCALES) {
        const out = listHtml([{ root_id: UUID_A, context_id: HEX('c'), status: 'RW_WITHDRAWN' }], locale);
        expect(out).toContain('RW_WITHDRAWN');
        expect(out).toContain(translator(locale, createTranslator())('refusedEntry'));
        expect(out).not.toContain(NOW[locale]);
        expect(stripNote(out)).not.toMatch(/Created|创建时间|[Gg]eneration|代次/);
      }
    });
    it('shows "Created under generation N" in the opened result at every depth, in both locales (the R8 case: created at 1, context now at 3)', () => {
      const read = createdFixture(REAL, REAL_LABELS, block()) as Record<string, unknown>;
      delete read.replayed; read.schema_version = 'finweb.cp7.real_scoped_read/2'; read.created_under_generation = 1;
      const root = readRoot(read, 'read');
      for (const locale of LOCALES) {
        expect(listHtml([readable], locale)).toContain(`${NOW[locale]} 3`);
        for (const depth of DEPTHS) {
          const out = html(createElement(RootDetail, { root, locale, depth, t: translator(locale, createTranslator()) }));
          expect(out).toContain(`<dt>${CREATED[locale]}</dt><dd>1</dd>`);
          expect(out).not.toContain(NOW[locale]);
        }
      }
    });
    it('shows no created-under row on a create result (it carries none), and the retired bare key is gone', () => {
      const root = readRoot(createdFixture(REAL, REAL_LABELS, block()), 'created');
      for (const locale of LOCALES) {
        expect(html(createElement(RootDetail, { root, locale, depth: 'quick', t: translator(locale, createTranslator()) }))).not.toContain(CREATED[locale]);
      }
      expect('generation' in common.en).toBe(false);
      expect('generation' in common['zh-CN']).toBe(false);
    });
  });
});

describe('the phrases the browser spec forbids over TEST data', () => {
  it('occur in no client string that is not claim text, and each occurs in the claim templates or the real origin labels', () => {
    const nonClaim = [...Object.values(common.en), ...Object.values(common['zh-CN']), ...Object.values(testOrigin.en), ...Object.values(testOrigin['zh-CN']),
      ...Object.values(testOriginZh.INVENTED_TEST_DATA), ...Object.values(refusalZh), TEST_LABELS.origin_statement, TEST_LABELS.holding_statement,
      readFileSync(new URL('./RealModeApp.tsx', import.meta.url), 'utf8')];
    const claimAndLabels = [...LOCALES.flatMap((l) => DEPTHS.flatMap((d) => Object.values(TEMPLATES[l][d]))), REAL_LABELS.origin_statement,
      REAL_LABELS.holding_statement, ...Object.values(realOriginZh.REAL_SOURCE_CONSTRUCTED_ACCOUNT), 'REAL_SOURCE_CONSTRUCTED_ACCOUNT'].join('\n');
    expect(REAL_SENTENCES.length).toBeGreaterThan(10);
    for (const phrase of REAL_SENTENCES) {
      for (const text of nonClaim) expect(text, `"${phrase}" collides with a non-claim string`).not.toContain(phrase);
      expect(claimAndLabels, `"${phrase}" is in no claim template or real label`).toContain(phrase);
    }
    expect(nonClaim.some((text) => text.includes('constructed by the project for testing'))).toBe(true);     // the collision the list once had: the control
  });
});

describe('no permanent client string states a real origin (TR7-M-1)', () => {
  // A permanent string renders over TEST data too. The drift guard above cannot forbid a phrase that sits in one, so this test forbids real-origin wording
  // in all of them directly: the common, test-origin and refusal tables, the page's own HTML, and the app source apart from the one entry tag that is
  // rendered only when the stored origin is real.
  // Origin wording only. "Real mode" (the name of this app's mode: 该路由在真实模式下已关闭) and the refusal 真实数据工作区当前不可用 ("the real-data
  // workspace is unavailable") name a workspace, not the origin of a result, and are not matched.
  const REAL_WORDING = /real[- ]source|real origin|from a real|real market|真实来源|真实数据/i;
  const permanent = (htmlSource: string, appSource: string): string[] => [
    // The test origin's own mark and statements are excluded: they negate a real source on purpose ("no claim about any real source").
    // refusalZh is excluded too: some refusals name the real source in the negative (金融服务拒绝对非真实来源的市场数据估值), and they render only on a refusal.
    ...Object.values(common.en), ...Object.values(common['zh-CN']), htmlSource, appSource.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '').split('\n').filter((line) => !line.includes('isRealOrigin(entry.origin) ?')).join('\n')];
  const realHtml = () => readFileSync(new URL('../real.html', import.meta.url), 'utf8');
  const appSource = () => readFileSync(new URL('./RealModeApp.tsx', import.meta.url), 'utf8');

  it('holds for every permanent string and for real.html', () => {
    for (const text of permanent(realHtml(), appSource())) {
      expect(text, text.slice(0, 80)).not.toMatch(REAL_WORDING);
      for (const label of [REAL_LABELS.origin_statement, REAL_LABELS.holding_statement, 'REAL_SOURCE_CONSTRUCTED_ACCOUNT',
        ...Object.values(realOriginZh.REAL_SOURCE_CONSTRUCTED_ACCOUNT)]) expect(text).not.toContain(label);
    }
  });
  it('TR7F-L-5: holds for the test-origin table too, every string but the two deliberate negations, which are allowed by exact string', () => {
    const ALLOWED = ['Invented test data; no claim about any real source.', '测试用虚构数据；不对任何真实来源作出声明。'];
    expect([testOrigin.en.mark, testOrigin['zh-CN'].mark]).toEqual(ALLOWED);
    for (const locale of ['en', 'zh-CN'] as const) {
      for (const [key, text] of Object.entries(testOrigin[locale])) {
        if (ALLOWED.includes(text)) { expect(key).toBe('mark'); continue; }
        expect(text, `${locale}.${key}`).not.toMatch(REAL_WORDING);
      }
    }
  });
  it('TR7F-L-5: the guard bites on the test-origin strings (figuresNone en and zh, the TEST rawNote, figuresNote)', () => {
    const flagged = (en: Partial<Record<string, string>>, zh: Partial<Record<string, string>>) => [...Object.entries({ ...testOrigin.en, ...en }), ...Object.entries({ ...testOrigin['zh-CN'], ...zh })]
      .some(([key, text]) => key !== 'mark' && REAL_WORDING.test(text));
    expect(flagged({}, {})).toBe(false);
    expect(flagged({ figuresNone: testOrigin.en.figuresNone + ' Real source.' }, {})).toBe(true);
    expect(flagged({}, { figuresNone: testOrigin['zh-CN'].figuresNone + '真实来源。' })).toBe(true);
    expect(flagged({ rawNote: 'It comes from a real source' }, {})).toBe(true);
    expect(flagged({ figuresNote: testOrigin.en.figuresNote + ' Real market data.' }, {})).toBe(true);
    expect(flagged({}, { rawNote: testOrigin['zh-CN'].rawNote + '真实数据' })).toBe(true);
  });
  it('fails on the old title, in the strings and in real.html', () => {
    const oldEn = { ...common.en, title: 'Real-source portfolio' };
    const oldZh = { ...common['zh-CN'], title: '真实来源组合' };
    expect(Object.values(oldEn).some((text) => REAL_WORDING.test(text))).toBe(true);
    expect(Object.values(oldZh).some((text) => REAL_WORDING.test(text))).toBe(true);
    expect(REAL_WORDING.test(realHtml().replace('Stored results', 'Real-source portfolio'))).toBe(true);
    expect(common.en.title).toBe('Stored results');
    expect(common['zh-CN'].title).toBe('已存结果');
  });
  it('renders no real-origin wording in the first screen of the app in either language', () => {
    expect(renderToStaticMarkup(createElement(RealModeApp))).not.toMatch(REAL_WORDING);
  });
});

describe('the widened-wording test on the client strings (fact 11)', () => {
  it('has no fictional, sandbox, synthetic or invented wording in any string a real root\'s screen uses', () => {
    for (const locale of LOCALES) {
      const strings = [...Object.values(common[locale]), ...Object.values(refusalZh).filter(() => locale === 'zh-CN'),
        ...Object.values(realOriginZh).flatMap((v) => Object.values(v)).filter(() => locale === 'zh-CN'),
        ...Object.values(TEMPLATES[locale]).flatMap((table) => Object.values(table)), REAL_LABELS.origin_statement, REAL_LABELS.holding_statement];
      for (const text of strings) expect(text, text).not.toMatch(BANNED[locale]);
    }
  });
  it('keeps the wording that the test origin needs in its own table, and the regexes do bite', () => {
    expect(testOrigin.en.mark).toMatch(BANNED.en);
    expect(testOrigin['zh-CN'].mark).toMatch(BANNED['zh-CN']);
    expect(Object.values(testOriginZh.INVENTED_TEST_DATA).join()).toMatch(BANNED['zh-CN']);
    expect(Object.values(common.en).join()).not.toContain('nvented');
  });
  it('renders the whole first screen, both languages, without that wording', () => {
    const out = renderToStaticMarkup(createElement(RealModeApp));
    expect(out).not.toMatch(BANNED.en);
    expect(out).toContain(common.en.signIn);
  });
  it('has no import of the fictional account client, its list type or its mode string', () => {
    for (const file of ['real-mode.ts', 'real-mode-claims.ts', 'real-mode-i18n.ts', 'RealModeApp.tsx', 'real-main.tsx']) {
      const source = readFileSync(new URL(`./${file}`, import.meta.url), 'utf8');
      for (const banned of ['./account', 'AccountPanel', 'SavedPortfolio', 'LOCAL_SYNTHETIC', '/api/v1/portfolios', '/api/v1/real-', './i18n\'']) {
        expect(source, `${file}: ${banned}`).not.toContain(banned);
      }
    }
  });
});

function createdFixture(origin: Origin, labels: object, claims: object, extra: object = {}) {
  return { schema_version: 'finweb.cp7.real_scoped_create_result/1', state: 'COMMITTED', persisted: true, replayed: false, root_id: UUID_A, operation_id: UUID_B,
    revision_id: UUID_A, ledger_pin: 2, origin: structuredClone(origin), labels: structuredClone(labels), response_sha256: HEX('a'), issued_sha256: HEX('b'),
    result: { metrics: [] }, claim_limits: structuredClone(claims), ...extra };
}

describe('strict readers', () => {
  it('accepts the contract shapes', () => {
    expect(readRoot(createdFixture(REAL, REAL_LABELS, block()), 'created').origin).toEqual(REAL);
    expect(readRoot(createdFixture(TEST, TEST_LABELS, testBlock()), 'created').claim_limits.items).toEqual([]);
    const read = createdFixture(REAL, REAL_LABELS, block()) as Record<string, unknown>;
    delete read.replayed; read.schema_version = 'finweb.cp7.real_scoped_read/2'; read.created_under_generation = 1;
    expect(readRoot(read, 'read').root_id).toBe(UUID_A);
    expect(readRoot(read, 'read').created_under_generation).toBe(1);
    expect(readRoot(createdFixture(REAL, REAL_LABELS, block()), 'created').created_under_generation).toBeUndefined();
  });
  it('requires the read result\'s created_under_generation: an integer, at least 1, within the safe-integer range (HG4 condition 2)', () => {
    const base = () => { const v = createdFixture(REAL, REAL_LABELS, block()) as Record<string, unknown>; delete v.replayed; v.schema_version = 'finweb.cp7.real_scoped_read/2'; return v; };
    const missingField = base();
    expect(() => readRoot(missingField, 'read')).toThrow(ApiError);
    for (const bad of [0, -1, 1.5, '1', null, true, Number.MAX_SAFE_INTEGER + 1, Number.NaN]) {
      const v = base(); v.created_under_generation = bad;
      expect(() => readRoot(v, 'read'), String(bad)).toThrow(ApiError);
    }
    const ok = base(); ok.created_under_generation = Number.MAX_SAFE_INTEGER;
    expect(readRoot(ok, 'read').created_under_generation).toBe(Number.MAX_SAFE_INTEGER);
    const old = base(); old.created_under_generation = 1; old.schema_version = 'finweb.cp7.real_scoped_read/1';
    expect(() => readRoot(old, 'read')).toThrow(ApiError);
    const onCreate = createdFixture(REAL, REAL_LABELS, block(), { created_under_generation: 1 });
    expect(() => readRoot(onCreate, 'created')).toThrow(ApiError);
  });
  it('refuses a root that deviates in any way', () => {
    const ok = () => createdFixture(REAL, REAL_LABELS, block()) as Record<string, unknown>;
    const mutants: Record<string, (v: Record<string, unknown>) => void> = {
      'an extra key': (v) => { v.extra = 1; }, 'a missing key': (v) => { delete v.labels; }, 'wrong schema': (v) => { v.schema_version = 'x'; },
      'not persisted': (v) => { v.persisted = false; }, 'a short digest': (v) => { v.issued_sha256 = 'a'; }, 'a bad id': (v) => { v.root_id = 'x'; },
      'a float pin': (v) => { v.ledger_pin = 1.5; }, 'a personal-holdings origin': (v) => { (v.origin as Origin).personal_holdings = true; },
      'a contradictory origin': (v) => { (v.origin as Origin).synthetic = true; },
      'labels of another origin': (v) => { v.labels = TEST_LABELS; },
      'an empty label': (v) => { (v.labels as Record<string, string>).origin_statement = ''; },
      'a block with a missing item': (v) => { (v.claim_limits as { items: unknown[] }).items.pop(); },
      'a block with the mark': (v) => { (v.claim_limits as { invented_data_mark: string }).invented_data_mark = MARK; },
      'a slot group gone': (v) => { delete ((v.claim_limits as { slots: Record<string, unknown> }).slots).S2; },
    };
    for (const [label, mutate] of Object.entries(mutants)) {
      const value = ok(); mutate(value);
      expect(() => readRoot(value, 'created'), label).toThrow(ApiError);
    }
    const testWith = (change: (b: ReturnType<typeof testBlock>) => void) => { const b = testBlock(); change(b); return createdFixture(TEST, TEST_LABELS, b); };
    expect(() => readRoot(testWith((b) => { (b.slots as Record<string, string>).S3 = 'other'; }), 'created')).toThrow(ApiError);
    expect(() => readRoot(testWith((b) => { (b.items as unknown[]).push({}); }), 'created')).toThrow(ApiError);
    expect(() => readRoot(testWith((b) => { b.invented_data_mark = ''; }), 'created')).toThrow(ApiError);
  });
  it('reads origins, labels and the claim block on their own', () => {
    expect(readOrigin(REAL)).toEqual(REAL);
    expect(() => readOrigin({ ...REAL, extra: 1 })).toThrow(ApiError);
    expect(() => readOrigin({ market_origin: 'REAL_SOURCE', ledger_origin: 'INVENTED_TEST_LEDGER', personal_holdings: false, synthetic: false })).toThrow(ApiError);
    expect(() => readLabels(TEST_LABELS, REAL)).toThrow(ApiError);
    expect(() => readClaimBlock({ items: [], slots: {}, invented_data_mark: null }, REAL)).toThrow(ApiError);
  });
  it('reads the reproduction: a digest is required unless the source refused or the input mismatched', () => {
    const base = { schema_version: 'finweb.cp7.real_scoped_reproduce/1', root_id: UUID_A, operation_id: UUID_B, origin: REAL, labels: REAL_LABELS, status: 'REPRODUCED', detail: '', issued_sha256: HEX('b') };
    expect(readReproduction(base).status).toBe('REPRODUCED');
    for (const status of ['INPUT_MISMATCH', 'SOURCE_REFUSED']) expect(readReproduction({ ...base, status, detail: 'd', issued_sha256: null }).issued_sha256).toBeNull();
    for (const status of ['REPRODUCED', 'RESULT_DIFFERS']) expect(() => readReproduction({ ...base, status, issued_sha256: null })).toThrow(ApiError);
    expect(() => readReproduction({ ...base, status: 'MAYBE' })).toThrow(ApiError);
  });
  it('reads the list: readable entries and refused entries, nothing else', () => {
    const good = { schema_version: 'finweb.cp7.real_scoped_list/2', roots: [
      { root_id: UUID_A, operation_id: UUID_B, context_id: HEX('c'), generation: 3, created_at: '2026-01-05T00:00:00+00:00', origin: TEST },
      { root_id: UUID_B, context_id: HEX('d'), status: 'RW_WITHDRAWN' }] };
    expect(readRootList(good)).toHaveLength(2);
    expect(readRootList(good)[0].operation_id).toBe(UUID_B);                                       // DR-R8-1: the list carries the stored create operation id
    const { operation_id: _gone, ...noOperation } = good.roots[0] as Record<string, unknown>;
    expect(() => readRootList({ ...good, roots: [noOperation] })).toThrow(ApiError);               // a readable entry without it is refused, not repaired
    expect(() => readRootList({ ...good, roots: [{ ...good.roots[0], operation_id: 'not-a-uuid' }] })).toThrow(ApiError);
    expect(() => readRootList({ ...good, roots: [{ ...good.roots[1], operation_id: UUID_A }] })).toThrow(ApiError);   // a refused entry carries none
    expect(readRootList({ ...good, roots: [] })).toEqual([]);
    expect(() => readRootList({ ...good, roots: [{ ...good.roots[1], origin: TEST }] })).toThrow(ApiError);
    expect(() => readRootList({ ...good, roots: [{ ...good.roots[0], generation: 'x' }] })).toThrow(ApiError);
    expect(() => readRootList({ ...good, extra: 1 })).toThrow(ApiError);
    expect(() => readRootList({ schema_version: 'x', roots: [] })).toThrow(ApiError);
  });
  it('reads the session and builds the create body exactly as the contract\'s intent', () => {
    expect(readSession({ schema_version: 'finweb.cp7/1', authenticated: false, user: null, csrf_token: HEX('e') }).authenticated).toBe(false);
    expect(() => readSession({ schema_version: 'finweb.cp7/1', authenticated: true, user: null, csrf_token: HEX('e') })).toThrow(ApiError);
    const body = createBody({ contextId: HEX('c'), releaseId: HEX('d'), listingId: UUID_A, name: 'n', asOf: '2026-01-05', quantity: '2', cash: '20', currency: 'USD' }, UUID_B);
    expect(Object.keys(body).sort()).toEqual(['as_of', 'constructed_ledger_acknowledged', 'expected_release_id', 'name', 'opening_cash', 'opening_positions', 'operation_id',
      'reporting_currency', 'schema_version', 'source_context_id']);
    expect(body.constructed_ledger_acknowledged).toBe(true);
    expect(JSON.stringify(body)).not.toContain('mode');
  });
});

describe('the transport', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  const json = (status: number, value: unknown) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

  it('talks only to the auth routes and the four scoped routes, with the CSRF header on every write', async () => {
    const calls: { path: string; method: string; csrf: string | null }[] = [];
    const session = { schema_version: 'finweb.cp7/1', authenticated: true, user: { user_id: UUID_A, username: 'someone' }, csrf_token: HEX('e') };
    vi.stubGlobal('fetch', async (path: string, init: RequestInit) => {
      calls.push({ path, method: String(init.method), csrf: (init.headers as Record<string, string>)['X-Finweb-CSRF'] ?? null });
      if (path.endsWith('/auth/session')) return json(200, { ...session, authenticated: false, user: null });
      if (path.endsWith('/auth/register')) return json(201, session);
      if (path.endsWith('/reproduce')) return json(200, { schema_version: 'finweb.cp7.real_scoped_reproduce/1', root_id: UUID_A, operation_id: UUID_B, origin: TEST, labels: TEST_LABELS,
        status: 'REPRODUCED', detail: '', issued_sha256: HEX('b') });
      if (path.endsWith('/roots') && init.method === 'GET') return json(200, { schema_version: 'finweb.cp7.real_scoped_list/2', roots: [] });
      if (path.endsWith('/roots')) return json(201, createdFixture(TEST, TEST_LABELS, testBlock()));
      return json(200, (() => { const v = createdFixture(TEST, TEST_LABELS, testBlock()) as Record<string, unknown>; delete v.replayed; v.schema_version = 'finweb.cp7.real_scoped_read/2'; v.created_under_generation = 1; return v; })());
    });
    const api = new RealModeApi();
    await api.credentials('register', 'someone', 'a long disposable password');
    expect(await api.list()).toEqual([]);
    const created = await api.create(createBody({ contextId: HEX('c'), releaseId: HEX('d'), listingId: UUID_A, name: 'n', asOf: '2026-01-05', quantity: '2', cash: '20', currency: 'USD' }, UUID_B));
    expect(created.root_id).toBe(UUID_A);
    await api.read(UUID_A, UUID_B);
    expect((await api.reproduce(UUID_A, UUID_B)).status).toBe('REPRODUCED');
    const allowed = /^\/api\/(v1\/auth\/(session|register|login|logout)|real\/v1\/roots(\/[0-9a-f-]{36}\/operations\/[0-9a-f-]{36}(\/reproduce)?)?)$/;
    for (const call of calls) expect(call.path, call.path).toMatch(allowed);
    for (const call of calls.filter((c) => c.method === 'POST')) expect(call.csrf, call.path).toBe(HEX('e'));
    expect(calls.filter((c) => c.method === 'GET').every((c) => c.csrf === null)).toBe(true);
  });

  it('keeps the operation id and the exact body of a create whose outcome is unknown, and reports a session loss', async () => {
    vi.stubGlobal('fetch', async (path: string) => {
      if (path.endsWith('/auth/session')) return json(200, { schema_version: 'finweb.cp7/1', authenticated: false, user: null, csrf_token: HEX('e') });
      return json(503, { schema_version: 'finweb.cp7.real_scoped_unknown/1', state: 'UNKNOWN', operation_id: UUID_B, retried: false, next: 'repeat' });
    });
    const api = new RealModeApi();
    await api.session();
    const body = createBody({ contextId: HEX('c'), releaseId: HEX('d'), listingId: UUID_A, name: 'n', asOf: '2026-01-05', quantity: '2', cash: '20', currency: 'USD' }, UUID_B);
    const failure = await api.create(body).catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(UnknownOutcome);
    expect((failure as UnknownOutcome).operationId).toBe(UUID_B);
    expect(JSON.parse((failure as UnknownOutcome).body)).toEqual(body);

    let lost = 0;
    vi.stubGlobal('fetch', async () => json(401, { error: { code: 'AUTHENTICATION_REQUIRED', detail: 'x' } }));
    api.onSessionLost = () => { lost += 1; };
    await expect(api.list()).rejects.toMatchObject({ code: 'AUTHENTICATION_REQUIRED', status: 401 });
    expect(lost).toBe(1);
  });

  it('mints a new operation id for every new Create, and sends the same bytes again only for a repeat of an unknown outcome (R7-REPLAY)', async () => {
    const form = { contextId: HEX('c'), releaseId: HEX('d'), listingId: UUID_A, name: 'n', asOf: '2026-01-05', quantity: '2', cash: '20', currency: 'USD' };
    const first = createBody(form, newOperationId());
    const second = createBody(form, newOperationId());
    expect(first.operation_id).not.toBe(second.operation_id);          // a second click on Create is a NEW command, not a replay
    const sent: string[] = [];
    vi.stubGlobal('fetch', async (path: string, init: RequestInit) => {
      if (path.endsWith('/auth/session')) return json(200, { schema_version: 'finweb.cp7/1', authenticated: false, user: null, csrf_token: HEX('e') });
      sent.push(String(init.body));
      return json(503, { schema_version: 'finweb.cp7.real_scoped_unknown/1', state: 'UNKNOWN', operation_id: UUID_B, retried: false, next: 'repeat' });
    });
    const api = new RealModeApi();
    await api.session();
    const failure = await api.create(first).catch((e: unknown) => e) as UnknownOutcome;
    await api.create(JSON.parse(failure.body)).catch(() => undefined);   // the repeat button resends the stored body
    expect(sent).toHaveLength(2);
    expect(sent[1]).toBe(sent[0]);
    expect(JSON.parse(sent[1]).operation_id).toBe(first.operation_id);
    // one click is one create: the Create button is disabled while a command is in flight
    const source = readFileSync(new URL('./RealModeApp.tsx', import.meta.url), 'utf8');
    expect(source).toContain('disabled={busy || !ack}');
    expect(source).not.toContain('newOperationId');                                    // HG4 revision: the one mint moved to the command module
    const commands = readFileSync(new URL('./real-mode-session.ts', import.meta.url), 'utf8');
    expect(commands.match(/newOperationId\(\)/g)).toHaveLength(1);
  });

  it('keeps the operation id and body of a create that got no readable answer (TR7-L-5)', async () => {
    const body = createBody({ contextId: HEX('c'), releaseId: HEX('d'), listingId: UUID_A, name: 'n', asOf: '2026-01-05', quantity: '2', cash: '20', currency: 'USD' }, UUID_B);
    const session = () => json(200, { schema_version: 'finweb.cp7/1', authenticated: false, user: null, csrf_token: HEX('e') });
    const answers: Record<string, () => Response | Promise<Response>> = {
      'no answer (fetch rejects)': () => { throw new TypeError('network'); },
      'a proxy page that is not JSON': () => new Response('<html>502</html>', { status: 502 }),
      'a 5xx JSON that is not a contract refusal': () => json(500, { detail: 'boom' }),
      'a 201 that fails the strict reader': () => json(201, { schema_version: 'finweb.cp7.real_scoped_create_result/1' }),
    };
    for (const [what, answer] of Object.entries(answers)) {
      vi.stubGlobal('fetch', async (path: string) => (path.endsWith('/auth/session') ? session() : answer()));
      const api = new RealModeApi();
      await api.session();
      const failure = await api.create(body).catch((e: unknown) => e);
      expect(failure, what).toBeInstanceOf(UnknownOutcome);
      expect((failure as UnknownOutcome).operationId, what).toBe(UUID_B);
      expect(JSON.parse((failure as UnknownOutcome).body), what).toEqual(body);
    }
    // A contract refusal (an error object with a code) is a definite refusal, not an unknown outcome.
    vi.stubGlobal('fetch', async (path: string) => (path.endsWith('/auth/session') ? session() : json(503, { error: { code: 'REAL_UNAVAILABLE', detail: 'x' } })));
    const api = new RealModeApi();
    await api.session();
    await expect(api.create(body)).rejects.toMatchObject({ code: 'REAL_UNAVAILABLE', status: 503 });
  });

  it('turns a response outside the contract into INVALID_RESPONSE and shows no part of it', async () => {
    vi.stubGlobal('fetch', async () => json(200, { schema_version: 'finweb.cp7.real_scoped_list/2', roots: [{ root_id: 'x' }] }));
    await expect(new RealModeApi().list()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    vi.stubGlobal('fetch', async () => { throw new Error('down'); });
    await expect(new RealModeApi().list()).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
    const t = translator('en', createTranslator());
    expect(refusalText(new ApiError('INVALID_RESPONSE', 'secret detail'), 'en', t)).toBe(common.en.invalidResponse);
    expect(refusalText(new ApiError('RW_WITHDRAWN', 'The context has been withdrawn', 409), 'zh-CN', t)).toContain(refusalZh.RW_WITHDRAWN);
    expect(refusalText(new ApiError('RW_WITHDRAWN', 'The context has been withdrawn', 409), 'en', t)).toContain('The context has been withdrawn');
  });

  it('refuses a malformed id before it can reach a path', async () => {
    vi.stubGlobal('fetch', async () => { throw new Error('must not be called'); });
    await expect(new RealModeApi().read('../../x', UUID_B)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});

/* ---- PD-0079: the key figures of a stored result ------------------------------------------------------------------------------------------ */

/** A stored metric in the shape of the engine's canonical dictionary (`ComputedMetric.to_canonical_dict`); every value here is a placeholder or an invented
 * number. A fixture in memory: never stored, never served. */
const metric = (id: string, view: string, extra: Record<string, unknown> = {}) => ({
  metric_id: id, view, subject: [['currency', 'USD']], value: '1.00', state: 'AVAILABLE', reason: null, unit: 'CURRENCY_AMOUNT', currency: 'USD', exact: '1/1', ...extra });
const NAV_TEXT = '1234567890123456789.123456789012345678';           // more digits than a float holds
const NEGATIVE = '-0.0000001234500';                                  // negative, many decimals, trailing zeros
const storedResult = () => ({
  manifest_id: 'm', result_digest: HEX('d'), metrics: [
    metric('cash_value', 'NATIVE', { value: '5.5' }),                // not a listed view: not listed
    metric('cash_value', 'REPORTING', { subject: [['account', 'A1'], ['currency', 'USD']], value: NEGATIVE }),
    metric('holding_value', 'REPORTING', { subject: [['account', 'A1'], ['listing', 'L2']], value: '0.10' }),
    metric('holding_value', 'REPORTING', { subject: [['account', 'A1'], ['listing', 'L1']], value: '9.90' }),     // stored order is kept, not sorted
    // F-3 (amended): under a NAV with a number a part shows its breakdown line, so this NAV carries one line per part, each the part's own stored text
    metric('portfolio_value', 'REPORTING', { value: NAV_TEXT, state: 'AVAILABLE',
      breakdown: [['cash:A1/USD', NEGATIVE, '1/1'], ['holding:A1/L2', '0.10', '1/1'], ['holding:A1/L1', '9.90', '1/1']] }),
    metric('portfolio_value_priced_holdings', 'REPORTING', { value: '77.77', partial: true }),
  ] });
const figuresHtml = (result: object, origin: Origin = REAL, locale: Locale = 'en') =>
  renderToStaticMarkup(createElement(KeyFigures, { result: result as never, origin, locale, t: translator(locale, createTranslator()) }));

describe('the key figures (PD-0079)', () => {
  it('shows each stored value byte for byte: many digits, a negative, trailing zeros, no formatting', () => {
    const out = figuresHtml(storedResult());
    for (const stored of [NAV_TEXT, NEGATIVE, '0.10', '9.90']) expect(out, stored).toContain('>' + stored + ' USD<');
    expect(out).not.toMatch(/1,234|1\.23e|0\.1<|9\.9<|-1\.2345e/i);                // no separators, no exponent, no trimmed zeros
    expect(out.indexOf('0.10')).toBeLessThan(out.indexOf('9.90'));                   // the stored order, not the order of the values
    expect(out.indexOf('data-figure-id="portfolio_value"')).toBeLessThan(out.indexOf('data-figure-id="holding_value"'));   // the fixed list's order
    expect(out).not.toContain('77.77');                                              // the partial figure is not listed (it could read as the NAV)
    expect(out).not.toContain('>5.5');                                               // the native view is not listed
  });

  it('shows no number on INSUFFICIENT_DATA even when the stored row has a value, and shows the state and the reason', () => {
    const result = { metrics: [metric('portfolio_value', 'REPORTING', { value: '999.99', state: 'INSUFFICIENT_DATA', reason: 'PRICE_MISSING' })] };
    for (const locale of LOCALES) {
      const out = figuresHtml(result, REAL, locale);
      expect(out).not.toContain('999.99');
      expect(out).not.toContain('figure-value');
      expect(out).toContain('>INSUFFICIENT_DATA<');
      expect(out).toContain('>PRICE_MISSING<');
      expect(out).toContain(common[locale].figureNoValue);
    }
    expect(keyFigures(result)[0].rows[0].value).toBeNull();
  });

  it('shows a state outside the three known ones with no number (no metric without a state)', () => {
    const out = figuresHtml({ metrics: [metric('portfolio_value', 'REPORTING', { value: '5', state: 'SOMETHING_ELSE' })] });
    expect(out).not.toContain('figure-value');
    expect(out).toContain('>SOMETHING_ELSE<');
    expect(out).toContain(common.en.figureUnreadable);
    expect(figuresHtml({ metrics: [{ metric_id: 'portfolio_value', view: 'REPORTING', value: '5' }] })).not.toContain('figure-value');      // no state at all
  });

  it('shows a LIMITED figure with its state, its reason and a marker beside the value', () => {
    for (const locale of LOCALES) {
      const out = figuresHtml({ metrics: [metric('portfolio_value', 'REPORTING', { value: '10.00', state: 'LIMITED', reason: 'STALE_PRICE' })] }, REAL, locale);
      expect(out).toMatch(/figure-value">10\.00 USD<\/span>[\s\S]*figure-state">LIMITED<\/code>[\s\S]*figure-limited[\s\S]*figure-reason">STALE_PRICE</);
      expect(out).toContain(common[locale].figureLimited);
      // an AVAILABLE figure carries no such marker
      expect(figuresHtml({ metrics: [metric('portfolio_value', 'REPORTING')] }, REAL, locale)).not.toContain('figure-limited');
    }
  });

  it('shows a listed figure that the result does not hold as absent, and drops none of the list', () => {
    for (const result of [{ metrics: [] }, {}, { metrics: 'nope' }, { metrics: [metric('portfolio_value', 'REPORTING')] }]) {
      const groups = keyFigures(result as never);
      expect(groups.map((g) => g.id)).toEqual(FIGURE_LIST.map((f) => f.id));
      const out = figuresHtml(result);
      expect(out.match(/data-figure-id=/g)).toHaveLength(FIGURE_LIST.length);
      // over a real source a result with no NAV row says so in a prominent notice (PD-0080), not in a plain absent line: three absent lines, one notice
      const navAbsent = groups[0].rows.length === 0;
      expect((out.match(/figure-absent/g) ?? []).length).toBe(groups.filter((g) => g.rows.length === 0).length - (navAbsent ? 1 : 0));
      expect(out.includes('figure-no-nav')).toBe(navAbsent);
    }
    expect(figuresHtml({ metrics: [] })).toContain(common.en.figureAbsent);
    expect(figuresHtml({ metrics: [] }, REAL, 'zh-CN')).toContain(common['zh-CN'].figureAbsent);
  });

  it('carries the invented-data marking over TEST data and no real-origin wording, and no marking over a real source', () => {
    for (const locale of LOCALES) {
      const test = figuresHtml(storedResult(), TEST, locale);
      expect(test).toContain('figures-mark">' + testOrigin[locale].mark + '<');
      expect(test).not.toContain('data-claim-id');
      expect(test.replace(testOrigin[locale].mark, '')).not.toMatch(/real[- ]source|真实来源/i);       // the mark itself negates a real source on purpose
      expect(figuresHtml(storedResult(), REAL, locale)).not.toContain('figures-mark');
    }
  });

  it('puts the figures below the claim limits, above the raw document, and labels the raw document in both languages, its content unchanged', () => {
    for (const [origin, labels, claims] of [[TEST, TEST_LABELS, testBlock()], [REAL, REAL_LABELS, block()]] as const) {
      const root = readRoot(createdFixture(origin, labels, claims, { result: storedResult() }), 'created');
      for (const locale of LOCALES) {
        const out = renderToStaticMarkup(createElement(RootDetail, { root, locale, depth: 'professional', t: translator(locale, createTranslator()) }));
        const claimsAt = out.indexOf('class="claim-limits'), figuresAt = out.indexOf('class="key-figures"'), noteAt = out.indexOf('class="raw-note"'), rawAt = out.indexOf('class="issued-result"');
        expect(claimsAt).toBeGreaterThan(-1);
        expect(claimsAt).toBeLessThan(figuresAt);
        expect(figuresAt).toBeLessThan(noteAt);
        expect(noteAt).toBeLessThan(rawAt);
        const esc = (text: string) => text.replace(/'/g, '&#x27;');
        const real = origin === REAL;
        // F-6: the notes differ by origin. A real origin reads `common`; any other origin reads `testOrigin`, which points at the mark, and says nothing of claim limits.
        expect(out).toContain('class="raw-note">' + esc(real ? common[locale].rawNote : testOrigin[locale].rawNote) + '<');
        expect(out).toContain('class="figures-note">' + esc(real ? common[locale].figuresNote : testOrigin[locale].figuresNote) + '<');
        if (!real) {
          const notes = (out.match(/class="(?:raw|figures)-note">[^<]*</g) ?? []).join(' ');
          expect(notes).not.toContain('claim limits');
          expect(notes).not.toContain('声明限制');
          expect(notes).toMatch(/invented test data|测试用虚构数据/);
        }
        expect(out).toMatch(/<details><summary>[^<]+<\/summary><pre class="issued-result">/);              // still collapsed
        const escaped = JSON.stringify(root.result, null, 2).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        expect(out).toContain('<pre class="issued-result">' + escaped + '</pre>');                           // the document, unchanged
      }
    }
    expect(common.en.rawNote).toMatch(/exactly as issued/);
    expect(common.en.rawNote).toMatch(/English/);
    expect(common.en.rawNote).toMatch(/not interpreted/);
    expect(common.en.rawNote).toMatch(/claim limits/);
    expect(common['zh-CN'].rawNote).toMatch(/原样签发/);
    expect(common['zh-CN'].rawNote).toMatch(/英文/);
    expect(common['zh-CN'].rawNote).toMatch(/未作解读/);
    expect(common['zh-CN'].rawNote).toMatch(/声明限制/);
  });

  it('renders a pure in-memory REAL_SOURCE fixture: the figures list and the 7.4 text, no invented marking (never stored, never served)', () => {
    const root = readRoot(createdFixture(REAL, REAL_LABELS, block(), { result: storedResult() }), 'created');
    const out = renderToStaticMarkup(createElement(RootDetail, { root, locale: 'en', depth: 'professional', t: translator('en', createTranslator()) }));
    expect(out).toContain('data-claim-id');
    expect(out).toContain('>' + NAV_TEXT + ' USD<');
    expect(out).not.toContain('figures-mark');
    expect(out).not.toContain('invented-data-mark');
  });
});

/* ---- the recorded stored document, and the Quant's rulings F-6, F-9, F-10 and the wording guards (PD-0079 ruling, 2026-11-09) -------------------------- */

/** A RECORD of the document a TEST create stores (the CP5 diversification result: `tests/product/test_postgres_real_mode_figures.py` compares this file with the
 * live document and fails when either moves). Its `metrics` are the stored rows without the per-run `manifest_id`; invented data. */
const RECORDED = JSON.parse(readFileSync(new URL('./real-mode-stored-result.fixture.json', import.meta.url), 'utf8')) as {
  metrics: Record<string, unknown>[]; buckets: unknown[]; top_keys: string[]; valuation_manifest_keys: string[];
};
const recordedResult = () => ({ metrics: structuredClone(RECORDED.metrics), manifest: { buckets: structuredClone(RECORDED.buckets) } });
/** A crafted variant of a recorded row: the same row, re-labelled as a listed figure, for the states a TEST create does not produce. */
const asListed = (row: Record<string, unknown>, extra: Record<string, unknown> = {}) => ({ ...structuredClone(row), metric_id: 'portfolio_value', view: 'REPORTING', ...extra });

describe('the recorded stored document (the shape the key figures are built against)', () => {
  it('is the diversification result: no listed metric id is in it, so every listed figure is absent over a TEST create', () => {
    expect(RECORDED.top_keys).toEqual(['clusters', 'exposure_decompositions', 'manifest', 'manifest_id', 'metrics', 'result_digest']);
    expect(RECORDED.metrics.length).toBeGreaterThan(10);
    for (const row of RECORDED.metrics) {
      expect(String(row.method_key).startsWith('diversification/1.2#')).toBe(true);
      expect('view' in row).toBe(false);                                    // the performance engine's `view`, `currency`, `unit` are not in this document
      expect('currency' in row).toBe(false);
    }
    expect(RECORDED.metrics.map((row) => row.metric_id)).not.toContain('portfolio_value');
    const groups = keyFigures(recordedResult() as never);
    expect(groups.map((g) => g.rows.length)).toEqual(FIGURE_LIST.map(() => 0));
    // PD-0080: over TEST data the four absent lines are REPLACED by one statement (four "not in this result" lines could be read as four zeros). It is chosen by the
    // origin and by the document holding none of the listed figures, never from `manifest.buckets[]` (whose money amounts are not a valuation).
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(recordedResult(), TEST, locale);
      expect(out).toContain('figures-none');
      expect(out).toContain(testOrigin[locale].figuresNone.replace(/'/g, '&#x27;'));
      expect(out).toContain('figures-mark');                                   // the invented-data mark still heads the list
      expect(out).not.toContain('figure-absent');
      expect(out).not.toContain('figure-value');
      expect(out).not.toContain('data-figure-id');
      expect(out).not.toContain('figure-no-nav');
    }
    // the buckets' exact rationals are never read: a result whose only money is in `manifest.buckets` still shows the statement and none of those amounts
    const buckets = JSON.stringify((recordedResult().manifest as { buckets: unknown }).buckets);
    expect(buckets.length).toBeGreaterThan(2);
    expect(figuresHtml(recordedResult(), TEST)).not.toMatch(/figure-value|\d+\/\d+/);
  });
});

describe('the Quant ruling on the key figures: F-9 and F-10, and the wording', () => {
  const stored = recordedResult().metrics;
  const insufficient = stored.find((row) => row.state === 'INSUFFICIENT_DATA' && Array.isArray(row.details) && row.details.length > 1)!;

  it('F-9: a row with no reason code shows the stored cause codes of `details`, uninterpreted and unselected', () => {
    expect(insufficient.reason).toBeNull();
    const out = figuresHtml({ metrics: [asListed(insufficient)] });
    expect(out).toContain(common.en.figureDetail);
    expect(out).toContain('figure-detail">INSUFFICIENT_OBSERVATIONS TOO_FEW_SECURITIES WINDOW_NOT_POSITIVE<');
    expect(out).not.toContain('figure-value');
    expect(figuresHtml({ metrics: [asListed(insufficient)] }, REAL, 'zh-CN')).toContain(common['zh-CN'].figureDetail);
    // a row with neither a reason nor details shows neither label
    expect(figuresHtml({ metrics: [asListed(insufficient, { details: [] })] })).not.toContain('figure-detail');
  });

  it('F-10: AVAILABLE or LIMITED with a null value, or with a numeric JSON value, shows "not readable" and no number; only INSUFFICIENT_DATA says "no number for this state"', () => {
    const available = stored.find((row) => row.state === 'AVAILABLE')!;
    const limited = stored.find((row) => row.state === 'LIMITED')!;
    for (const locale of LOCALES) {
      for (const [label, row] of [['AVAILABLE null', asListed(available, { value: null })], ['LIMITED null', asListed(limited, { value: null })],
        ['AVAILABLE number', asListed(available, { value: 0.5 })], ['LIMITED number', asListed(limited, { value: 12345.678 })],
        ['AVAILABLE missing', (() => { const r = asListed(available); delete (r as Record<string, unknown>).value; return r; })()]] as const) {
        const out = figuresHtml({ metrics: [row] }, REAL, locale);
        expect(out, label).toContain(common[locale].figureUnreadable);
        expect(out, label).not.toContain('figure-value');
        expect(out, label).not.toContain(common[locale].figureNoValue);
        expect(out, label).not.toContain('0.5<');
        expect(out, label).not.toContain('12345');
      }
      const suppressed = figuresHtml({ metrics: [asListed(insufficient)] }, REAL, locale);
      expect(suppressed).toContain(common[locale].figureNoValue);
      expect(suppressed).not.toContain(common[locale].figureUnreadable);
    }
    expect(keyFigures({ metrics: [asListed(available, { value: 0.5 })] } as never)[0].rows[0]).toMatchObject({ value: null, unreadable: true });
  });

  it('keeps the same keys in English and Chinese, in `common` and in `testOrigin`', () => {
    expect(Object.keys(common['zh-CN']).sort()).toEqual(Object.keys(common.en).sort());
    expect(Object.keys(testOrigin['zh-CN']).sort()).toEqual(Object.keys(testOrigin.en).sort());
    for (const key of ['figureStaleWeight', 'figureStaleNotStated', 'figureDetail', 'figurePartial', 'figurePartialNotNav', 'figureExcludedHoldings', 'figureExcludedComponents']) {
      expect(common.en[key as keyof typeof common.en], key).toBeTruthy();
      expect(common['zh-CN'][key as keyof typeof common.en], key).toBeTruthy();
    }
  });

  it('term guard (zh): no 净资产, and no 净值 that is not part of 资产净值; the zh labels are the ruled ones', () => {
    const zh = Object.values(common['zh-CN']).join('\n') + Object.values(testOrigin['zh-CN']).join('\n');
    expect(zh).not.toContain('净资产');
    expect(zh).not.toMatch(/(?<!资产)净值/);
    expect(zh).toContain('资产净值');
    expect(common['zh-CN'].figureCash).toContain('现金余额');
    expect(common['zh-CN'].figureHolding).toContain('持仓市值');
    expect(common['zh-CN'].figureReceivable).toContain('应收股息');
    expect(common.en.figureReceivable).toContain('Dividend receivable');
    expect(common['zh-CN'].figureLimited).not.toContain('并非完整数字');
    expect(common['zh-CN'].figureAbsent).toContain('并不表示数值为零');
    expect(common.en.figureAbsent).toContain('not a stated zero');
  });
});

/* ---- the ENGINE-MADE document (PD-0080) ---------------------------------------------------------------------------------------------------
 * `real-mode-engine-result.fixture.json` is what the performance engine produced for invented inputs, in memory (tests/product/real_figures_engine_fixture.py;
 * `test_real_figures_engine_fixture.py` regenerates it and fails on any difference). It keeps every listed row and the partial row VERBATIM; for the other rows
 * only the identity is kept. Four cases: AVAILABLE, LIMITED (stale), SUPPRESSED (no FX for CNH: no NAV number, a partial figure) and SUBCENT (the F-3 case).
 * Nothing below edits a row except where a test says it is a MUTANT of an engine row, to show the screen reads the field. */
type EngineRecord = { top_keys: string[]; metric_keys: string[]; index: unknown[][]; rows: Array<Record<string, any>> };
const ENGINE = JSON.parse(readFileSync(new URL('./real-mode-engine-result.fixture.json', import.meta.url), 'utf8')) as Record<string, EngineRecord>;
const engineResult = (name: string, edit?: (rows: Array<Record<string, any>>) => Array<Record<string, any>>) => {
  const rows = structuredClone(ENGINE[name].rows);
  return { metrics: edit ? edit(rows) : rows };
};
/** The REPORTING row of a metric (the engine's documents hold a NATIVE row first; the screen must skip it). */
const rowOf = (rows: Array<Record<string, any>>, id: string, view = 'REPORTING') => rows.find((row) => row.metric_id === id && row.view === view)!;
const partialPart = (html: string) => html.slice(html.indexOf('class="figure-partial"'));

describe('the key figures on the engine-made document (PD-0080, F-1, F-2, F-3)', () => {
  it('is a performance valuation document: its top keys, its row keys and the cases it holds', () => {
    expect(Object.keys(ENGINE).sort()).toEqual(['AVAILABLE', 'LIMITED', 'RECEIVABLE', 'SPLIT_UNRESOLVED', 'SUBCENT', 'SUPPRESSED']);
    for (const record of Object.values(ENGINE)) {
      expect(record.top_keys).toEqual(['manifest', 'manifest_id', 'metrics', 'result_digest']);
      expect(record.metric_keys).toEqual(expect.arrayContaining(['metric_id', 'view', 'subject', 'value', 'state', 'reason', 'currency', 'details', 'breakdown',
        'partial', 'stale_weight_presented', 'lineage']));
      expect(record.index.length).toBeGreaterThan(5);
    }
  });

  it('AVAILABLE: the NAV and its three parts as stored, no stale weight, no partial block, no no-NAV notice', () => {
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('AVAILABLE'), REAL, locale);
      for (const stored of ['9229.49', '5128.21', '101.28', '4000']) expect(out, stored).toContain('>' + stored + ' USD<');
      expect(out).not.toMatch(/figure-stale|figure-partial|figure-no-nav|figure-limited/);
      expect((out.match(/figure-absent/g) ?? []).length).toBe(1);                // only the receivable line: this document holds no receivable
    }
  });

  it('F-1: a LIMITED NAV shows the stored stale weight byte for byte, beside the marker, in both languages', () => {
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('LIMITED'), REAL, locale);
      expect(out).toContain('figure-stale-weight">0.555632726768<');
      expect(out).toContain(common[locale].figureStaleWeight.replace(/'/g, '&#x27;'));
      expect(out).toContain('9229.49 USD');
      expect(out.indexOf('figure-limited')).toBeLessThan(out.indexOf('figure-stale-weight'));
      expect(out).not.toContain('figure-stale-not-stated');
    }
  });

  it('F-1 mutant: the same engine row with the weight dropped shows "not stated" instead, and never a weight', () => {
    const mutant = engineResult('LIMITED', (rows) => { rowOf(rows, 'portfolio_value').stale_weight_presented = null; return rows; });
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(mutant, REAL, locale);
      expect(out).not.toContain('figure-stale-weight');
      expect(out).toContain('figure-stale-not-stated');
      expect(out).toContain(common[locale].figureStaleNotStated);
    }
    // an AVAILABLE NAV that stores no weight says nothing about one; a stale weight on any other row is shown wherever it is a string
    expect(figuresHtml(engineResult('AVAILABLE'), REAL)).not.toContain('figure-stale-not-stated');
    const other = engineResult('LIMITED', (rows) => { rowOf(rows, 'holding_value').stale_weight_presented = '0.25'; return rows; });
    expect(figuresHtml(other)).toContain('figure-stale-weight">0.25<');
  });

  it('F-3: the parts are the breakdown lines (1.01 and 1), not the separate rows (1 and 1)', () => {
    const rows = ENGINE.SUBCENT.rows;
    expect(rowOf(rows, 'holding_value').value).toBe('1');                         // the engine's own holding row says 1 ...
    expect(rowOf(rows, 'portfolio_value').breakdown[0][1]).toBe('1.01');          // ... its breakdown says 1.01 so that the parts add up to 2.01
    const groups = keyFigures(engineResult('SUBCENT') as never);
    expect(groups.map((g) => g.rows.map((r) => r.value))).toEqual([['2.01'], ['1.01'], ['1'], []]);
    const out = figuresHtml(engineResult('SUBCENT'));
    expect(out).toContain('>1.01 USD<');
    expect(out).toContain('>2.01 USD<');
    expect((out.match(/>1 USD</g) ?? []).length).toBe(1);                         // the cash part; the holding is not shown as 1
  });

  it('F-3 mutants: a changed breakdown changes the part; an empty breakdown under a total with a number gives no part a number; a part with no line shows no number', () => {
    const changed = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown[0][1] = '7.77'; return rows; }));
    expect(changed).toContain('>7.77 USD<');
    const none = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown = []; return rows; }));
    expect((none.match(/>1 USD</g) ?? []).length).toBe(0);                        // Quant case C: no part falls back to its own row
    expect(none.split(common.en.figureUnreadable).length - 1).toBe(2);
    expect(none).toContain('>2.01 USD<');
    expect(none).not.toContain('1.01');
    for (const locale of ['en', 'zh-CN'] as const) {
      const missing = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown.shift(); return rows; }), REAL, locale);
      expect(missing).toContain(common[locale].figureUnreadable);
      expect(missing).not.toContain('1.01');
      expect((missing.match(/>1 USD</g) ?? []).length).toBe(1);                   // the holding shows no number; only the cash part (a breakdown line) does
    }
  });

  it('F-2: a suppressed NAV shows no number, the stored cause, and the partial block after the four groups with both stored counts, in both languages', () => {
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('SUPPRESSED'), REAL, locale);
      const nav = out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'));
      expect(nav).toContain(common[locale].figureNoValue);
      expect(nav).toContain('figure-state">INSUFFICIENT_DATA<');
      expect(nav).toContain('figure-reason">MISSING_FX_HISTORY<');
      expect(nav).not.toContain('figure-value');
      expect(out).not.toContain('figure-no-nav');                                 // a suppressed NAV row is NOT a missing one: no notice
      expect(out.indexOf('class="figure-partial"')).toBeGreaterThan(out.indexOf('data-figure-id="receivable_value"'));
      const part = partialPart(out);
      expect(part).toContain(common[locale].figurePartial);
      expect(part).toContain('figure-value">4000 USD<');
      expect(part).toContain(common[locale].figurePartialNotNav);
      expect(part).toContain(common[locale].figureExcludedHoldings + ': <code>0</code>');   // a CNH cash balance is excluded with zero holdings excluded
      expect(part).toContain(common[locale].figureExcludedComponents + ': <code>1</code>');
      expect(out.match(/figure-partial"/g)).toHaveLength(1);
    }
  });

  it('F-2 mutants: the block shows only where the NAV has no number (a NAV number beside the partial figure never shows it), and only where the row is stored', () => {
    const withNumber = engineResult('SUPPRESSED', (rows) => { Object.assign(rowOf(rows, 'portfolio_value'), { state: 'AVAILABLE', reason: null, value: '4000' }); return rows; });
    expect(figuresHtml(withNumber)).not.toContain('figure-partial');
    const available = engineResult('AVAILABLE', (rows) => [...rows, structuredClone(rowOf(ENGINE.SUPPRESSED.rows, 'portfolio_value_priced_holdings'))]);
    expect(figuresHtml(available)).not.toContain('figure-partial');
    expect(figuresHtml(engineResult('SUPPRESSED', (rows) => rows.filter((row) => row.metric_id !== 'portfolio_value_priced_holdings'))).includes('figure-partial')).toBe(false);
    // the partial figure is never placed in the NAV row
    const out = figuresHtml(engineResult('SUPPRESSED'));
    expect(out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'))).not.toContain('4000');
    // a count the row does not store is not shown as a number
    const noCounts = figuresHtml(engineResult('SUPPRESSED', (rows) => { rowOf(rows, 'portfolio_value_priced_holdings').lineage = []; return rows; }));
    expect(partialPart(noCounts)).not.toMatch(/<code>\d+<\/code>/);
  });

  it('no NAV row at all over a real source is a prominent notice, apart from the plain absent line and from a suppressed NAV', () => {
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('AVAILABLE', (rows) => rows.filter((row) => row.metric_id !== 'portfolio_value')), REAL, locale);
      expect(out).toContain('figure-no-nav');
      expect(out).toContain(common[locale].figureNoNav);
      expect(common[locale].figureNoNav).not.toBe(common[locale].figureAbsent);
      // G-3: the notice sits INSIDE the NAV group (so the label never stands with nothing under it), and that group has no plain absent line
      const group = out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'));
      expect(group).toContain('figure-no-nav');
      expect(group).toContain(common[locale].figureNoNav);
      expect(group).not.toContain('figure-absent');
      expect(out.match(/figure-no-nav/g)).toHaveLength(1);
      expect(out.indexOf('data-figure-id="portfolio_value"')).toBeLessThan(out.indexOf('figure-no-nav'));
    }
    // over a TEST origin the notice is never shown for a missing NAV (the origin's own statement or list applies)
    expect(figuresHtml(engineResult('AVAILABLE', (rows) => rows.filter((row) => row.metric_id !== 'portfolio_value')), TEST)).not.toContain('figure-no-nav');
  });

  it('G-6: the receivable part comes from its breakdown line, built from the stored subject (accrued dividend, engine-made)', () => {
    const groups = keyFigures(engineResult('RECEIVABLE') as never);
    expect(groups.map((g) => g.rows.map((r) => r.value))).toEqual([['11228.21'], ['5128.21'], ['6000'], ['100']]);
    const nav = rowOf(ENGINE.RECEIVABLE.rows, 'portfolio_value');
    const receivable = rowOf(ENGINE.RECEIVABLE.rows, 'receivable_value');
    const event = (receivable.subject as string[][]).find((pair) => pair[0] === 'event')![1];     // read from the row, not hard-coded
    expect(nav.breakdown.map((line: string[]) => line[0])).toContain(`receivable:${(receivable.subject as string[][])[0][1]}/${event}`);
    // a mutant that changes the breakdown line's `shown` changes the part (and only that part); the row's own 100 is not what is shown
    const mutant = engineResult('RECEIVABLE', (rows) => { rowOf(rows, 'portfolio_value').breakdown[2][1] = '99.99'; return rows; });
    expect(keyFigures(mutant as never)[3].rows[0].value).toBe('99.99');
    expect(keyFigures(mutant as never)[2].rows[0].value).toBe('6000');
    // a mutant that points the line at another event leaves the part with no number
    const lost = engineResult('RECEIVABLE', (rows) => { rowOf(rows, 'portfolio_value').breakdown[2][0] = 'receivable:x/y'; return rows; });
    const part = keyFigures(lost as never)[3].rows[0];
    expect([part.value, part.unreadable]).toEqual([null, true]);
    expect(figuresHtml(engineResult('RECEIVABLE'))).toContain('>100 USD<');
  });

  it('TR7F-L-3: the fixture keeps the NATIVE rows (they come first in an engine document) and the screen skips them', () => {
    for (const name of ['AVAILABLE', 'LIMITED', 'RECEIVABLE', 'SUBCENT', 'SUPPRESSED']) {
      const rows = ENGINE[name].rows;
      for (const id of name === 'SUPPRESSED' ? ['portfolio_value', 'cash_value'] : ['portfolio_value', 'holding_value', 'cash_value']) {
        expect(rows.some((row) => row.metric_id === id && row.view === 'NATIVE'), `${name} ${id}`).toBe(true);
      }
      expect(rows.findIndex((row) => row.metric_id === 'portfolio_value')).toBeLessThan(rows.findIndex((row) => row.metric_id === 'portfolio_value' && row.view === 'REPORTING'));
    }
    expect(ENGINE.SUBCENT.rows.find((row) => row.metric_id === 'portfolio_value')!.view).toBe('NATIVE');   // the first NAV row is the NATIVE one, with an empty breakdown
    const out = figuresHtml(engineResult('SUBCENT'));
    expect(out).toContain('>1.01 USD<');                           // a lookup that read the NATIVE row would find no breakdown and show 1
    expect(figuresHtml(engineResult('SUPPRESSED'))).toContain('figure-partial"');
    expect(figuresHtml(engineResult('AVAILABLE'))).toContain('>9229.49 USD<');
  });

  it('TR7F-L-1: two NAV rows show "not readable" and no number, and no partial block', () => {
    const two = engineResult('SUPPRESSED', (rows) => {
      rows.push({ ...structuredClone(rowOf(rows, 'portfolio_value')), state: 'AVAILABLE', reason: null, value: '5' });
      return rows;
    });
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(two, REAL, locale);
      const nav = out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'));
      expect(nav).not.toContain('figure-value');
      expect((nav.match(new RegExp(common[locale].figureUnreadable, 'g')) ?? []).length).toBe(2);
      expect(out).not.toContain('figure-partial"');
    }
    const reversed = engineResult('SUPPRESSED', (rows) => {
      rows.unshift({ ...structuredClone(rowOf(rows, 'portfolio_value')), state: 'AVAILABLE', reason: null, value: '5' });
      return rows;
    });
    expect(figuresHtml(reversed)).not.toMatch(/figure-value">5 |figure-partial"/);
  });

  it('TR7F-L-1: a duplicate breakdown ref, or a malformed line anywhere in it, shows no part (not the first line, not the next good one)', () => {
    const ref = (ENGINE.SUBCENT.rows.find((row) => row.metric_id === 'portfolio_value' && row.view === 'REPORTING')!.breakdown[0] as string[])[0];
    const edits: Record<string, (b: unknown[][]) => void> = {
      'a duplicate ref': (b) => { b.splice(1, 0, [ref, '9.99', '1/1']); },
      'a numeric line first': (b) => { b.unshift([ref, 1.01, 'x']); },
      'an unrelated malformed line': (b) => { b.push(['junk']); },
      'a line whose shown is not decimal text': (b) => { b.push(['other', 'abc', '1/1']); },
    };
    for (const [label, edit] of Object.entries(edits)) {
      const out = figuresHtml(engineResult('SUBCENT', (rows) => { edit(rowOf(rows, 'portfolio_value').breakdown); return rows; }));
      expect(out, label).not.toMatch(/1\.01|9\.99|>1 USD</);
      expect(out, label).toContain('>2.01 USD<');                                // the NAV itself is unaffected
      expect(out.match(/figure-no-value/g) ?? [], label).toHaveLength(2);        // both parts: "not readable"
    }
  });

  it('TR7F-L-1: a value that is not decimal text (empty, NaN, abc) on AVAILABLE shows "not readable"; the partial block then shows if its row is stored', () => {
    for (const bad of ['', 'NaN', 'abc', ' 5', '5 ', '1,000']) {
      // a part's own value, with the total having no number (SUPPRESSED, where a part shows its own row): the USD cash row carries the bad text
      const cash = engineResult('SUPPRESSED', (rows) => {
        rows.find((row) => row.metric_id === 'cash_value' && row.view === 'REPORTING' && JSON.stringify(row.subject).includes('"USD"'))!.value = bad; return rows;
      });
      const out = figuresHtml(cash);
      const group = out.slice(out.indexOf('data-figure-id="cash_value"'), out.indexOf('data-figure-id="receivable_value"'));
      expect(group, JSON.stringify(bad)).not.toContain('figure-value');
      expect(group, JSON.stringify(bad)).toContain(common.en.figureUnreadable);
      expect(group, JSON.stringify(bad)).toContain(common.en.figureNoValue);     // the CNH row still shows "no value"
      const nav = engineResult('SUPPRESSED', (rows) => { Object.assign(rowOf(rows, 'portfolio_value'), { state: 'AVAILABLE', reason: null, value: bad }); return rows; });
      const shown = figuresHtml(nav);
      const navGroup = shown.slice(shown.indexOf('data-figure-id="portfolio_value"'), shown.indexOf('data-figure-id="holding_value"'));
      expect(navGroup, JSON.stringify(bad)).not.toContain('figure-value');
      expect(navGroup, JSON.stringify(bad)).toContain(common.en.figureUnreadable);
      expect(shown, JSON.stringify(bad)).toContain('figure-partial"');           // the NAV has no number to show, so the partial figure shows, with its counts
    }
  });

  it('H-1 and TR7F-L-1: the stale weight shows only on a LIMITED row that shows a number', () => {
    const withWeight = (name: string, id: string, patch: Record<string, unknown>) => engineResult(name, (rows) => {
      Object.assign(rowOf(rows, id), { stale_weight_presented: '0.55', ...patch }); return rows;
    });
    // suppressed (INSUFFICIENT_DATA), unknown state, AVAILABLE: no weight, and none of its digits
    for (const [name, patch] of [['SUPPRESSED', {}], ['SUPPRESSED', { state: 'WEIRD' }], ['AVAILABLE', {}]] as const) {
      const out = figuresHtml(withWeight(name, 'portfolio_value', patch as Record<string, unknown>));
      expect(out, name + JSON.stringify(patch)).not.toMatch(/figure-stale|0\.55/);
    }
    // a numeric weight, or text that is not decimal, on a LIMITED NAV: "not readable" in the weight's place, never "not stated"
    for (const bad of [0.5, 'abc', '']) {
      const out = figuresHtml(withWeight('LIMITED', 'portfolio_value', { stale_weight_presented: bad }));
      expect(out, String(bad)).toContain('figure-stale"');
      expect(out, String(bad)).not.toContain('figure-stale-not-stated');
      expect(out, String(bad)).not.toContain('figure-stale-weight');
    }
    // a LIMITED row with an unreadable value shows no weight either
    expect(figuresHtml(withWeight('LIMITED', 'portfolio_value', { value: '' }))).not.toMatch(/figure-stale/);
  });

  it('H-2: the two counts show only beside a number; a split-unresolved partial row (INSUFFICIENT_DATA, counts 0 and 0, engine-made) shows none', () => {
    const rows = ENGINE.SPLIT_UNRESOLVED.rows;
    const partial = rowOf(rows, 'portfolio_value_priced_holdings');
    expect([partial.state, partial.reason, partial.value]).toEqual(['INSUFFICIENT_DATA', 'UNRESOLVED_CONVENTION', null]);
    expect(partial.lineage).toEqual([['excluded_components', '0'], ['excluded_holdings', '0'], ['included_components', '0']]);
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('SPLIT_UNRESOLVED'), REAL, locale);
      expect(out).toContain('figure-partial"');                                 // the block shows: its state and reason are the stored answer
      expect(out).toContain('UNRESOLVED_CONVENTION');
      expect(out).toContain(common[locale].figurePartialNotNav);
      expect(out).not.toContain('figure-partial-count');
      expect(out).not.toContain(common[locale].figureExcludedHoldings);
      const nav = out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'));
      expect(nav).not.toContain('figure-value');
    }
    // beside a number the counts stay (the suppressed document: 1 and 0 beside 4000)
    expect(figuresHtml(engineResult('SUPPRESSED'))).toContain('figure-partial-count');
    // an unreadable partial row also shows no count
    const unreadable = engineResult('SUPPRESSED', (r) => { rowOf(r, 'portfolio_value_priced_holdings').value = 'abc'; return r; });
    expect(figuresHtml(unreadable)).not.toContain('figure-partial-count');
  });

  it('TR7F-L-2: every path that copies a value shows the stored text byte for byte, for text a conversion would change', () => {
    const UNSAFE = ['0.10', '1.00', '1000.000', '-0.0000001234500', '1234567890123456789012345678901234567890', '12345678901234567.89',
      '1234567890123456789012345678901234567890.123456789012345678901234567890'];
    for (const u of UNSAFE) {
      // the NAV's own value, breakdown intact
      const own = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').value = u; return rows; }));
      expect(own.split('>' + u + ' USD<').length - 1, `own ${u}`).toBe(1);
      // a part's own value, where the total has no number (SUPPRESSED)
      const ownPart = figuresHtml(engineResult('SUPPRESSED', (rows) => {
        rows.find((row) => row.metric_id === 'cash_value' && row.view === 'REPORTING' && JSON.stringify(row.subject).includes('"USD"'))!.value = u; return rows;
      }));
      expect(ownPart.split('>' + u + ' USD<').length - 1, `own part ${u}`).toBe(1);
      // a breakdown part
      const part = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown[0][1] = u; return rows; }));
      expect(part, `part ${u}`).toContain('>' + u + ' USD<');
      // a stale weight
      const weight = figuresHtml(engineResult('LIMITED', (rows) => { rowOf(rows, 'portfolio_value').stale_weight_presented = u; return rows; }));
      expect(weight, `weight ${u}`).toContain('figure-stale-weight">' + u + '<');
    }
    // a lineage count (digits only)
    for (const c of ['007', '0', '1234567890123456789012345678901234567890', '00000000000000000001']) {
      const out = figuresHtml(engineResult('SUPPRESSED', (rows) => {
        const row = rowOf(rows, 'portfolio_value_priced_holdings');
        row.lineage = [['excluded_components', c], ['excluded_holdings', c], ['included_components', '1']]; return rows;
      }));
      expect(out.split('<code>' + c + '</code>').length - 1, `count ${c}`).toBe(2);
    }
    // a count that is not digits is not shown as one
    const bad = figuresHtml(engineResult('SUPPRESSED', (rows) => { rowOf(rows, 'portfolio_value_priced_holdings').lineage = [['excluded_components', '1e3'], ['excluded_holdings', '1'], ['excluded_holdings', '2']]; return rows; }));
    expect(bad).not.toMatch(/<code>(1e3|1|2)<\/code>/);
  });

  it('TR7F2-L-1: an exponent is not a stored figure (the engine writes plain digits): unreadable on every value path', () => {
    for (const bad of ['1e3', '1E3', '1e+3', '2.5e-3']) {
      const own = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').value = bad; rowOf(rows, 'portfolio_value').breakdown = []; rowOf(rows, 'holding_value').value = bad; return rows; }));
      expect(own, bad).not.toContain(bad);
      expect(own, bad).not.toContain('figure-value">' + bad);
      expect(own.split(common.en.figureUnreadable).length - 1, bad).toBe(2);                    // the NAV and the holding
      const part = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown[0][1] = bad; return rows; }));
      expect(part, bad).not.toContain(bad);
      expect(part, bad).not.toMatch(/1\.01|>1 USD</);                                            // an invalid breakdown gives no part a number
      const weight = figuresHtml(engineResult('LIMITED', (rows) => { rowOf(rows, 'portfolio_value').stale_weight_presented = bad; return rows; }));
      expect(weight, bad).not.toContain(bad);
      expect(weight, bad).toContain('figure-stale"');
      expect(weight, bad).not.toContain('figure-stale-weight');
      const count = figuresHtml(engineResult('SUPPRESSED', (rows) => { rowOf(rows, 'portfolio_value_priced_holdings').lineage = [['excluded_components', bad], ['excluded_holdings', bad]]; return rows; }));
      expect(count, bad).not.toContain(bad);
      const partial = figuresHtml(engineResult('SUPPRESSED', (rows) => { rowOf(rows, 'portfolio_value_priced_holdings').value = bad; return rows; }));
      expect(partial, bad).not.toContain(bad);
      expect(partial, bad).not.toContain('figure-partial-count');
    }
  });

  it('TR7F2-L-1: two partial rows show "not readable", no number and no count', () => {
    const two = engineResult('SUPPRESSED', (rows) => { rows.push({ ...structuredClone(rowOf(rows, 'portfolio_value_priced_holdings')), value: '9.99' }); return rows; });
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(two, REAL, locale);
      expect(out).toContain('figure-partial"');
      const part = partialPart(out);
      expect(part).not.toContain('figure-value');
      expect(part).not.toMatch(/4000|9\.99/);
      expect(part).toContain(common[locale].figureUnreadable);
      expect(part).not.toContain('figure-partial-count');
    }
  });

  it('TR7F2-L-1: a breakdown that is not an array gives no part a number; the parts do not fall back to their own rows', () => {
    for (const broken of [null, 'abc', 5, { a: 1 }, true]) {
      const out = figuresHtml(engineResult('SUBCENT', (rows) => { rowOf(rows, 'portfolio_value').breakdown = broken; return rows; }));
      expect(out, JSON.stringify(broken)).toContain('>2.01 USD<');               // the NAV itself still shows
      expect(out, JSON.stringify(broken)).not.toMatch(/>1(\.01)? USD</);         // no part shows 1 (its own row) or 1.01
      expect(out.split(common.en.figureUnreadable).length - 1, JSON.stringify(broken)).toBe(2);
    }
    // an empty array (case C), or no breakdown key at all (case B), under a total with a number gives no part a number
    for (const locale of ['en', 'zh-CN'] as const) {
      for (const edit of [(b: Record<string, any>) => { b.breakdown = []; }, (b: Record<string, any>) => { delete b.breakdown; }]) {
        const result = engineResult('SUBCENT', (rows) => { edit(rowOf(rows, 'portfolio_value')); return rows; });
        const out = figuresHtml(result, REAL, locale);
        expect(out).toContain('>2.01 USD<');
        expect(out).not.toContain('1.01');
        expect((out.match(/>1 USD</g) ?? []).length).toBe(0);
        expect(out.split(common[locale].figureUnreadable).length - 1).toBe(2);
        expect(out).toContain(common[locale].figureAbsent);
        expect(out).toContain('class="figures-note"');                               // the note is shown, its text unchanged
        expect(keyFigures(result as never).map((g) => g.rows.map((r) => r.value))).toEqual([['2.01'], [null], [null], []]);
        expect(keyFigures(result as never).map((g) => g.rows.map((r) => r.unreadable))).toEqual([[false], [true], [true], []]);
        expect(navStatus(result as never)).toBe('NUMBER');
        expect(partialBlock(result as never)).toBeNull();
      }
    }
    // case E: the suppressed shape (no NAV number, empty breakdown); deleting the breakdown changes nothing, the USD cash part still shows 4000
    for (const edit of [(b: Record<string, any>) => b, (b: Record<string, any>) => { delete b.breakdown; return b; }]) {
      const out = figuresHtml(engineResult('SUPPRESSED', (rows) => { edit(rowOf(rows, 'portfolio_value')); return rows; }));
      expect(out).toContain('>4000 USD<');
      expect(out).toContain(common.en.figureNoValue);
    }
  });

  it('TR8C-L-1 (a): under a total with a number, a part with no number of its own shows as its own row says, never its breakdown line (addendum 2026-11-14 section 1)', () => {
    const holdingGroup = (out: string) => out.slice(out.indexOf('data-figure-id="holding_value"'), out.indexOf('data-figure-id="cash_value"'));
    // INSUFFICIENT_DATA with no value, breakdown line 1.01 intact: "no value", not "not readable", and no 1.01
    for (const locale of ['en', 'zh-CN'] as const) {
      const out = figuresHtml(engineResult('SUBCENT', (rows) => { Object.assign(rowOf(rows, 'holding_value'), { state: 'INSUFFICIENT_DATA', reason: 'MISSING_PRICE_HISTORY', value: null }); return rows; }), REAL, locale);
      const group = holdingGroup(out);
      expect(group).toContain(common[locale].figureNoValue);
      expect(group).not.toContain(common[locale].figureUnreadable);
      expect(group).not.toContain('figure-value');
      expect(group).not.toContain('1.01');
      expect(out).toContain('>2.01 USD<');
      expect(out).toContain('>1 USD<');                                          // the cash part is still its breakdown line
    }
    // an unknown state, and a value that is not decimal text: the row's own display (not readable), and no 1.01
    for (const patch of [{ state: 'WEIRD' }, { value: 'abc' }, { value: '' }]) {
      const group = holdingGroup(figuresHtml(engineResult('SUBCENT', (rows) => { Object.assign(rowOf(rows, 'holding_value'), patch); return rows; })));
      expect(group, JSON.stringify(patch)).toContain(common.en.figureUnreadable);
      expect(group, JSON.stringify(patch)).not.toContain('figure-value');
      expect(group, JSON.stringify(patch)).not.toContain('1.01');
    }
  });

  it('TR8C-L-1 (b): more than one NAV row means the total has no number, so each part shows its own stored value', () => {
    const cashRef = 'cash:00000000-0000-0000-0000-000000000001/USD';
    for (const breakdown of [[], [[cashRef, '7.77', '1/1']]]) {
      const out = figuresHtml(engineResult('SUPPRESSED', (rows) => {
        rows.unshift({ ...structuredClone(rowOf(rows, 'portfolio_value')), state: 'AVAILABLE', reason: null, value: '5', breakdown });
        return rows;
      }));
      const nav = out.slice(out.indexOf('data-figure-id="portfolio_value"'), out.indexOf('data-figure-id="holding_value"'));
      expect(nav).not.toContain('figure-value');                                 // both NAV rows are "not readable"
      expect(out).toContain('>4000 USD<');                                       // the USD cash part shows its own value
      expect(out).not.toContain('7.77');
    }
  });

  it('the engine-made document is a real-source document: over a TEST origin the list is replaced by the statement only when none of the listed figures is held', () => {
    expect(figuresHtml(engineResult('AVAILABLE'), TEST)).toContain('data-figure-id');
    expect(figuresHtml(engineResult('AVAILABLE'), TEST)).not.toContain('figures-none');
    expect(figuresHtml({ metrics: [] }, TEST)).toContain('figures-none');
  });

  it('the new strings exist in both languages and the Chinese ones respect the term guard', () => {
    for (const text of [common.en.figureNoNav, common['zh-CN'].figureNoNav, testOrigin.en.figuresNone, testOrigin['zh-CN'].figuresNone]) expect(text.length).toBeGreaterThan(20);
    expect(`${common['zh-CN'].figureNoNav}${testOrigin['zh-CN'].figuresNone}`).not.toMatch(/净资产|(?<!资产)净值/);
    expect(testOrigin.en.figuresNone).not.toMatch(/claim limits/i);
    expect(testOrigin['zh-CN'].figuresNone).not.toContain('声明限制');
  });
});

describe('the client does no arithmetic on a stored value (PD-0079, P1)', () => {
  const between = (file: string, from: string, to: string) => {
    const source = readFileSync(new URL(`./${file}`, import.meta.url), 'utf8');
    return source.slice(source.indexOf(from), source.indexOf(to));
  };
  /** The figure code: the selection in real-mode.ts and the component in RealModeApp.tsx, comments removed. */
  const figureCode = () => [between('real-mode.ts', 'export const FIGURE_LIST', 'export interface CreateForm'),
    between('RealModeApp.tsx', 'export function KeyFigures', 'export function RootEntries')]
    .map((code) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')).join('\n');
  /** What would compute, convert, format or reorder a value. */
  const FORBIDDEN: [string, RegExp][] = [
    ['Number()', /\bNumber\s*\(/], ['parseFloat/parseInt', /\bparse(Float|Int)\s*\(/], ['unary plus on a value', /[=(,:?]\s*\+\s*[A-Za-z_]/], ['toFixed/toPrecision', /\.to(Fixed|Precision|Exponential)\s*\(/],
    ['toLocaleString/Intl', /toLocale\w*\s*\(|\bIntl\b/], ['Math.', /\bMath\./], ['BigInt/Decimal', /\bBigInt\b|\bDecimal\b|\bbig\.js\b/], ['sort/reduce', /\.(sort|toSorted|reduce|reduceRight)\s*\(/],
    ['arithmetic operator', /[A-Za-z_\)\]]\s+[-*/%]\s+[A-Za-z_\(\d]|\*\*|\+\+|--/], ['string-to-number coercion', /\*\s*1\b|-\s*0\b|~~/],
    ['replace/slice of a value', /value\s*\.\s*(replace|slice|substring|padEnd|padStart|trim)\s*\(/],
  ];
  const violations = (code: string) => FORBIDDEN.filter(([, pattern]) => pattern.test(code)).map(([name]) => name);

  it('has none of them in the figure selection or the figure component', () => {
    expect(violations(figureCode())).toEqual([]);
  });

  it('the scan bites: each kind of computation, formatting or reordering added to the code is found', () => {
    const code = figureCode();
    const mutants: Record<string, string> = {
      'Number()': code.replace('const stored = decimalText(metric.value);', 'const stored = String(Number(decimalText(metric.value)));'),
      'toFixed': code.replace('{row.value}', '{Number(row.value).toFixed(2)}'),
      'toLocaleString': code.replace('{row.value}', '{row.value.toLocaleString()}'),
      'Intl': code.replace('{row.value}', '{new Intl.NumberFormat().format(row.value)}'),
      'parseFloat': code.replace('{row.value}', '{parseFloat(row.value)}'),
      'a sort of the rows': code.replace('&& metric.view === entry.view)', '&& metric.view === entry.view).sort((a, b) => 0)'),
      'a sum': code.replace('{row.value}', '{rows.reduce((s, r) => s + r, 0)}'),
      'a subtraction': code.replace('{row.value}', '{row.value - row.other}'),
      'a trim of the value': code.replace('{row.value}', '{row.value.trim()}'),
    };
    for (const [label, mutated] of Object.entries(mutants)) {
      expect(mutated, label).not.toBe(code);
      expect(violations(mutated).length, label).toBeGreaterThan(0);
    }
  });

  it('passes a value that a float could not hold through unchanged (a behavioural control)', () => {
    const row = keyFigures({ metrics: [metric('portfolio_value', 'REPORTING', { value: NAV_TEXT })] })[0].rows[0];
    expect(row.value).toBe(NAV_TEXT);
    expect(Number(NAV_TEXT).toString()).not.toBe(NAV_TEXT);                    // a number conversion WOULD have changed it
  });
});
