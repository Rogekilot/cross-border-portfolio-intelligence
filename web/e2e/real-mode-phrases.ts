// Phrases that must never render over TEST data (F1 R7). Shared by the Playwright spec and by a vitest (src/real-mode.test.ts) that fails if any phrase occurs
// in a client string that is not claim text, so the list cannot drift into colliding with a permanent string (such as the create form's acknowledgement).
// Only the real origin labels and wording unique to the 7.4 claim templates belong here. Bare status tokens (UNVERIFIABLE, SINGLE_SOURCE) do not: the stored
// engine JSON carries them. "constructed by the project for testing" does not either: the create form's acknowledgement says it on every screen.
export const REAL_SENTENCES: string[] = [
  'Market data from a real source', 'REAL_SOURCE_CONSTRUCTED_ACCOUNT',
  'official closing-cross price', 'compared with any other source', 'split label is verified', 'dividend component is verified', 'split history is complete',
  'zero records at', 'ledger fact the project entered', 'not a verification', 'as the owner read it',
  '市场数据来自真实来源', '收盘集合竞价价格', '拆股调整标签', '股息调整部分', '拆股历史', '零条记录', '账本事实', '并非核实', '所有者的持仓',
];
