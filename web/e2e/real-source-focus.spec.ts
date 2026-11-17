import { expect, test, type Page, type Route } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const readinessPath = '/api/v1/real-source-contexts';
async function capture(page: Page, name: string) {
  const directory = process.env.FINWEB_REAL_SOURCE_FOCUS_ARTIFACT_DIR;
  if (directory) { await mkdir(directory, { recursive: true }); await writeFile(join(directory, name), await page.screenshot(), { flag: 'wx' }); }
}
async function openReadiness(page: Page) {
  const response = page.waitForResponse((item) => new URL(item.url()).pathname === readinessPath);
  await page.getByRole('button', { name: /^(Real-source readiness|真实来源就绪状态)$/ }).click(); expect((await response).status()).toBe(200);
  await expect(page.locator('#real-source-readiness-title')).toBeFocused();
}
async function keyboardRetry(page: Page) {
  const retry = page.getByRole('button', { name: /^(Check readiness again|重新检查就绪状态)$/ });
  await retry.focus(); await page.keyboard.press('Enter');
}

test('readiness keyboard retry restores updated heading for success/error and stale requests never steal focus after navigation/logout', async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto('/portfolio'); const account = page.getByRole('region', { name: 'Local account', exact: true });
  await account.getByRole('button', { name: 'Sign in', exact: true }).click(); await account.getByRole('button', { name: 'Create local account', exact: true }).click();
  const marker = Date.now().toString(36); await account.getByLabel('Username', { exact: true }).fill(`cp7e_focus_${marker}`); await account.getByLabel('Password', { exact: true }).fill(`cp7e-focus-disposable-${marker}`);
  await account.locator('form').getByRole('button', { name: 'Create local account', exact: true }).click(); await expect(page.getByRole('button', { name: 'Use example quantities', exact: true })).toBeEnabled();
  await openReadiness(page);
  for (const language of ['en', 'zh-CN']) {
    await page.locator('.language-control select').selectOption(language);
    const response = page.waitForResponse((item) => new URL(item.url()).pathname === readinessPath); await keyboardRetry(page); expect((await response).status()).toBe(200);
    await expect(page.locator('#real-source-readiness-title')).toBeFocused(); await expect(page.locator('.real-source-actions button:disabled')).toHaveCount(3);
    await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: /^(Check readiness again|重新检查就绪状态)$/ })).toBeFocused(); await capture(page, `focus-retry-${language}.png`);
  }
  // Transport-only fault injection exercises the same keyboard recovery from an error.
  await page.locator('.language-control select').selectOption('en'); await page.route(`**${readinessPath}`, (route) => route.abort('failed')); await keyboardRetry(page);
  await expect(page.locator('.real-source-readiness [role="alert"]')).toContainText('NETWORK_ERROR'); await expect(page.locator('#real-source-readiness-title')).toBeFocused();
  await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: 'Check readiness again', exact: true })).toBeFocused(); await page.unroute(`**${readinessPath}`);
  const recovered = page.waitForResponse((item) => new URL(item.url()).pathname === readinessPath); await page.keyboard.press('Enter'); expect((await recovered).status()).toBe(200); await expect(page.locator('#real-source-readiness-title')).toBeFocused();

  // Hold a genuine blocked response, then leave the view before it can publish.
  let release!: () => void; let computed!: () => void; let delivered!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; }); const ready = new Promise<void>((resolve) => { computed = resolve; }); const completed = new Promise<void>((resolve) => { delivered = resolve; });
  const delayed = async (route: Route) => { const response = await route.fetch(); expect(response.status()).toBe(200); computed(); await gate; await route.fulfill({ response }); delivered(); };
  await page.route(`**${readinessPath}`, delayed); await keyboardRetry(page); await ready;
  const overview = page.getByRole('link', { name: 'Overview', exact: true }); await overview.focus(); await page.keyboard.press('Enter'); await expect(page.locator('.real-source-readiness')).toHaveCount(0);
  const focusedAfterNavigation = await page.evaluate(() => ({ tag: document.activeElement?.tagName, id: document.activeElement?.id, href: document.activeElement?.getAttribute('href') }));
  release(); await completed; await page.unroute(`**${readinessPath}`, delayed); expect(await page.evaluate(() => ({ tag: document.activeElement?.tagName, id: document.activeElement?.id, href: document.activeElement?.getAttribute('href') }))).toEqual(focusedAfterNavigation);
  await expect(page.locator('#real-source-readiness-title')).toHaveCount(0); await openReadiness(page);

  // The old request expires after actual logout. Its real 401 must not refocus or restore the removed view.
  let releaseExpired!: () => void; let intercepted!: () => void; let expiredDelivered!: () => void; let expiredStatus: number | undefined;
  const expiryGate = new Promise<void>((resolve) => { releaseExpired = resolve; }); const captured = new Promise<void>((resolve) => { intercepted = resolve; }); const expiryCompleted = new Promise<void>((resolve) => { expiredDelivered = resolve; });
  const expired = async (route: Route) => { intercepted(); await expiryGate; const response = await route.fetch(); expiredStatus = response.status(); await route.fulfill({ response }); expiredDelivered(); };
  await page.route(`**${readinessPath}`, expired); await keyboardRetry(page); await captured;
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled(); await expect(page.locator('.real-source-readiness')).toHaveCount(0);
  const signIn = page.getByRole('button', { name: 'Sign in', exact: true }); await signIn.focus(); releaseExpired(); await expiryCompleted; await page.unroute(`**${readinessPath}`, expired);
  expect(expiredStatus).toBe(401); await expect(signIn).toBeFocused(); await expect(page.locator('#real-source-readiness-title')).toHaveCount(0);
});
