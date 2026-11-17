import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const origin = 'http://127.0.0.1:5174';
const sha = (raw: string) => createHash('sha256').update(raw, 'utf8').digest('hex');
/** Read genuine upstream APIResponse bytes, then fulfill the browser with those exact bytes; no CDP body lookup. */
async function observeJson(page: Page, pathname: string, method: 'GET' | 'POST' = 'POST') {
  let resolve!: (value: { status: number; requestBody: any; body: any }) => void;
  let reject!: (reason: unknown) => void;
  const result = new Promise<{ status: number; requestBody: any; body: any }>((done, failed) => { resolve = done; reject = failed; });
  await page.route(`${origin}${pathname}`, async (route) => {
    try {
      expect(route.request().method()).toBe(method);
      const requestBody = method === 'POST' ? route.request().postDataJSON() : null;
      const actual = await route.fetch({ maxRedirects: 0, maxRetries: 0, timeout: 15_000 });
      const bytes = await actual.body(); const status = actual.status(); const body = JSON.parse(bytes.toString('utf8'));
      await route.fulfill({ response: actual, body: bytes });
      resolve({ status, requestBody, body });
    } catch (failure) { reject(failure); await route.abort('failed').catch(() => undefined); }
  }, { times: 1 });
  return { result };
}
async function confine(context: BrowserContext) {
  await context.route('**/*', async (route) => {
    const target = new URL(route.request().url());
    if (target.origin === origin || target.origin === 'http://127.0.0.1:8003') await route.continue();
    else await route.abort('blockedbyclient');
  });
}
async function register(page: Page, suffix: string, reuseDisposableUsername?: string) {
  const marker = reuseDisposableUsername ? reuseDisposableUsername.slice('f3_ui_owner_'.length) : Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const username = reuseDisposableUsername ?? `f3_ui_${suffix}_${marker}`.slice(0, 32); const password = `f3-disposable-only-${marker}`;
  await page.goto(origin);
  const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click();
  if (!reuseDisposableUsername) await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(username); await account.getByLabel('Password', { exact: true }).fill(password);
  await account.locator('form').getByRole('button', { name: reuseDisposableUsername ? 'Sign in' : 'Create local account', exact: true }).click();
  await expect(account).toContainText(`Signed in as ${username}`); return account;
}

// Every run registers newly invented disposable accounts in the disposable F3 database that `tests/product/dev_env.py up`
// created; nothing here depends on an account left by an earlier run. No real credentials.
test('guarded fictional date → actual ledger and CSV → lost response reconciliation → exact archive/reproduce/export → isolation and bilingual keyboard', async ({ page, browser }) => {
  test.setTimeout(180_000); await confine(page.context()); await register(page, 'owner');
  const name = 'F3 fictional trial A3';
  await page.getByLabel('Portfolio name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Use example quantities', exact: true }).click();
  await page.getByLabel('Opening facts date', { exact: true }).fill('2026-01-01');
  await page.getByRole('checkbox', { name: /I understand these are synthetic/ }).check();
  const created = await observeJson(page, '/api/v1/portfolios');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click();
  const createResponse = await created.result; expect(createResponse.status).toBe(200); const initial = createResponse.body;
  expect(initial.disposition).toBe('COMMITTED'); expect(sha(initial.response_json)).toBe(initial.response_sha256);
  expect(createResponse.requestBody.opening_date).toBe('2026-01-01');
  expect(createResponse.requestBody.operation_id).toBe(initial.operation_id);
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await expect(page.getByText('This historical analytical feature is unavailable in the guarded fictional profile. No legacy financial route is used.', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const root = initial.portfolio_id; const base = `/api/v1/portfolios/${root}`;
  const initialWorkspace = await (await page.request.get(`${origin}${base}/workspace`)).json();
  await page.locator('#ledger-event-0-event_type').selectOption('DEPOSIT');
  await page.locator('#ledger-event-0-account_id').selectOption(initialWorkspace.accounts[0].account_id);
  await page.locator('#ledger-event-0-event_date').fill('2026-01-02'); await page.locator('#ledger-event-0-currency').fill('USD');
  await page.locator('#ledger-event-0-amount').fill('7');
  const previewed = await observeJson(page, `${base}/ledger-commands/preview`);
  await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click();
  const preview = (await previewed.result).body; expect(preview.preview).toBe(true); expect(preview.snapshot.persisted).toBe(false);
  const afterPreview = await (await page.request.get(`${origin}${base}/workspace`)).json();
  expect(afterPreview.revision_id).toBe(initialWorkspace.revision_id); expect(afterPreview.ledger.events).toEqual(initialWorkspace.ledger.events);
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check();
  let committed!: Record<string, any>; let command: unknown; let delivered!: () => void;
  const reachedServer = new Promise<void>((resolve) => { delivered = resolve; });
  await page.route(`${origin}${base}/ledger-commands`, async (route) => {
    command = route.request().postDataJSON(); const actual = await route.fetch(); expect(actual.status()).toBe(200);
    committed = await actual.json(); await route.abort('failed'); delivered();
  }, { times: 1 });
  await page.getByRole('button', { name: 'Confirm & append saved revision', exact: true }).click(); await reachedServer;
  await expect(page.locator('.guarded-pending')).toContainText('Outcome not confirmed');
  await expect(page.locator('.guarded-pending')).toContainText(committed.operation_id);
  await expect(page.locator('.revision-strip').first()).toContainText(initialWorkspace.revision_id);
  const reconciled = await observeJson(page, `${base}/operations/${committed.operation_id}/reconcile`, 'GET');
  await page.getByRole('button', { name: 'Check this operation', exact: true }).click();
  const confirmation = await reconciled.result; expect(confirmation.status).toBe(200);
  expect(confirmation.body.response_sha256).toBe(committed.response_sha256);
  await expect(page.locator('.guarded-pending')).toHaveCount(0);
  await expect(page.locator('.revision-strip').first()).toContainText(committed.revision_id);
  const session = await (await page.request.get(`${origin}/api/v1/auth/session`)).json();
  const replay = await page.request.post(`${origin}${base}/ledger-commands`, { headers: { Origin: origin, 'X-Finweb-CSRF': session.csrf_token }, data: command });
  expect(replay.status()).toBe(200); const replayed = await replay.json();
  expect(replayed.response_sha256).toBe(committed.response_sha256); expect(replayed.issued_sha256).toBe(committed.issued_sha256);

  const workspace = await (await page.request.get(`${origin}${base}/workspace`)).json();
  const csv = `key,account,type,date,currency,amount\nf3-cash-1,${workspace.accounts[0].account_id},DEPOSIT,2026-01-02,USD,3\n`;
  await page.locator('#csv-kind').selectOption('TRANSACTIONS'); await page.locator('#csv-delimiter').selectOption(',');
  await page.locator('#csv-ack').check(); await page.locator('#csv-file').setInputFiles({ name: 'f3-fictional.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  const parsed = await observeJson(page, `${base}/imports/parse`);
  await page.getByRole('button', { name: 'Parse selected bytes', exact: true }).click(); expect((await parsed.result).status).toBe(200);
  await page.locator('#csv-date-format').selectOption('ISO'); await page.locator('#csv-decimal').selectOption('.'); await page.locator('#csv-thousands').selectOption('NONE');
  await page.locator('#csv-namespace').fill(`f3-ui-${initial.operation_id}`);
  for (const [field, column] of [['source_row_key', '0'], ['account_id', '1'], ['event_type', '2'], ['event_date', '3'], ['currency', '4'], ['amount', '5']]) await page.locator(`#csv-map-${field}`).selectOption(column);
  const csvPreviewed = await observeJson(page, `${base}/imports/preview`);
  await page.getByRole('button', { name: 'Validate complete batch & obtain server preview', exact: true }).click(); expect((await csvPreviewed.result).status).toBe(200);
  await page.locator('#csv-confirm').check(); const imported = await observeJson(page, `${base}/imports/commit`);
  await page.getByRole('button', { name: 'Confirm atomic financial import & report', exact: true }).click();
  const csvResponse = await imported.result; expect(csvResponse.status).toBe(200); const csvEnvelope = csvResponse.body;
  const csvResult = JSON.parse(csvEnvelope.response_json); expect(csvResult.report.status).toBe('COMMITTED');
  expect(sha(csvEnvelope.response_json)).toBe(csvEnvelope.response_sha256);
  await expect(page.locator('.revision-strip').first()).toContainText(csvEnvelope.revision_id);
  const archivePanel = page.getByRole('region', { name: 'Archived CP5 answer', exact: true });
  await archivePanel.getByRole('button', { name: 'Read archived answer', exact: true }).click();
  await expect(archivePanel.locator('.guarded-archive-result')).toContainText(csvEnvelope.issued_sha256);
  const reproduced = await observeJson(page, `${base}/operations/${csvEnvelope.operation_id}/reproduce`);
  await archivePanel.getByRole('button', { name: 'Reproduce archived CP5 answer', exact: true }).click();
  const reproduction = (await reproduced.result).body; expect(reproduction.status).toBe('REPRODUCED'); expect(reproduction.issued_sha256).toBe(csvEnvelope.issued_sha256);
  await expect(archivePanel.locator('.reproduction-result')).toContainText('The complete archived CP5 answer was reproduced.');
  const downloading = page.waitForEvent('download'); await archivePanel.getByRole('button', { name: 'Download exact archive · JSON', exact: true }).click();
  const download = await downloading; const bytes = await readFile((await download.path())!); const exported = JSON.parse(bytes.toString('utf8'));
  expect(exported.operation_id).toBe(csvEnvelope.operation_id); expect(sha(exported.issued_json)).toBe(exported.issued_sha256);
  await test.info().attach('f3-fictional-archive.json', { body: bytes, contentType: 'application/json' });
  await page.reload(); await page.getByRole('button', { name: `Open ${name}`, exact: true }).click();
  await expect(page.locator('.revision-strip').first()).toContainText(csvEnvelope.revision_id);

  const otherContext = await browser.newContext({ baseURL: origin, viewport: { width: 390, height: 844 } });
  await confine(otherContext); const otherPage = await otherContext.newPage();
  try {
    await register(otherPage, 'other');
    const foreign = await otherPage.request.get(`${origin}${base}/operations/${csvEnvelope.operation_id}`);
    expect(foreign.status()).toBe(404); const missing = await otherPage.request.get(`${origin}/api/v1/portfolios/55555555-5555-4555-8555-555555555555/operations/66666666-6666-4666-8666-666666666666`);
    expect(missing.status()).toBe(404); expect(await foreign.json()).toEqual(await missing.json());
  } finally { await otherContext.close(); }
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  const chineseArchive = page.getByRole('region', { name: '已归档 CP5 结果', exact: true });
  await chineseArchive.getByRole('button', { name: '读取归档结果', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(chineseArchive.locator('.guarded-archive-result')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await test.info().attach('f3-zh-390.png', { body: await page.screenshot(), contentType: 'image/png' });
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await expect(page.locator('.guarded-archive')).toHaveCount(0); await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
});

// ---- Repeat CSV import: the saved "nothing new" report (review finding M-1, PD-0062 §1) ----------------------------------
type Lang = 'en' | 'zh';
/** UI strings (web/src/csv-i18n.ts, guarded-i18n.ts). Server-derived values below are always read from the real response. */
const ui = {
  en: { parse: 'Parse selected bytes', validate: 'Validate complete batch & obtain server preview', financial: 'Confirm atomic financial import & report',
    reportOnly: 'Confirm zero-import report only', saved: 'Saved import report', noop: 'Source facts already recorded · explicit no-op',
    alreadyCount: 'Already recorded', importedCount: 'Actually imported', noRevision: 'No new financial revision',
    evidence: 'Saved zero-import report evidence', read: 'Read report archive', download: 'Download exact report archive · JSON',
    reportSaved: 'Report saved and evidence verified · zero financial entries and no new portfolio revision.',
    hash: 'Stored UTF-8 bytes match their recorded SHA-256 hashes.', unknown: 'Outcome not confirmed', open: 'Open', uncommitted: 'Uncommitted import report' },
  zh: { parse: '解析所选原始字节', validate: '校验完整批次并获取服务器预览', financial: '确认原子金融导入并保存报告',
    reportOnly: '仅确认零导入报告', saved: '已保存的导入报告', noop: '来源事实已入账 · 明确无操作',
    alreadyCount: '已入账', importedCount: '实际导入', noRevision: '没有新增金融版本',
    evidence: '已保存零导入报告证据', read: '读取报告归档', download: '下载完整报告归档 · JSON',
    reportSaved: '报告已保存且证据已核验 · 零笔金融写入，没有新增组合版本。',
    hash: '保存的 UTF-8 字节与记录的 SHA-256 完全一致。', unknown: '操作结果尚未确认', open: '打开', uncommitted: '尚未提交的导入报告' },
} as const;

/** Drive the whole CSV flow in the browser and return what the real server answered at the preview and at the commit. */
async function importCsv(page: Page, base: string, lang: Lang, mode: 'financial' | 'report', csv: string, namespace: string) {
  const text = ui[lang];
  await page.locator('#csv-kind').selectOption('TRANSACTIONS'); await page.locator('#csv-delimiter').selectOption(',');
  await page.locator('#csv-ack').check(); await page.locator('#csv-file').setInputFiles({ name: 'f3-fictional-repeat.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  const parsed = await observeJson(page, `${base}/imports/parse`);
  await page.getByRole('button', { name: text.parse, exact: true }).click(); expect((await parsed.result).status).toBe(200);
  await page.locator('#csv-date-format').selectOption('ISO'); await page.locator('#csv-decimal').selectOption('.'); await page.locator('#csv-thousands').selectOption('NONE');
  await page.locator('#csv-namespace').fill(namespace);
  for (const [field, column] of [['source_row_key', '0'], ['account_id', '1'], ['event_type', '2'], ['event_date', '3'], ['currency', '4'], ['amount', '5']]) await page.locator(`#csv-map-${field}`).selectOption(column);
  const previewed = await observeJson(page, `${base}/imports/preview`);
  await page.getByRole('button', { name: text.validate, exact: true }).click();
  const preview = await previewed.result; expect(preview.status).toBe(200);
  await page.locator('#csv-confirm').check();
  const committed = await observeJson(page, mode === 'financial' ? `${base}/imports/commit` : `${base}/import-report-operations`);
  await page.getByRole('button', { name: mode === 'financial' ? text.financial : text.reportOnly, exact: true }).click();
  return { preview: preview.body, commit: await committed.result };
}
/** The visible saved report must show exactly the counts and status the server stored, and nothing in an uncertain state. */
async function expectSavedNothingNew(page: Page, lang: Lang, report: { status: string; counts: Record<string, number>; revision_id: string | null }) {
  const text = ui[lang];
  expect(report.status).toBe('ALREADY_IMPORTED'); expect(report.revision_id).toBeNull(); expect(report.counts.imported).toBe(0);
  const saved = page.getByRole('region', { name: text.saved, exact: true });
  await expect(saved).toBeVisible(); await expect(saved.locator('.scope-strip strong')).toHaveText(text.noop);
  await expect(saved.locator('.technical-details').first()).toContainText(text.noRevision);
  expect((await saved.locator('.csv-counts dd').allTextContents()).sort()).toEqual(Object.values(report.counts).map(String).sort());
  const count = (label: string) => saved.locator('.csv-counts > div').filter({ has: page.locator('dt', { hasText: new RegExp(`^${label}$`) }) }).locator('dd');
  await expect(count(text.alreadyCount)).toHaveText(String(report.counts.already_imported)); await expect(count(text.importedCount)).toHaveText('0');
  await expect(page.locator('.guarded-pending')).toHaveCount(0); await expect(page.locator('.guarded-report-pending')).toHaveCount(0);
  await expect(page.getByText(text.unknown, { exact: true })).toHaveCount(0); await expect(page.locator('.csv-workspace .error-notice')).toHaveCount(0);
}

test('guarded repeat CSV import → saved "nothing new" report → reopen, exact archive and download → other writes not blocked → English and Chinese', async ({ page }) => {
  test.setTimeout(240_000); await confine(page.context()); await register(page, 'rpt');
  const name = 'F3 fictional repeat import';
  await page.getByLabel('Portfolio name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Use example quantities', exact: true }).click();
  await page.getByLabel('Opening facts date', { exact: true }).fill('2026-01-01');
  await page.getByRole('checkbox', { name: /I understand these are synthetic/ }).check();
  const created = await observeJson(page, '/api/v1/portfolios');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click();
  const initial = (await created.result).body; expect(initial.disposition).toBe('COMMITTED');
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const root = initial.portfolio_id; const base = `/api/v1/portfolios/${root}`;
  const workspaceNow = async () => (await page.request.get(`${origin}${base}/workspace`)).json();
  const account = (await workspaceNow()).accounts[0].account_id;
  // Newly invented fictional rows; the stable source keys make a second import of the same bytes a no-op.
  const marker = Date.now().toString(36) + Math.random().toString(36).slice(2, 6); const namespace = `f3-repeat-${marker}`;
  const csv = `key,account,type,date,currency,amount\nrpt-cash-${marker}-1,${account},DEPOSIT,2026-01-02,USD,5\nrpt-cash-${marker}-2,${account},DEPOSIT,2026-01-03,USD,8\n`;

  // 1. First import: a genuine financial commit that records the source keys.
  const first = await importCsv(page, base, 'en', 'financial', csv, namespace);
  expect(first.preview.financial_preview).not.toBeNull(); expect(first.commit.status).toBe(200);
  const firstReport = JSON.parse(first.commit.body.response_json).report; expect(firstReport.status).toBe('COMMITTED'); expect(firstReport.counts.imported).toBe(2);
  await expect(page.locator('.revision-strip').first()).toContainText(first.commit.body.revision_id);
  const afterFirst = await workspaceNow();

  // 2. Same bytes again: the server answers with a zero-import report and the UI shows it as saved, not as an uncertain outcome.
  const second = await importCsv(page, base, 'en', 'report', csv, namespace);
  expect(second.preview.financial_preview).toBeNull(); expect(second.preview.report.counts.already_imported).toBe(firstReport.counts.imported);
  await expect(page.getByText(ui.en.reportSaved, { exact: true }).first()).toBeVisible();
  expect(second.commit.status).toBe(200); const envelope = second.commit.body;
  expect(envelope.disposition).toBe('REPORT_COMMITTED'); expect(sha(envelope.response_json)).toBe(envelope.response_sha256);
  const secondReport = JSON.parse(envelope.response_json).report; expect(secondReport.report_id).toBe(envelope.report_id);
  await expectSavedNothingNew(page, 'en', secondReport);
  const afterSecond = await workspaceNow();
  expect(afterSecond.revision_id).toBe(afterFirst.revision_id); expect(afterSecond.ledger.events).toEqual(afterFirst.ledger.events);

  // 3. The saved report evidence: read the exact archive, then download it.
  const evidence = page.getByRole('region', { name: ui.en.evidence, exact: true });
  await expect(evidence).toContainText(envelope.operation_id); await expect(evidence).toContainText(envelope.report_id);
  await evidence.getByRole('button', { name: ui.en.read, exact: true }).click();
  await expect(evidence.locator('.guarded-report-archive-result')).toContainText(envelope.response_sha256);
  await expect(evidence.locator('.guarded-report-archive-result')).toContainText(ui.en.hash);
  const downloading = page.waitForEvent('download'); await evidence.getByRole('button', { name: ui.en.download, exact: true }).click();
  const download = await downloading; expect(download.suggestedFilename()).toBe(`finweb-csv-report-${envelope.report_id}.json`);
  const bytes = await readFile((await download.path())!); const exported = JSON.parse(bytes.toString('utf8'));
  expect(exported.operation_id).toBe(envelope.operation_id); expect(exported.report_id).toBe(envelope.report_id);
  expect(exported.response_sha256).toBe(envelope.response_sha256); expect(sha(exported.response_json)).toBe(exported.response_sha256);
  expect(sha(exported.envelope_json)).toBe(exported.envelope_sha256);
  await test.info().attach('f3-repeat-report-archive.json', { body: bytes, contentType: 'application/json' });
  await expect(page.locator('.guarded-pending')).toHaveCount(0);

  // 4. Reopen after a reload: the saved report is listed by the server and opens again with the same identity.
  await page.reload(); await page.getByRole('button', { name: `Open ${name}`, exact: true }).click();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const listed = (await (await page.request.get(`${origin}${base}/imports`)).json()).reports.find((item: { report_id: string }) => item.report_id === envelope.report_id);
  expect(listed.status).toBe('ALREADY_IMPORTED');
  await page.locator('.csv-reports-list').getByRole('button', { name: `${ui.en.open} ${ui.en.noop} · ${listed.created_at}`, exact: true }).click();
  await expectSavedNothingNew(page, 'en', secondReport);
  await expect(page.locator('.csv-report .technical-details').first()).toContainText(envelope.report_id);

  // 5. Other writes are not blocked: a ledger command commits normally.
  await page.locator('#ledger-event-0-event_type').selectOption('DEPOSIT');
  await page.locator('#ledger-event-0-account_id').selectOption(account);
  await page.locator('#ledger-event-0-event_date').fill('2026-01-04'); await page.locator('#ledger-event-0-currency').fill('USD');
  await page.locator('#ledger-event-0-amount').fill('7');
  const ledgerPreview = await observeJson(page, `${base}/ledger-commands/preview`);
  await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click(); expect((await ledgerPreview.result).status).toBe(200);
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check();
  const ledgerCommit = await observeJson(page, `${base}/ledger-commands`);
  await page.getByRole('button', { name: 'Confirm & append saved revision', exact: true }).click();
  const ledgerResult = await ledgerCommit.result; expect(ledgerResult.status).toBe(200); expect(ledgerResult.body.disposition).toBe('COMMITTED');
  await expect(page.locator('.revision-strip').first()).toContainText(ledgerResult.body.revision_id);
  await expect(page.locator('.guarded-pending')).toHaveCount(0);

  // 6. Chinese: the same bytes a third time give another saved "nothing new" report, shown in Chinese.
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  const third = await importCsv(page, base, 'zh', 'report', csv, namespace);
  expect(third.preview.financial_preview).toBeNull(); expect(third.commit.status).toBe(200);
  const thirdEnvelope = third.commit.body; expect(thirdEnvelope.disposition).toBe('REPORT_COMMITTED');
  expect(thirdEnvelope.report_id).not.toBe(envelope.report_id); expect(sha(thirdEnvelope.response_json)).toBe(thirdEnvelope.response_sha256);
  const thirdReport = JSON.parse(thirdEnvelope.response_json).report;
  await expect(page.getByText(ui.zh.reportSaved, { exact: true }).first()).toBeVisible();
  await expectSavedNothingNew(page, 'zh', thirdReport);
  const zhEvidence = page.getByRole('region', { name: ui.zh.evidence, exact: true });
  await expect(zhEvidence).toContainText(thirdEnvelope.operation_id);
  await zhEvidence.getByRole('button', { name: ui.zh.read, exact: true }).click();
  await expect(zhEvidence.locator('.guarded-report-archive-result')).toContainText(thirdEnvelope.response_sha256);
  await expect(zhEvidence.locator('.guarded-report-archive-result')).toContainText(ui.zh.hash);
  const zhDownloading = page.waitForEvent('download'); await zhEvidence.getByRole('button', { name: ui.zh.download, exact: true }).click();
  const zhExport = JSON.parse((await readFile((await (await zhDownloading).path())!)).toString('utf8'));
  expect(zhExport.operation_id).toBe(thirdEnvelope.operation_id); expect(zhExport.response_sha256).toBe(thirdEnvelope.response_sha256);
  expect((await workspaceNow()).revision_id).toBe(ledgerResult.body.revision_id);
});
