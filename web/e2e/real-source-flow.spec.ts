import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function artifact(name: string, bytes: Buffer) {
  const directory = process.env.FINWEB_REAL_SOURCE_ARTIFACT_DIR;
  if (directory) { await mkdir(directory, { recursive: true }); await writeFile(join(directory, name), bytes, { flag: 'wx' }); }
}

test('E1 signed-in explicit metadata GET → blocked dual origins → no financial requests → bilingual keyboard/narrow recovery and clearing', async ({ page }) => {
  const readinessPath = '/api/v1/real-source-contexts'; const requests: { method: string; path: string }[] = [];
  page.on('request', (request) => { requests.push({ method: request.method(), path: new URL(request.url()).pathname }); });
  await page.goto('/portfolio'); await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled();
  expect(requests.filter((request) => request.path === readinessPath)).toHaveLength(0); await expect(page.getByRole('button', { name: 'Real-source readiness', exact: true })).toHaveCount(0);
  const account = page.getByRole('region', { name: 'Local account', exact: true }); await account.getByRole('button', { name: 'Sign in', exact: true }).click(); await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  const marker = `${Date.now()}_${test.info().workerIndex}`; await account.getByLabel('Username', { exact: true }).fill(`cp7e_test_${marker}`); await account.getByLabel('Password', { exact: true }).fill(`cp7e-disposable-only-${marker}`);
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click(); await expect(page.getByRole('button', { name: 'Use example quantities', exact: true })).toBeEnabled();
  expect(requests.filter((request) => request.path === readinessPath)).toHaveLength(0);
  const entered = page.waitForResponse((response) => new URL(response.url()).pathname === readinessPath); const entry = page.getByRole('button', { name: 'Real-source readiness', exact: true }); await entry.focus(); await page.keyboard.press('Enter');
  const initialResponse = await entered; expect(initialResponse.status()).toBe(200); const issued = await initialResponse.json(); expect(issued.state).toBe('BLOCKED'); expect(issued.approved_context_count).toBe(0); expect(issued.capabilities.create).toBe(false);
  const panel = page.getByRole('region', { name: 'Real historical source readiness', exact: true }); await expect(panel.getByRole('heading', { level: 1 })).toBeFocused(); await expect(panel.locator('.real-source-actions button:disabled')).toHaveCount(3); await expect(panel.locator('input, form, .metric-value')).toHaveCount(0);
  const blockedStart = requests.length;
  for (const language of ['en', 'zh-CN']) {
    await page.locator('.language-control select').selectOption(language);
    for (const depth of language === 'en' ? ['Quick', 'Simple', 'Professional'] : ['速览', '简明', '专业']) {
      await page.getByRole('button', { name: depth, exact: true }).click(); await expect(page.locator('.real-source-actions button:disabled')).toHaveCount(3); await expect(page.locator('.real-source-origins p')).toHaveCount(2);
      await expect(page.locator('.real-source-readiness')).toContainText(language === 'en' ? 'nothing created' : '尚未创建');
      for (const code of issued.blockers) await expect(page.locator('.real-source-readiness')).toContainText(code);
    }
  }
  expect(requests.slice(blockedStart).filter((request) => request.method !== 'GET' || /guest-portfolios|\/portfolios|analytics/.test(request.path))).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 }); await page.locator('#real-source-readiness-title').scrollIntoViewIfNeeded(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); await artifact('e1-blocked-zh-390.png', await page.screenshot());
  await page.locator('.language-control select').selectOption('en'); await page.setViewportSize({ width: 1280, height: 900 }); await artifact('e1-blocked-en.png', await page.locator('.real-source-readiness').screenshot()); await artifact('e1-public-readiness.json', Buffer.from(JSON.stringify(issued, null, 2)));
  // Explicit transport failure injection, not a fabricated source or financial response.
  await page.route(`**${readinessPath}`, (route) => route.abort('failed')); await page.getByRole('button', { name: 'Check readiness again', exact: true }).click(); await expect(panel.getByRole('alert')).toContainText('NETWORK_ERROR'); await expect(panel).not.toContainText('No source context is configured');
  await page.unroute(`**${readinessPath}`); const recovered = page.waitForResponse((response) => new URL(response.url()).pathname === readinessPath); await page.getByRole('button', { name: 'Check readiness again', exact: true }).focus(); await page.keyboard.press('Enter'); expect((await recovered).status()).toBe(200); await expect(panel.getByRole('alert')).toHaveCount(0); await expect(panel).toContainText('Source not ready');
  await page.getByRole('link', { name: 'Overview', exact: true }).click(); await expect(page.locator('.real-source-readiness')).toHaveCount(0); await expect(page.locator('.synthetic-banner')).toContainText('SYNTHETIC DEVELOPMENT DATA'); const afterLeaving = requests.filter((request) => request.path === readinessPath).length;
  await page.getByRole('link', { name: 'Portfolio', exact: true }).click(); await expect(page.getByRole('button', { name: 'Use example quantities', exact: true })).toBeEnabled(); expect(requests.filter((request) => request.path === readinessPath)).toHaveLength(afterLeaving);
  const reopened = page.waitForResponse((response) => new URL(response.url()).pathname === readinessPath); await page.getByRole('button', { name: 'Real-source readiness', exact: true }).click(); expect((await reopened).status()).toBe(200);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await expect(page.locator('.real-source-readiness')).toHaveCount(0); await expect(page.getByRole('button', { name: 'Real-source readiness', exact: true })).toHaveCount(0);
  expect(requests.some((request) => request.method === 'POST' && request.path === '/api/v1/real-portfolios')).toBe(false); expect(requests.filter((request) => request.path === readinessPath).every((request) => request.method === 'GET')).toBe(true);
});
