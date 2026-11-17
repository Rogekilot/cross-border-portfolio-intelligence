import { expect, test, type Page } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const sourceText = '\ufeffrow;kind;date;symbol;qty;amount;ccy;basis;note;note\r\ncash-1;CASH;2026-01-02;;;50;USD;;"=fictional";"two\nphysical lines"\r\npos-1;POSITION;2026-01-02;UNKNOWN;;;USD;;"<img src=x>";""\r\n';
const sourceBytes = Buffer.from(sourceText, 'utf8');
let artifactNumber = 0;
async function retainArtifact(name: string, bytes: Buffer, contentType: string) {
  const directory = process.env.FINWEB_CSV_ARTIFACT_DIR;
  if (directory) { await mkdir(directory, { recursive: true }); await writeFile(join(directory, `${++artifactNumber}-${name}`), bytes, { flag: 'wx' }); }
  await test.info().attach(name, { body: bytes, contentType });
}
async function createAccountAndPortfolio(page: Page) {
  const marker = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  await page.goto('/'); const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click(); await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(`cp7c_test_${marker}`);
  await account.getByLabel('Password', { exact: true }).fill(`cp7c-disposable-only-${marker}`);
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByLabel('Portfolio name', { exact: true }).fill('C fictional import sandbox'); await page.getByRole('button', { name: 'Use example quantities' }).click();
  await page.getByRole('checkbox').check(); const created = page.waitForResponse((r) => r.url().endsWith('/api/v1/portfolios') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click(); const snapshot = await (await created).json();
  await expect(page.getByRole('heading', { name: 'C fictional import sandbox', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click(); return snapshot;
}
async function source(page: Page, kind: 'HOLDINGS' | 'TRANSACTIONS', bytes: Buffer, name: string) {
  await page.locator('#csv-kind').selectOption(kind); await page.locator('#csv-delimiter').selectOption(';'); await page.locator('#csv-ack').check();
  await page.locator('#csv-file').setInputFiles({ name, mimeType: 'text/csv', buffer: bytes });
  const parsed = page.waitForResponse((r) => r.url().endsWith('/imports/parse'));
  const parseButton = page.getByRole('button', { name: 'Parse selected bytes', exact: true });
  await expect(parseButton).toBeEnabled(); await page.locator('#csv-file').focus(); await page.keyboard.press('Tab'); await expect(parseButton).toBeFocused(); await page.keyboard.press('Enter');
  const response = await parsed; expect(response.status()).toBe(200); const result = await response.json();
  expect(response.request().postDataJSON().delimiter).toBe(';'); await expect(page.locator('#csv-date-format')).toBeVisible();
  await page.locator('#csv-date-format').selectOption('ISO'); await page.locator('#csv-decimal').selectOption('.'); await page.locator('#csv-thousands').selectOption('NONE');
  await page.locator('#csv-namespace').fill('fictional-c-source'); return result;
}
async function holdingsMapping(page: Page) {
  await page.locator('#csv-source-account').fill('fictional-source-account'); await page.locator('#csv-snapshot-key').fill('opening-2026-01-02'); await page.locator('#csv-new-account').fill('=C Fictional import');
  for (const [field, index] of [['source_row_key', 0], ['event_type', 1], ['event_date', 2], ['symbol', 3], ['quantity', 4], ['amount', 5], ['currency', 6], ['cost_basis', 7]] as const) await page.locator(`#csv-map-${field}`).selectOption(String(index));
}
async function getPreview(page: Page) {
  const pending = page.waitForResponse((r) => r.url().endsWith('/imports/preview'));
  await page.getByRole('button', { name: 'Validate complete batch & obtain server preview', exact: true }).click();
  const response = await pending; expect(response.status()).toBe(200); return response.json();
}
async function commitPreview(page: Page, financial: boolean) {
  await page.locator('#csv-confirm').check(); const pending = page.waitForResponse((r) => r.url().endsWith('/imports/commit'));
  await page.getByRole('button', { name: financial ? 'Confirm atomic financial import & report' : 'Confirm zero-import report only', exact: true }).click();
  const response = await pending; expect(response.status()).toBe(201); const result = await response.json();
  await expect(page.locator('.csv-report.is-persisted').getByText(result.report.report_id, { exact: true })).toBeVisible(); return result;
}
async function downloaded(page: Page, button: string) {
  const pending = page.waitForEvent('download'); await page.getByRole('button', { name: button, exact: true }).click(); const download = await pending;
  expect(download.suggestedFilename()).toMatch(/^finweb-[a-zA-Z0-9._-]+\.(csv|json)$/);
  const bytes = await readFile((await download.path())!);
  await retainArtifact(download.suggestedFilename(), bytes, download.suggestedFilename().endsWith('.json') ? 'application/json' : 'text/csv');
  return bytes.toString('utf8');
}

test('fictional indexed CSV → zero-write quarantine → explicit correction → atomic new-account holdings → source no-op → transactions → fixed exports/history/identity clearing', async ({ page }) => {
  test.setTimeout(180_000); const initial = await createAccountAndPortfolio(page);
  const initialWorkspace = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json();
  const parsed = await source(page, 'HOLDINGS', sourceBytes, 'fictional-holdings.csv'); expect(parsed.bom).toBe(true);
  expect(parsed.columns[8].header).toBe(parsed.columns[9].header); expect(parsed.rows[0].physical_end).toBeGreaterThan(parsed.rows[0].physical_start);
  await holdingsMapping(page); const quarantined = await getPreview(page);
  expect(quarantined.report.counts.ready).toBe(1); expect(quarantined.report.counts.quarantined).toBe(1); expect(quarantined.financial_preview).toBeNull();
  expect(quarantined.report.proposal.file_base64).toBe(sourceBytes.toString('base64'));
  await expect(page.getByRole('button', { name: 'Confirm atomic financial import & report', exact: true })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  await expect(page.locator('.csv-confirmation')).toContainText('证券未知、存在歧义或标识冲突');
  await expect(page.locator('.csv-confirmation')).toContainText('全部金融写入已被阻止');
  await retainArtifact('csv-zh-quarantine.png', await page.locator('.csv-confirmation').screenshot(), 'image/png');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  const zero = await commitPreview(page, false); expect(zero.report.status).toBe('REPORT_ONLY'); expect(zero.report.counts.imported).toBe(0); expect(zero.workspace_result).toBeNull();
  const unchanged = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json();
  expect(unchanged.accounts).toEqual(initialWorkspace.accounts); expect(unchanged.ledger.events).toEqual(initialWorkspace.ledger.events); expect(unchanged.revision_id).toBe(initialWorkspace.revision_id);
  const row = page.locator('.csv-source-rows > details').nth(1); await row.locator('summary').first().click(); await row.locator('details > summary').first().click();
  const listing = initialWorkspace.listings.find((item: { symbol: string }) => item.symbol === 'SYN-A');
  await page.locator('#csv-row-2-listing_id').selectOption(listing.listing_id); await page.locator('#csv-row-2-symbol').fill('SYN-A'); await page.locator('#csv-row-2-quantity').fill('2');
  await page.locator('#csv-row-2-correction-reason').fill('Correct explicit fictional listing and missing quantity from the test source');
  const corrected = await getPreview(page); expect(corrected.report.counts.quarantined).toBe(0); expect(corrected.financial_preview.snapshot.persisted).toBe(false);
  expect(corrected.report.rows[1].cells[3]).toBe('UNKNOWN'); expect(corrected.report.rows[1].event).not.toHaveProperty('cost_basis');
  await page.locator('#csv-snapshot-key').fill('changed-source-key'); await expect(page.locator('.csv-confirmation')).toHaveCount(0);
  await page.locator('#csv-snapshot-key').fill('opening-2026-01-02'); await getPreview(page);
  const saved = await commitPreview(page, true); expect(saved.report.status).toBe('COMMITTED'); expect(saved.report.counts.imported).toBe(2);
  const account = saved.workspace_result.workspace.accounts.find((item: { name: string }) => item.name === '=C Fictional import'); expect(account).toBeTruthy();
  await expect(page.locator('#csv-file')).toHaveValue('');
  const reportJson = JSON.parse(await downloaded(page, 'Download full report · JSON'));
  expect(reportJson.proposal.file_base64).toBe(sourceBytes.toString('base64')); expect(reportJson.proposal.corrections[0].reason).toContain('explicit fictional');
  const holdingsCsv = await downloaded(page, 'Download Native holdings and states · CSV'); expect(holdingsCsv).toContain("'=C Fictional import");
  const nativeJson = JSON.parse(await downloaded(page, 'Download Native holdings and states · JSON'));
  expect(nativeJson.revision_id).toBe(saved.report.revision_id); expect(nativeJson.accounts).toContainEqual({ account_id: account.account_id, name: '=C Fictional import' });
  // Same stable source under a new command is an explicit no-op, not a second account.
  await source(page, 'HOLDINGS', sourceBytes, 'fictional-holdings.csv'); await holdingsMapping(page);
  const sourceRow = page.locator('.csv-source-rows > details').nth(1); await sourceRow.locator('summary').first().click(); await sourceRow.locator('details > summary').first().click();
  await page.locator('#csv-row-2-listing_id').selectOption(listing.listing_id); await page.locator('#csv-row-2-symbol').fill('SYN-A'); await page.locator('#csv-row-2-quantity').fill('2'); await page.locator('#csv-row-2-correction-reason').fill('Same explicit fictional correction');
  const already = await getPreview(page); expect(already.report.counts.already_imported).toBe(2); expect(already.financial_preview).toBeNull();
  const noOp = await commitPreview(page, false); expect(noOp.report.status).toBe('ALREADY_IMPORTED'); expect(noOp.report.counts.imported).toBe(0);
  expect((await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json()).accounts).toHaveLength(initialWorkspace.accounts.length + 1);
  const transactions = Buffer.from('key;type;date;symbol;qty;amount;currency;basis\r\nt1;DEPOSIT;2026-01-03;;;10;USD;\r\nt2;DEPOSIT;2026-01-03;;;10;USD;\r\nt3;TRANSFER_IN;2026-01-03;SYN-B;1;;USD;0\r\nfooter;NOTE;;;;;;\r\n');
  await source(page, 'TRANSACTIONS', transactions, 'fictional-transactions.csv'); await page.locator('#csv-as-of').fill('2026-01-03');
  for (const [field, index] of [['source_row_key', 0], ['event_type', 1], ['event_date', 2], ['symbol', 3], ['quantity', 4], ['amount', 5], ['currency', 6], ['cost_basis', 7]] as const) await page.locator(`#csv-map-${field}`).selectOption(String(index));
  await page.locator('#csv-constant-account_id').selectOption(account.account_id);
  const footer = page.locator('.csv-source-rows > details').nth(3); await footer.locator('summary').first().click(); await page.locator('#csv-row-4-classification').selectOption('NON_DATA'); await page.locator('#csv-row-4-classification-reason').fill('Explicit fictional file footer, not an economic record');
  const transactionPreview = await getPreview(page); expect(transactionPreview.report.counts.excluded).toBe(1); expect(transactionPreview.report.rows[2].event.cost_basis).toBe('0');
  // Hold a real committed response: navigation may clear the local panel, but the
  // validated result must still advance the same-account parent revision.
  let releaseCommit!: () => void; let serverCommitted!: () => void; let serverResult: any;
  const commitGate = new Promise<void>((resolve) => { releaseCommit = resolve; }); const committed = new Promise<void>((resolve) => { serverCommitted = resolve; });
  const commitUrl = `**/api/v1/portfolios/${initial.portfolio_id}/imports/commit`;
  await page.route(commitUrl, async (route) => { const real = await route.fetch(); serverResult = await real.json(); serverCommitted(); await commitGate; await route.fulfill({ response: real }); });
  await page.locator('#csv-confirm').check(); const deliveredCommit = page.waitForResponse((r) => r.url().endsWith('/imports/commit'));
  await page.getByRole('button', { name: 'Confirm atomic financial import & report', exact: true }).click(); await committed;
  await page.getByRole('link', { name: 'Overview', exact: true }).click(); await expect(page.locator('.csv-workspace')).toHaveCount(0);
  releaseCommit(); expect((await deliveredCommit).status()).toBe(201); const imported = serverResult;
  await expect(page.locator('.revision-strip').first()).toContainText(imported.report.revision_id); await page.unroute(commitUrl);
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  await expect(page.locator('.csv-report.is-persisted').getByText(imported.report.report_id, { exact: true })).toBeVisible();
  expect(imported.report.counts.imported).toBe(3);
  expect(imported.report.rows[0].event_id).not.toBe(imported.report.rows[1].event_id);
  const allTransactions = JSON.parse(await downloaded(page, 'Download Complete transaction audit · JSON'));
  expect(allTransactions.events).toEqual(imported.workspace_result.workspace.ledger.events);
  await downloaded(page, 'Download full report · CSV');
  // An old saved proof and old fixed-revision export remain unchanged after both imports.
  await page.locator('.revision-history summary').click(); await page.locator('.revision-history li').first().getByRole('button', { name: 'Open revision and its evidence' }).click();
  await expect(page.locator('.csv-import-form')).toHaveCount(0);
  const oldExport = JSON.parse(await downloaded(page, 'Download Complete transaction audit · JSON')); expect(oldExport.events).toEqual(initialWorkspace.ledger.events);
  await page.getByRole('link', { name: 'Overview', exact: true }).click(); await page.locator('.observation').first().getByRole('button', { name: 'View evidence' }).click();
  const dialog = page.getByRole('dialog', { name: 'Evidence & methodology' }); await expect(dialog.getByText(initial.insights.result_digest, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Reproduce recorded result' }).click(); await expect(dialog.locator('.reproduction-result')).toContainText('Reproduced'); await dialog.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click(); await page.getByRole('button', { name: 'Open latest revision', exact: true }).click();
  await source(page, 'HOLDINGS', sourceBytes, 'fictional-private-pending.csv'); await holdingsMapping(page); await getPreview(page);
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  await expect(page.getByRole('heading', { name: 'CSV 导入、报告与导出', exact: true })).toBeVisible(); await expect(page.locator('.csv-confirmation')).toContainText('全部金融写入已被阻止');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('heading', { name: 'CSV 导入、报告与导出', exact: true }).scrollIntoViewIfNeeded();
  await retainArtifact('csv-zh-390px.png', await page.screenshot(), 'image/png');
  await page.getByRole('button', { name: '退出登录', exact: true }).click(); await expect(page.locator('.csv-workspace')).toHaveCount(0);
  await expect(page.getByText('fictional-private-pending.csv', { exact: false })).toHaveCount(0); expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
});
