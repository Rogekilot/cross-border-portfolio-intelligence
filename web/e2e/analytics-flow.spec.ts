import { expect, test, type Page } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function artifact(name: string, bytes: Buffer) {
  const directory = process.env.FINWEB_D_ARTIFACT_DIR;
  if (directory) { await mkdir(directory, { recursive: true }); await writeFile(join(directory, name), bytes, { flag: 'wx' }); }
}
async function create(page: Page) {
  const marker = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  await page.goto('/'); const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click(); await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(`cp7d_test_${marker}`); await account.getByLabel('Password', { exact: true }).fill(`cp7d-disposable-only-${marker}`);
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByLabel('Portfolio name', { exact: true }).fill('D fictional unknown and known basis'); await page.locator('#quantity-SYN-B').fill('1'); await page.getByLabel('Opening cash (USD)', { exact: true }).fill('1'); await page.getByRole('checkbox').check();
  const pending = page.waitForResponse((response) => response.url().endsWith('/api/v1/portfolios') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click(); const response = await pending; expect(response.status()).toBe(201); return response.json();
}
async function ledgerCommit(page: Page) {
  const preview = page.waitForResponse((response) => response.url().endsWith('/ledger-commands/preview')); await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click(); expect((await preview).status()).toBe(200);
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check(); const commit = page.waitForResponse((response) => response.url().endsWith('/ledger-commands'));
  await page.getByRole('button', { name: 'Confirm & append saved revision', exact: true }).click(); const response = await commit; expect(response.status()).toBe(201); const result = await response.json(); await expect(page.locator('.revision-strip').first()).toContainText(result.workspace.revision_id); return result;
}
async function evaluate(page: Page, status = 200) {
  const family = await page.locator('#analytics-family').inputValue();
  const pending = page.waitForResponse((response) => response.url().endsWith('/analytics/evaluate') && response.request().postDataJSON().family === family);
  const button = page.locator('.analytical-workspace').getByRole('button', { name: /Evaluate this exact question|计算本确切问题/, exact: true });
  await button.focus(); await page.keyboard.press('Enter'); const response = await pending; expect(response.status()).toBe(status); return response.json();
}

test('owned revision analytics → exact/partial zero gains → default risk X/Y own proof → family/identity race → bilingual depth/390px/history', async ({ page }) => {
  test.setTimeout(180_000); const initial = await create(page);
  await expect(page.getByRole('heading', { name: 'D fictional unknown and known basis', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Performance', exact: true })).toBeVisible(); await expect(page.getByRole('region', { name: 'Risk', exact: true })).toBeVisible();
  const commonRestrictions = page.locator('#observations-common-restrictions');
  for (const language of ['en', 'zh-CN']) {
    await page.locator('.language-control select').selectOption(language);
    for (const depth of language === 'en' ? ['Quick', 'Simple', 'Professional'] : ['速览', '简明', '专业']) {
      await page.getByRole('button', { name: depth, exact: true }).click(); await expect(commonRestrictions.locator('li')).toHaveCount(5);
      await expect(page.locator('.observation .shared-restriction-reference a')).toHaveCount(initial.insights.packets.length);
      await expect(commonRestrictions).toContainText(language === 'en' ? 'every observation below' : '以下全部观察共同适用');
    }
  }
  await page.locator('.language-control select').selectOption('en'); await page.getByRole('button', { name: 'Quick', exact: true }).click();
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click(); const initialWorkspace = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json();
  await page.getByRole('button', { name: 'Add account container', exact: true }).click(); await page.getByLabel('New account container name', { exact: true }).fill('D known recorded basis'); const added = await ledgerCommit(page);
  const account = added.workspace.accounts.find((item: { name: string }) => item.name === 'D known recorded basis'); const listing = added.workspace.listings.find((item: { symbol: string }) => item.symbol === 'SYN-A');
  await page.getByRole('button', { name: 'Append new activity', exact: true }).click(); await page.locator('#ledger-event-0-event_type').selectOption('OPENING_POSITION'); await page.locator('#ledger-event-0-account_id').selectOption(account.account_id);
  await page.locator('#ledger-event-0-event_date').fill('2026-01-02'); await page.locator('#ledger-event-0-currency').fill('USD'); await page.locator('#ledger-event-0-listing_id').selectOption(listing.listing_id); await page.locator('#ledger-event-0-quantity').fill('2'); await page.locator('#ledger-event-0-cost_basis').fill('200'); const opened = await ledgerCommit(page);
  await page.getByRole('link', { name: 'Analytics', exact: true }).click(); await page.locator('#analytics-family').selectOption('GAINS'); await page.locator('#analytics-scope').selectOption(account.account_id);
  const known = await evaluate(page); const knownTotal = known.results[0].engine_result.metrics.find((metric: { metric_id: string }) => metric.metric_id === 'unrealized_gain_total');
  expect(knownTotal.state).toBe('AVAILABLE'); expect(knownTotal.value).toBe('0'); expect(knownTotal.exact).toBe('0/1');
  const gainCard = page.locator('.analytical-metric[data-metric-id="unrealized_gain_total"]'); await expect(gainCard.locator('.metric-value > span').first()).toHaveText(knownTotal.value); await expect(gainCard).toContainText('Exactly zero');
  await gainCard.locator('.claim-depth select').selectOption('professional'); await expect(gainCard).toContainText(known.results[0].engine_result.manifest_id); await expect(gainCard).toContainText('2026-01-02 → 2026-01-02');
  const completeBinding = gainCard.locator('.analytics-complete-binding'); await expect(completeBinding).not.toHaveAttribute('open', '');
  await completeBinding.locator('summary').focus(); await page.keyboard.press('Enter'); await expect(completeBinding).toHaveAttribute('open', ''); await expect(completeBinding.locator('pre')).toContainText(known.results[0].binding.input_sha256); await page.keyboard.press('Enter'); await expect(completeBinding).not.toHaveAttribute('open', '');
  await page.getByRole('button', { name: 'Simple', exact: true }).click(); await expect(gainCard.locator('.analytics-method-details')).toBeVisible(); await gainCard.locator('.claim-depth select').selectOption(''); await expect(gainCard.locator('.analytics-method-details')).toHaveCount(0);
  await page.locator('#analytics-scope').selectOption(''); const partial = await evaluate(page); const partialTotal = partial.results[0].engine_result.metrics.find((metric: { metric_id: string }) => metric.metric_id === 'unrealized_gain_total');
  expect(partialTotal.state).toBe('LIMITED'); expect(partialTotal.value).toBe('0'); expect(partialTotal.excluded_weight).not.toBeNull(); expect(partialTotal.partial).toBe(false);
  await expect(gainCard).toContainText(partialTotal.excluded_weight); await expect(gainCard).toContainText('Excluded components: Unknown'); await expect(gainCard).not.toContainText('Value of priced holdings (partial)');
  await page.getByRole('combobox', { name: 'Gain/loss color convention', exact: true }).selectOption('RED_GAIN'); await expect(gainCard).toHaveClass(/colors-red_gain/);
  await page.getByRole('combobox', { name: 'Interface language', exact: true }).selectOption('zh-CN');
  for (const depth of ['速览', '简明', '专业']) { await page.getByRole('button', { name: depth, exact: true }).click(); await expect(gainCard.locator('.metric-value > span').first()).toHaveText('0'); await expect(gainCard).toContainText('引擎给出的排除权重'); }
  for (const depth of ['quick', 'simple', 'professional']) { await gainCard.locator('.claim-depth select').selectOption(depth); await expect(gainCard).toContainText(partialTotal.excluded_weight); }
  await page.setViewportSize({ width: 390, height: 844 }); await gainCard.locator('.metric-topline').scrollIntoViewIfNeeded(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); await artifact('d-zh-partial-zero-390px.png', await page.screenshot());
  await page.getByRole('combobox', { name: '界面语言', exact: true }).selectOption('en'); await page.setViewportSize({ width: 1280, height: 900 });
  // A real GAINS response arrives after another family has become the current question.
  let release!: () => void; let computed!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; }); const ready = new Promise<void>((resolve) => { computed = resolve; });
  const endpoint = `**/api/v1/portfolios/${initial.portfolio_id}/analytics/evaluate`;
  await page.route(endpoint, async (route) => { if (route.request().postDataJSON().family === 'GAINS') { const response = await route.fetch(); computed(); await gate; await route.fulfill({ response }); } else await route.continue(); });
  const delayedDelivered = page.waitForResponse((response) => response.url().endsWith('/analytics/evaluate') && response.request().postDataJSON().family === 'GAINS');
  await page.getByRole('button', { name: 'Evaluate this exact question', exact: true }).click(); await ready;
  await page.locator('#analytics-family').selectOption('RISK'); await expect(page.locator('.analytics-result-region .analytical-metric')).toHaveCount(0); const risk = await evaluate(page); release(); expect((await delayedDelivered).status()).toBe(200); await page.unroute(endpoint);
  await expect(page.locator('.analytics-result-region .analytical-metric[data-metric-id="unrealized_gain_total"]')).toHaveCount(0);
  const fallback = risk.views.find((view: { fallback: boolean }) => view.fallback); expect(fallback).toBeTruthy(); expect(risk.results.some((result: { engine_result: { metrics: { observation_count: unknown }[] } }) => result.engine_result.metrics.some((metric) => metric.observation_count === null))).toBe(true);
  const evidenceOpener = page.locator('.fallback-evidence').first().getByRole('button', { name: 'Original refused request · View evidence', exact: true }); await evidenceOpener.click();
  const dialog = page.getByRole('dialog', { name: 'Analytical evidence & methodology', exact: true }); const refused = risk.results.find((result: { result_id: string }) => result.result_id === fallback.refused_result_id);
  await expect(dialog).toContainText(refused.engine_result.manifest_id); await dialog.getByRole('button', { name: 'Reproduce this analytical result', exact: true }).click(); await expect(dialog.locator('.reproduction-result')).toContainText('Reproduced'); await page.keyboard.press('Escape'); await expect(dialog).toHaveCount(0); await expect(evidenceOpener).toBeFocused();
  await artifact('d-risk-xy-desktop.png', await page.locator('.analytical-workspace').screenshot());
  await page.locator('#analytics-family').selectOption('PERFORMANCE_WINDOW'); await page.locator('#analytics-rule').selectOption('CUSTOM'); await page.locator('#analytics-base').fill('2025-01-01'); const beforeSnapshot = await evaluate(page); expect(beforeSnapshot.results[0].engine_result.metrics.find((metric: { metric_id: string }) => metric.metric_id === 'return_twr').value).toBeNull();
  await page.locator('#analytics-base').fill('2000-01-01'); const refusedSpan = await evaluate(page, 422); expect(refusedSpan.error.code).toBe('ANALYTICS_SPAN_LIMIT'); await expect(page.locator('.analytics-result-region [role="alert"]')).toContainText('3,660');
  // Use the offered native date input and real keyboard focus/blur. A visible
  // DOM string alone is not proof that React submitted that explicit date.
  for (const language of ['en', 'zh-CN']) {
    await page.locator('.language-control select').selectOption(language); await page.locator('#analytics-rule').selectOption('CUSTOM');
    await page.locator('#analytics-base').fill('2010-01-01'); await page.locator('#analytics-base').press('Tab'); await expect(page.locator('#analytics-base')).toHaveValue('2010-01-01');
    await expect(page.locator('.analytical-workspace').getByRole('button', { name: /Evaluate this exact question|计算本确切问题/, exact: true })).toBeEnabled();
    const sent = page.waitForRequest((request) => request.url().endsWith('/analytics/evaluate') && request.postDataJSON().window.base === '2010-01-01');
    const error = await evaluate(page, 422); const submitted = (await sent).postDataJSON(); expect(submitted.window).toEqual({ rule: 'CUSTOM', months: null, base: '2010-01-01' }); expect(error.error.code).toBe('ANALYTICS_SPAN_LIMIT');
    expect(error).not.toHaveProperty('results'); await expect(page.locator('.analytics-result-region [role="alert"]')).toContainText(language === 'en' ? 'local 3,660-day' : '本地 3,660 天');
    await artifact(`d-custom-date-resource-${language}.png`, await page.locator('.analytical-workspace').screenshot());
    await page.locator('#analytics-rule').selectOption('SINCE_INCEPTION'); await expect(page.locator('.analytics-result-region [role="alert"]')).toHaveCount(0); const recovered = await evaluate(page);
    expect(recovered.question.window).toEqual({ rule: 'SINCE_INCEPTION', months: null, base: null }); await expect(page.locator('.analytics-result-region .analytical-metric').first()).toBeVisible();
  }
  await page.locator('.language-control select').selectOption('en');
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click(); await page.locator('.revision-history summary').click(); await page.locator('.revision-history li').first().getByRole('button', { name: 'Open revision and its evidence' }).click();
  const downloadPending = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download Complete transaction audit · JSON', exact: true }).click(); const download = await downloadPending; const bytes = await readFile((await download.path())!); expect(JSON.parse(bytes.toString('utf8')).events).toEqual(initialWorkspace.ledger.events); await artifact('d-original-revision-transactions.json', bytes);
  const oldSnapshot = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}?revision_id=${initialWorkspace.revision_id}`)).json(); expect(oldSnapshot).toEqual(initial);
  // Hold the real selected snapshot so a newer user navigation wins over the
  // earlier Open latest request, while the validated workspace still arrives.
  let releaseSnapshot!: () => void; let snapshotReady!: () => void; const snapshotGate = new Promise<void>((resolve) => { releaseSnapshot = resolve; }); const snapshotComputed = new Promise<void>((resolve) => { snapshotReady = resolve; });
  const snapshotRoute = (url: URL) => url.pathname === `/api/v1/portfolios/${initial.portfolio_id}` && url.searchParams.get('revision_id') === opened.workspace.revision_id;
  await page.route(snapshotRoute, async (route) => { const response = await route.fetch(); snapshotReady(); await snapshotGate; await route.fulfill({ response }); });
  await page.getByRole('button', { name: 'Open latest revision', exact: true }).click(); await snapshotComputed; await page.getByRole('link', { name: 'Analytics', exact: true }).click(); releaseSnapshot();
  await expect(page.locator('.revision-strip').first()).toContainText(opened.workspace.revision_id); await expect(page).toHaveURL(/\/analytics$/); await page.unroute(snapshotRoute); await page.locator('#analytics-family').selectOption('GAINS');
  let releasePrivate!: () => void; let privateReady!: () => void; const privateGate = new Promise<void>((resolve) => { releasePrivate = resolve; }); const privateComputed = new Promise<void>((resolve) => { privateReady = resolve; });
  await page.route(endpoint, async (route) => { const response = await route.fetch(); privateReady(); await privateGate; await route.fulfill({ response }).catch(() => {}); });
  await page.getByRole('button', { name: 'Evaluate this exact question', exact: true }).click(); await privateComputed; await page.getByRole('button', { name: 'Sign out', exact: true }).click(); releasePrivate(); await page.unroute(endpoint);
  await expect(page.locator('.analytical-workspace')).toHaveCount(0); await expect(page.getByText('D fictional unknown and known basis', { exact: true })).toHaveCount(0); expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  expect(opened.workspace.revision_id).not.toBe(initialWorkspace.revision_id);
});
