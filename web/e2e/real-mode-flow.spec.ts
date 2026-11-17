import { expect, test } from '@playwright/test';
import { REAL_SENTENCES } from './real-mode-phrases';

// F1 R7: the real-mode screen over a TEST install (invented data). Run recipe: web/README.md "Real mode" and the report of the R7 increment.
//   env: FINWEB_WEB_BASE_URL=http://127.0.0.1:5175   (the real-mode Vite profile; the page is /real.html)
//        FINWEB_R7_CONTEXT_ID, FINWEB_R7_RELEASE_ID, FINWEB_R7_LISTING_ID, FINWEB_R7_AS_OF   (printed by tests/product/real_dev_env.py)
// SIGN-UP LIMIT: this spec registers 2 accounts on the account store (10 per peer per 15 minutes). The limit is an authentication control and is not
// bypassed. Run the spec once per `real_dev_env.py` start.
const env = (name: string) => { const value = process.env[name]; if (!value) throw new Error(`${name} is required (see tests/product/real_dev_env.py)`); return value; };
const PAGE = '/real.html';
const ALLOWED = /^\/api\/(v1\/auth\/(session|register|login|logout)|real\/v1\/roots(\/[0-9a-f-]{36}\/operations\/[0-9a-f-]{36}(\/reproduce)?)?)$/;
// The real-source wording that must never render over TEST data: the real origin labels (EN, from persistence/real_labels.py; zh, from
// real-mode-i18n.ts) and distinctive PHRASES of the 7.4 claim text (EN and zh, from real-mode-claims.ts). Bare status tokens such as UNVERIFIABLE or
// SINGLE_SOURCE are NOT in this list: they occur legitimately in the stored engine JSON (its open_items notes), which is not 7.4 text.
// (The list lives in real-mode-phrases.ts; a vitest checks it against every non-claim client string.)
/** The text of the app with the stored-JSON block (`.issued-result`, inside the closed <details>) removed. The stored engine document is shown as stored; it is
 * checked separately below, for the same phrases. */
const textWithoutStoredJson = (page: import('@playwright/test').Page) => page.evaluate(() => {
  const copy = document.querySelector('.real-mode-app')!.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('.issued-result').forEach((node) => node.remove());
  return copy.textContent ?? '';
});
const storedJson = (page: import('@playwright/test').Page) => page.locator('.issued-result').evaluateAll((nodes) => nodes.map((n) => n.textContent ?? '').join('\n'));

async function signUp(page: import('@playwright/test').Page, username: string) {
  await page.goto(PAGE);
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled();
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(`invented-disposable-${username}`);
  await page.getByRole('button', { name: 'Create local account', exact: true }).click();
  await expect(page.getByText(username, { exact: true })).toBeVisible();
}

test('real mode over TEST data: create, mark shown, no real sentence, reproduce, list, both languages and depths, isolation, closed routes', async ({ page, browser }) => {
  const requests: { method: string; path: string }[] = [];
  page.on('request', (request) => { const url = new URL(request.url()); if (url.pathname.startsWith('/api/')) requests.push({ method: request.method(), path: url.pathname }); });
  const marker = `${Date.now()}_${test.info().workerIndex}`;
  await signUp(page, `r7_alice_${marker}`);
  await expect(page.getByText('No root has been created yet.')).toBeVisible();

  const create = page.getByRole('region', { name: 'Create a root', exact: true });
  await create.getByLabel('Context ID', { exact: true }).fill(env('FINWEB_R7_CONTEXT_ID'));
  await create.getByLabel('Release ID', { exact: true }).fill(env('FINWEB_R7_RELEASE_ID'));
  await create.getByLabel('Listing ID', { exact: true }).fill(env('FINWEB_R7_LISTING_ID'));
  await create.getByLabel('Name', { exact: true }).fill('invented browser root');
  await create.getByLabel('As-of date (YYYY-MM-DD)', { exact: true }).fill(env('FINWEB_R7_AS_OF'));
  await create.getByLabel('Quantity', { exact: true }).fill('2');
  await create.getByLabel('Opening cash', { exact: true }).fill('20');
  const submit = create.getByRole('button', { name: 'Create', exact: true });
  await expect(submit).toBeDisabled();                                      // the acknowledgement comes first
  await create.getByLabel(/I understand the ledger is constructed/).check();
  const created = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/real/v1/roots' && response.request().method() === 'POST');
  await submit.click();
  const response = await created;
  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.origin.market_origin).toBe('SYNTHETIC_TEST');

  const detail = page.locator('.real-root-detail');
  await expect(detail).toBeVisible();
  await expect(detail.locator('.origin-banner.test-origin')).toContainText('INVENTED TEST DATA');
  await expect(detail.locator('.invented-data-mark')).toHaveText('Invented test data; no claim about any real source.');
  await expect(page.locator('.real-mode-app .real-origin')).toHaveCount(0);
  await expect(page.locator('.real-mode-app [data-claim-id]')).toHaveCount(0);
  // PD-0079/PD-0080: the key figures over TEST data carry the invented-data marking, and the raw document is still there, labelled.
  // A TEST create stores the CP5 DIVERSIFICATION result, which holds no `portfolio_value` metric (see tests/product/test_postgres_real_mode_figures.py). Over TEST
  // data the screen therefore shows ONE statement that this document stores none of the listed figures, in place of four "not in this result" lines (which could be read as
  // zeros); it lists no figure and shows no number. The statement is chosen by the origin and by the document holding none of the listed figures.
  const figures = page.locator('.real-root-detail .key-figures');
  await expect(figures).toBeVisible();
  await expect(figures.locator('.figures-mark')).toHaveText('Invented test data; no claim about any real source.');
  const metrics = body.result.metrics as Record<string, unknown>[];
  expect(metrics.some((m) => m.metric_id === 'portfolio_value'), 'the API result holds no NAV metric').toBe(false);
  await expect(figures.locator('.figures-none')).toHaveCount(1);
  await expect(figures.locator('.figures-none')).toContainText('stores none of the listed figures');
  await expect(figures.locator('[data-figure-id]')).toHaveCount(0);
  await expect(figures.locator('.figure-absent')).toHaveCount(0);
  await expect(figures.locator('.figure-value')).toHaveCount(0);
  await expect(figures.locator('.figure-no-nav')).toHaveCount(0);
  await expect(page.locator('.real-root-detail .raw-note')).toContainText('exactly as issued');
  await expect(page.locator('.real-root-detail details > summary')).toHaveText('Issued result, as stored');
  await expect(page.locator('.issued-result')).toHaveCount(1);
  await expect(page.locator('h1.screen-title')).toHaveText('Stored results');          // the permanent title states no origin
  expect(await page.title()).toBe('Meridian — Stored results');
  // Structural checks above cover the whole app. The text checks: the app without the stored-JSON block, and the stored-JSON block on its own.
  const shown = await textWithoutStoredJson(page);
  const stored = await storedJson(page);
  expect(stored.length).toBeGreaterThan(0);
  for (const sentence of REAL_SENTENCES) {
    expect(shown, `app text: ${sentence}`).not.toContain(sentence);
    expect(stored, `stored JSON: ${sentence}`).not.toContain(sentence);
  }

  for (const [language, label, banner] of [['zh-CN', '简体中文', '测试用虚构数据'], ['en', 'English', 'INVENTED TEST DATA']] as const) {
    await page.locator('.language-control select').selectOption(language);
    for (const depth of language === 'en' ? ['Quick', 'Simple', 'Professional'] : ['速览', '简明', '专业']) {
      await page.getByRole('button', { name: depth, exact: true }).click();
      await expect(page.getByRole('button', { name: depth, exact: true })).toHaveAttribute('aria-pressed', 'true');
      await expect(detail.locator('.origin-banner.test-origin')).toContainText(banner);
      await expect(figures.locator('.figures-mark')).toHaveText(language === 'en' ? 'Invented test data; no claim about any real source.' : '测试用虚构数据；不对任何真实来源作出声明。');
      await expect(page.locator('.real-root-detail .raw-note')).toContainText(language === 'en' ? 'exactly as issued' : '原样签发');
      await expect(figures.locator('.figures-none')).toContainText(language === 'en' ? 'stores none of the listed figures' : '本文档未存储所列的任何数字');
      await expect(figures.locator('.figure-absent')).toHaveCount(0);
      await expect(page.locator('.real-mode-app [data-claim-id]')).toHaveCount(0);
      await expect(page.locator('.real-mode-app .real-origin')).toHaveCount(0);
      const shownNow = await textWithoutStoredJson(page);
      for (const sentence of REAL_SENTENCES) expect(shownNow, `${language}/${depth}: ${sentence}`).not.toContain(sentence);
    }
    expect(label).toBeTruthy();
  }

  await page.getByRole('button', { name: 'Reproduce', exact: true }).click();
  await expect(page.locator('.reproduction')).toContainText('REPRODUCED');

  await page.getByRole('button', { name: 'Refresh list', exact: true }).click();
  await expect(page.locator(`.real-root-list [data-root-id="${body.root_id}"]`)).toBeVisible();
  await expect(page.locator('.real-root-list .origin-tag')).toHaveAttribute('data-origin-kind', 'INVENTED_TEST_DATA');

  // Create again with the same form: the client mints a NEW operation id for every new Create (a replay is only the "repeat" of an unknown outcome, which
  // keeps the stored body), so this is a second command and a second root for the same context, not a replay. The replay rule itself is covered by
  // tests/product (test_a_replayed_create_is_a_200, the PostgreSQL module) and by the vitest R7-REPLAY.
  const again = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/real/v1/roots' && r.request().method() === 'POST');
  await submit.click();
  const second_ = await again;
  expect(second_.status()).toBe(201);
  const secondBody = await second_.json();
  expect(secondBody.replayed).toBe(false);
  expect(secondBody.operation_id).not.toBe(body.operation_id);
  expect(secondBody.root_id).not.toBe(body.root_id);
  await expect(detail.locator('.replayed')).toHaveCount(0);

  // Every closed route stays closed in the same app.
  const closed = await page.request.get('/api/v1/portfolios');
  expect(closed.status()).toBe(503);
  expect((await closed.json()).error.code).toBe('REAL_MODE_ROUTE_CLOSED');

  // A second user: the generic not-found for the first user's root, and an empty list.
  const other = await browser.newContext({ baseURL: process.env.FINWEB_WEB_BASE_URL ?? 'http://127.0.0.1:5175' });
  const second = await other.newPage();
  await signUp(second, `r7_bob_${marker}`);
  await second.getByRole('button', { name: 'Refresh list', exact: true }).click();
  await expect(second.getByText('No root has been created yet.')).toBeVisible();
  const reading = second.getByRole('region', { name: 'Read a stored result', exact: true });
  await reading.getByLabel('Root', { exact: true }).fill(body.root_id);
  await reading.getByLabel('Operation ID', { exact: true }).fill(body.operation_id);
  await reading.getByRole('button', { name: 'Read', exact: true }).click();
  await expect(second.getByRole('alert')).toContainText('RW_NOT_FOUND');
  await expect(second.locator('.real-root-detail')).toHaveCount(0);
  await other.close();

  // Nothing but the auth routes and the four scoped routes was requested by the page.
  expect(requests.length).toBeGreaterThan(0);
  for (const request of requests) expect(request.path, `${request.method} ${request.path}`).toMatch(ALLOWED);
});
