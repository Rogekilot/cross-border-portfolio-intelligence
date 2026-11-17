import { expect, test, type Page } from '@playwright/test';

// One disposable registration per run. All financial UI assertions use actual API strings.
async function createAccount(page: Page) {
  const marker = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  const identity = { username: `cp7b2_test_${marker}`, password: `cp7b2-disposable-only-${marker}` };
  await page.goto('/'); const region = page.getByRole('region', { name: 'Local account', exact: true });
  await region.getByRole('button', { name: 'Sign in', exact: true }).click();
  await region.getByRole('button', { name: 'Create local account', exact: true }).click();
  await region.getByLabel('Username', { exact: true }).fill(identity.username); await region.getByLabel('Password', { exact: true }).fill(identity.password);
  await region.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click();
  await expect(region).toContainText(identity.username);
}
async function save(page: Page, name: string) {
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByLabel('Portfolio name', { exact: true }).fill(name); await page.getByRole('button', { name: 'Use example quantities' }).click();
  await page.getByRole('checkbox').check();
  const pending = page.waitForResponse((r) => r.url().endsWith('/api/v1/portfolios') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click();
  const response = await pending; expect(response.status()).toBe(201); const snapshot = await response.json();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible(); return snapshot;
}
async function previewAndCommit(page: Page) {
  const previewed = page.waitForResponse((r) => r.url().endsWith('/ledger-commands/preview'));
  await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click();
  const previewResponse = await previewed; expect(previewResponse.status()).toBe(200); const preview = await previewResponse.json();
  expect(preview.preview).toBe(true); expect(preview.snapshot.persisted).toBe(false);
  await expect(page.getByRole('heading', { name: 'Uncommitted server preview', exact: true })).toBeVisible();
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check();
  const confirmed = page.waitForResponse((r) => r.url().endsWith('/ledger-commands') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Confirm & append saved revision', exact: true }).click();
  const response = await confirmed; expect(response.status()).toBe(201); const result = await response.json();
  expect(result.snapshot.persisted).toBe(true); expect(result.workspace.revision_id).toBe(result.workspace.current_revision_id);
  await expect(page.locator('.revision-strip').first()).toContainText(result.workspace.revision_id);
  return { result, command: response.request().postDataJSON() };
}

test('ledger preview/correction/history → optional user limits and explicit no benchmark → stale refusal and bilingual narrow revision', async ({ page }) => {
  test.setTimeout(120_000);
  await createAccount(page); const initial = await save(page, 'B2 ledger sandbox');
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const initialWorkspace = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json();
  await expect(page.getByRole('heading', { name: 'Activity & append-only ledger' })).toBeVisible();
  expect(await page.locator('#ledger-event-0-event_type option').evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value).sort()))
    .toEqual(Object.keys(initialWorkspace.ledger.field_rules).filter((family) => family !== 'REVERSAL').sort());
  await expect(page.getByRole('heading', { name: 'Original opening inputs' })).toBeVisible();
  await expect(page.locator('#policy-0-limit')).toHaveCount(0);
  await expect(page.locator('#benchmark-action option[value="SELECT"]')).toBeDisabled();
  await expect(page.getByText('Never stated', { exact: true })).toHaveCount(2);
  await page.locator('#ledger-as-of').fill('2026-01-03');
  await page.locator('#ledger-event-0-event_date').fill('2026-01-03'); await page.locator('#ledger-event-0-currency').fill('USD');
  const invalid = page.waitForResponse((r) => r.url().endsWith('/ledger-commands/preview'));
  await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click(); expect((await invalid).status()).toBe(422);
  await expect(page.locator('.ledger-workspace [role="alert"]')).toBeVisible();
  await page.locator('#ledger-event-0-amount').fill('25');
  const firstPreview = page.waitForResponse((r) => r.url().endsWith('/ledger-commands/preview'));
  await page.getByRole('button', { name: 'Validate & preview changes', exact: true }).click(); expect((await firstPreview).status()).toBe(200);
  const afterPreview = await (await page.request.get(`/api/v1/portfolios/${initial.portfolio_id}/workspace`)).json();
  expect(afterPreview.revision_id).toBe(initialWorkspace.revision_id); expect(afterPreview.ledger.events).toEqual(initialWorkspace.ledger.events);
  // Editing a validated amount invalidates the preview and its confirmation before any append.
  await page.locator('#ledger-event-0-amount').fill('30');
  await expect(page.getByRole('heading', { name: 'Uncommitted server preview' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Confirm & append saved revision' })).toHaveCount(0);
  const { result: appended, command } = await previewAndCommit(page);
  const deposited = appended.workspace.ledger.events.find((event: { event_type: string }) => event.event_type === 'DEPOSIT');
  expect(deposited).toBeTruthy();
  const native = appended.workspace.ledger.current_state.accounts[0].cash.find((cash: { currency: string }) => cash.currency === 'USD');
  await expect(page.locator('.native-balances').first()).toContainText(native.amount);
  const session = await (await page.request.get('/api/v1/auth/session')).json(); const origin = new URL(page.url()).origin;
  const retry = await page.request.post(`/api/v1/portfolios/${initial.portfolio_id}/ledger-commands`, { headers: { Origin: origin, 'X-Finweb-CSRF': session.csrf_token }, data: command });
  expect(retry.status()).toBe(201); expect((await retry.json()).snapshot).toEqual(appended.snapshot);
  await page.getByRole('checkbox', { name: `Select event ${deposited.event_id}`, exact: true }).check();
  await page.getByRole('button', { name: 'Correct selected records', exact: true }).click();
  await expect(page.locator('#ledger-event-0-amount')).toHaveValue(deposited.amount);
  await page.locator('#ledger-event-0-amount').fill('35'); const { result: corrected } = await previewAndCommit(page);
  const original = corrected.workspace.ledger.events.find((event: { event_id: string }) => event.event_id === deposited.event_id);
  expect(original.reversed_by).toBeTruthy();
  expect(corrected.workspace.ledger.events.some((event: { corrects_event_id: string }) => event.corrects_event_id === deposited.event_id)).toBe(true);
  expect(corrected.workspace.ledger.events.length).toBe(appended.workspace.ledger.events.length + 2);
  expect(corrected.snapshot.valuation.metrics.some((metric: { state: string; value: unknown }) => metric.state === 'INSUFFICIENT_DATA' && metric.value === null)).toBe(true);
  const replacement = corrected.workspace.ledger.events.find((event: { corrects_event_id: string }) => event.corrects_event_id === deposited.event_id);
  await page.getByRole('checkbox', { name: `Select event ${replacement.event_id}`, exact: true }).check();
  await page.getByRole('button', { name: 'Reverse selected records', exact: true }).click();
  const { result: reversed } = await previewAndCommit(page);
  expect(reversed.workspace.ledger.events.find((event: { event_id: string }) => event.event_id === replacement.event_id).reversed_by).toBeTruthy();
  await page.getByRole('button', { name: 'Add account container', exact: true }).click();
  await page.getByLabel('New account container name', { exact: true }).fill('Second synthetic container');
  const { result: addedAccount } = await previewAndCommit(page);
  const secondAccount = addedAccount.workspace.accounts.find((account: { name: string }) => account.name === 'Second synthetic container');
  expect(secondAccount).toBeTruthy();
  await page.getByRole('button', { name: 'Append new activity', exact: true }).click();
  await page.locator('#ledger-event-0-event_type').selectOption('TRANSFER_OUT'); await page.locator('#ledger-event-0-account_id').selectOption(initialWorkspace.accounts[0].account_id);
  await page.locator('#ledger-event-0-event_date').fill('2026-01-03'); await page.locator('#ledger-event-0-currency').fill('USD'); await page.locator('#ledger-event-0-amount').fill('1');
  await page.locator('#ledger-event-0-counterparty_account_id').selectOption(secondAccount.account_id);
  await page.getByRole('button', { name: 'Add another event to this atomic batch', exact: true }).click();
  await page.locator('#ledger-event-1-event_type').selectOption('TRANSFER_IN'); await page.locator('#ledger-event-1-account_id').selectOption(secondAccount.account_id);
  await page.locator('#ledger-event-1-event_date').fill('2026-01-03'); await page.locator('#ledger-event-1-currency').fill('USD'); await page.locator('#ledger-event-1-amount').fill('1');
  await page.locator('#ledger-event-1-counterparty_account_id').selectOption(initialWorkspace.accounts[0].account_id);
  const { result: transferred } = await previewAndCommit(page);
  expect(transferred.workspace.ledger.events.filter((event: { event_type: string }) => ['TRANSFER_IN', 'TRANSFER_OUT'].includes(event.event_type))).toHaveLength(2);
  await expect(page.locator('.native-balances').first()).toContainText('Second synthetic container');
  await page.locator('.revision-history summary').click();
  await page.locator('.revision-history li').first().getByRole('button', { name: 'Open revision and its evidence' }).click();
  await expect(page.locator('.revision-strip').first()).toContainText(initialWorkspace.revision_id);
  await expect(page.getByRole('button', { name: 'Append new activity', exact: true })).toBeDisabled();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.locator('.observation').first().getByRole('button', { name: 'View evidence' }).click();
  const dialog = page.getByRole('dialog', { name: 'Evidence & methodology' });
  await expect(dialog.getByText(initial.insights.result_digest, { exact: true })).toBeVisible();
  const reproduced = page.waitForResponse((r) => r.url().includes('/reproduce?revision_id='));
  await dialog.getByRole('button', { name: 'Reproduce recorded result' }).click(); expect((await reproduced).status()).toBe(200);
  await expect(dialog.locator('.reproduction-result')).toContainText('Reproduced'); await dialog.getByRole('button', { name: 'Close evidence' }).click();

  // A second portfolio uses the original source date; no extra account registration is needed.
  await page.getByRole('button', { name: 'New saved synthetic portfolio', exact: true }).click();
  const policySnapshot = await save(page, 'B2 policy sandbox'); await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const policyWorkspace = await (await page.request.get(`/api/v1/portfolios/${policySnapshot.portfolio_id}/workspace`)).json();
  await page.getByRole('button', { name: 'Add a blank personal limit', exact: true }).click();
  await expect(page.locator('#policy-0-limit')).toHaveValue(''); await expect(page.locator('#policy-0-from')).toHaveValue('');
  const target = policyWorkspace.policies.targets.find((candidate: { metric_id: string }) => candidate.metric_id === 'largest_security_weight');
  const targetValue = JSON.stringify([target.source_kind, target.scope_kind, target.account_id ?? null, target.metric_id, target.subject, target.semantic_key]);
  await page.locator('#policy-0-target').selectOption(targetValue); await page.locator('#policy-0-direction').selectOption('MAXIMUM');
  await page.locator('#policy-0-limit').fill('0'); await page.locator('#policy-0-from').fill('2026-01-02'); await page.locator('#policy-0-evidence').fill('Explicit disposable user-stated constraint');
  await page.locator('#benchmark-action').selectOption('CLEAR'); await page.locator('#benchmark-selected-on').fill('2026-01-02');
  await page.getByRole('checkbox', { name: /I explicitly confirm this complete set/ }).check();
  const savedPolicy = page.waitForResponse((r) => r.url().endsWith('/preferences'));
  await page.getByRole('button', { name: 'Confirm & save user choices', exact: true }).click();
  const policyResponse = await savedPolicy; expect(policyResponse.status()).toBe(201); const policyResult = await policyResponse.json();
  expect(policyResult.workspace.policies.state).toBe('ACTIVE'); expect(policyResult.workspace.benchmark.state).toBe('NONE');
  expect(policyResult.snapshot.insights.packets.some((packet: { insight_type: string }) => packet.insight_type === 'user_limit')).toBe(true);
  await expect(page.getByText('Explicitly no benchmark', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page.getByText('No personal risk limit has been supplied. These observations do not judge suitability.', { exact: true })).toHaveCount(0);
  const policyObservation = page.locator('.observation').filter({ has: page.locator('.policy-claim-basis') });
  await expect(policyObservation.locator('.judgment-label')).toHaveText('Depends on your stated preference');
  await expect(policyObservation.locator('.policy-claim-basis')).toContainText('Explicit disposable user-stated constraint');
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  for (const depth of ['速览', '简明', '专业']) {
    await page.getByRole('button', { name: depth, exact: true }).click();
    await expect(policyObservation.locator('.judgment-label')).toHaveText('取决于你声明的偏好');
    await expect(policyObservation.locator('.observation-claim')).toContainText(`超过了你声明的上限（${policyResult.workspace.policies.items[0].limit}）`);
    await expect(policyObservation.locator('.policy-claim-basis')).toContainText('2026-01-02');
  }
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click();
  const exactMetric = policyResult.snapshot.diversification.metrics.find((metric: { metric_id: string }) => metric.metric_id === 'largest_security_weight');
  await page.locator('#policy-0-limit').fill(exactMetric.exact); await page.getByRole('checkbox', { name: /I explicitly confirm this complete set/ }).check();
  const equalitySaved = page.waitForResponse((r) => r.url().endsWith('/preferences'));
  await page.getByRole('button', { name: 'Confirm & save user choices', exact: true }).click();
  const equalityResponse = await equalitySaved; expect(equalityResponse.status()).toBe(201); const equalityResult = await equalityResponse.json();
  expect(equalityResult.snapshot.insights.packets.some((packet: { insight_type: string }) => packet.insight_type === 'user_limit')).toBe(false);

  // A competing explicit instruction advances the head after a UI preview.
  await page.locator('#ledger-as-of').fill('2026-01-03'); await page.locator('#ledger-event-0-event_date').fill('2026-01-03');
  await page.locator('#ledger-event-0-currency').fill('USD'); await page.locator('#ledger-event-0-amount').fill('1');
  const stalePreview = page.waitForResponse((r) => r.url().endsWith('/ledger-commands/preview'));
  await page.getByRole('button', { name: 'Validate & preview changes' }).click(); expect((await stalePreview).status()).toBe(200);
  const competing = await page.request.post(`/api/v1/portfolios/${policySnapshot.portfolio_id}/preferences`, {
    headers: { Origin: origin, 'X-Finweb-CSRF': session.csrf_token }, data: { operation_id: crypto.randomUUID(), expected_revision_id: equalityResult.workspace.revision_id,
      as_of: '2026-01-02', policies: [], policies_confirmed: true, benchmark: { action: 'KEEP' } },
  }); expect(competing.status()).toBe(201); const latest = await competing.json();
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check();
  const stale = page.waitForResponse((r) => r.url().endsWith('/ledger-commands'));
  await page.getByRole('button', { name: 'Confirm & append saved revision' }).click(); expect((await stale).status()).toBe(409);
  await expect(page.getByText('A newer saved revision exists. Open the latest revision and review it before recording new changes.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reload snapshot', exact: true }).click();
  await expect(page.locator('.revision-strip').first()).toContainText(latest.workspace.revision_id);
  await expect(page.locator('#policy-0-limit')).toHaveCount(0); await expect(page.getByText('Explicitly no personal limits', { exact: true })).toBeVisible();
  // A genuinely delayed old refresh must not overwrite the confirmed newer revision.
  await page.locator('#ledger-as-of').fill('2026-01-03'); await page.locator('#ledger-event-0-event_date').fill('2026-01-03');
  await page.locator('#ledger-event-0-currency').fill('USD'); await page.locator('#ledger-event-0-amount').fill('1');
  const racePreview = page.waitForResponse((r) => r.url().endsWith('/ledger-commands/preview'));
  await page.getByRole('button', { name: 'Validate & preview changes' }).click(); expect((await racePreview).status()).toBe(200);
  await page.getByRole('checkbox', { name: /I have reviewed these exact source facts/ }).check();
  let release!: () => void; let entered!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; }); const intercepted = new Promise<void>((resolve) => { entered = resolve; });
  const delayedUrl = `**/api/v1/portfolios/${policySnapshot.portfolio_id}?revision_id=${latest.workspace.revision_id}`;
  await page.route(delayedUrl, async (route) => { const real = await route.fetch(); entered(); await held; await route.fulfill({ response: real }); });
  await page.getByRole('button', { name: 'Reload snapshot', exact: true }).click(); await intercepted;
  const raceCommit = page.waitForResponse((r) => r.url().endsWith('/ledger-commands'));
  await page.getByRole('button', { name: 'Confirm & append saved revision', exact: true }).click();
  const raceResponse = await raceCommit; expect(raceResponse.status()).toBe(201); const raceResult = await raceResponse.json();
  await expect(page.locator('.revision-strip').first()).toContainText(raceResult.workspace.revision_id);
  const oldDelivered = page.waitForResponse((r) => r.url().includes(`?revision_id=${latest.workspace.revision_id}`)); release(); await (await oldDelivered).finished();
  await expect(page.locator('.revision-strip').first()).toContainText(raceResult.workspace.revision_id); await page.unroute(delayedUrl);
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  await expect(page.locator('.revision-strip').first()).toContainText(raceResult.workspace.revision_id);
  await expect(page.getByRole('heading', { name: '活动与只追加流水', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '个人限制与组合基准', exact: true })).toBeVisible();
  await expect(page.getByText('明确无基准', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await expect(page.getByRole('heading', { name: '活动与只追加流水', exact: true })).toHaveCount(0);
  await expect(page.locator('.revision-strip')).toHaveCount(0); await expect(page.locator('.preferences-section')).toHaveCount(0);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
});
