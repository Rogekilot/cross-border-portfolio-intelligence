import { expect, test, type Page } from '@playwright/test';

// Disposable local test identities only. No real user account or credential is used.
function testIdentity(suffix: string) {
  const marker = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  return { username: `cp7b_test_${suffix}_${marker}`.slice(0, 32), password: `cp7b-local-test-only-${marker}` };
}
async function register(page: Page, identity: { username: string; password: string }) {
  await page.goto('/');
  const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click();
  await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(identity.username);
  await account.getByLabel('Password', { exact: true }).fill(identity.password);
  const result = page.waitForResponse((r) => r.url().endsWith('/api/v1/auth/register') && r.request().method() === 'POST');
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click();
  expect((await result).status()).toBe(201);
  await expect(account).toContainText(`Signed in as ${identity.username}`);
  await expect(page.getByRole('heading', { name: 'Save a synthetic sandbox' })).toBeVisible();
  await expect(account.locator('#account-password')).toHaveCount(0);
}
async function save(page: Page, name: string) {
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByLabel('Portfolio name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Use example quantities' }).click();
  await page.getByRole('checkbox').check();
  const result = page.waitForResponse((r) => r.url().endsWith('/api/v1/portfolios') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save & analyze synthetic portfolio', exact: true }).click();
  const response = await result; expect(response.status()).toBe(201); const snapshot = await response.json();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  expect(snapshot.mode).toBe('LOCAL_SYNTHETIC_ACCOUNT'); expect(snapshot.synthetic).toBe(true); expect(snapshot.persisted).toBe(true);
  return snapshot;
}

test('account → explicit synthetic save → owned list → browser reload → actual saved Proof Packet reproduction → logout clearing', async ({ page }) => {
  const identity = testIdentity('a'); const name = `Saved sandbox ${identity.username}`;
  await register(page, identity); const snapshot = await save(page, name);
  const cookies = await page.context().cookies();
  expect(cookies.some((cookie) => cookie.httpOnly && cookie.sameSite === 'Strict')).toBe(true);
  expect(await page.evaluate(() => document.cookie)).toBe('');
  const account = page.getByRole('region', { name: 'Local account', exact: true });
  await expect(account.getByRole('button', { name: `Open ${name}`, exact: true })).toBeVisible();
  const total = snapshot.valuation.metrics.find((m: { metric_id: string; view: string }) => m.metric_id === 'portfolio_value' && m.view === 'REPORTING');
  await expect(page.locator('.metric-grid .metric-card').first().locator('.metric-value > span').first()).toHaveText(total.value);
  const digest = snapshot.insights.result_digest;
  await page.reload();
  await expect(account).toContainText(`Signed in as ${identity.username}`);
  await account.getByRole('button', { name: `Open ${name}`, exact: true }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.locator('.observation').first().getByRole('button', { name: 'View evidence' }).click();
  const dialog = page.getByRole('dialog', { name: 'Evidence & methodology' });
  await expect(dialog.getByText(digest, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Reproduce recorded result' }).click();
  await expect(dialog.locator('.reproduction-result')).toContainText('Reproduced');
  await dialog.getByRole('button', { name: 'Close evidence' }).click();
  await account.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(account).toContainText('Guest access');
  await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
  await expect(account.getByRole('button', { name: `Open ${name}`, exact: true })).toHaveCount(0);
  await expect(page.locator('.observation')).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(identity.username);
  await account.getByLabel('Password', { exact: true }).fill(identity.password);
  await account.locator('form').getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(account).toContainText(`Signed in as ${identity.username}`);
  await account.getByRole('button', { name: `Open ${name}`, exact: true }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  // Removing the cookie exercises the actual protected API's 401 clearing path.
  await page.context().clearCookies();
  await page.getByRole('button', { name: 'Reload snapshot', exact: true }).click();
  await expect(page.getByText('The account session ended or could not be verified. Private portfolios and evidence have been cleared. Sign in again.', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
  await expect(page.locator('.observation')).toHaveCount(0);
});

test('separate accounts cannot list/read/open/reproduce foreign portfolio IDs; bilingual narrow login remains usable', async ({ page, browser }) => {
  const owner = testIdentity('owner'); const other = testIdentity('other');
  await register(page, owner); const snapshot = await save(page, `Owner sandbox ${owner.username}`);
  const origin = new URL(page.url()).origin;
  const otherContext = await browser.newContext({ baseURL: origin, viewport: { width: 390, height: 844 } });
  const otherPage = await otherContext.newPage(); await register(otherPage, other);
  const otherAccount = otherPage.getByRole('region', { name: 'Local account', exact: true });
  await expect(otherAccount).toContainText('No saved synthetic portfolios');
  await expect(otherPage.getByText(snapshot.name, { exact: true })).toHaveCount(0);
  const session = await (await otherPage.request.get('/api/v1/auth/session')).json();
  for (const path of [`/portfolios/${snapshot.portfolio_id}`, `/portfolios/${snapshot.portfolio_id}/workspace`, `/portfolios/${snapshot.portfolio_id}/packets/${snapshot.insights.packets[0].insight_id}`]) {
    const foreign = await otherPage.request.get(`/api/v1${path}`);
    const absent = await otherPage.request.get(`/api/v1${path.replace(snapshot.portfolio_id, '00000000-0000-0000-0000-000000000000')}`);
    expect(foreign.status()).toBe(404); expect(await foreign.json()).toEqual(await absent.json());
  }
  const reproduction = await otherPage.request.post(`/api/v1/portfolios/${snapshot.portfolio_id}/packets/${snapshot.insights.packets[0].insight_id}/reproduce`, {
    headers: { Origin: origin, 'X-Finweb-CSRF': session.csrf_token }, data: { expected_result_digest: snapshot.insights.result_digest },
  });
  expect(reproduction.status()).toBe(404);
  await otherPage.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  await expect(otherPage.getByRole('region', { name: '本地账户', exact: true })).toContainText(`已登录：${other.username}`);
  expect(await otherPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await otherPage.getByRole('button', { name: '退出登录', exact: true }).click();
  await otherPage.getByRole('button', { name: '登录', exact: true }).click();
  await expect(otherPage.getByLabel('密码', { exact: true })).toHaveAttribute('type', 'password');
  await expect(otherPage.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await otherContext.close();
});

test('guest state is not automatically migrated and a changed same-origin tab identity clears private UI', async ({ page, context }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByRole('button', { name: 'Use example quantities' }).click(); await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Analyze portfolio', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My synthetic portfolio', exact: true })).toBeVisible();
  // Registration is explicit and clears the old guest result. It creates no saved portfolio.
  const identity = testIdentity('tabs');
  const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click();
  await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  await account.getByLabel('Username', { exact: true }).fill(identity.username); await account.getByLabel('Password', { exact: true }).fill(identity.password);
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click();
  await expect(account).toContainText('No saved synthetic portfolios');
  await expect(page.getByRole('heading', { name: 'My synthetic portfolio', exact: true })).toHaveCount(0);
  const snapshot = await save(page, `Tab-private ${identity.username}`);
  const another = await context.newPage(); await another.goto('/');
  await expect(another.getByRole('region', { name: 'Local account', exact: true })).toContainText(identity.username);
  await another.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(account).toContainText('Guest access');
  await expect(page.getByRole('heading', { name: snapshot.name, exact: true })).toHaveCount(0);
  await expect(page.locator('.observation')).toHaveCount(0);
  await another.close();
});
