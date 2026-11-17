import { expect, test } from '@playwright/test';

test('manual guest → issued facts → scoped Proof Packet → actual replay; bilingual and narrow layout', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByRole('button', { name: 'Use example quantities' }).click();
  await page.getByRole('checkbox').check();
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/guest-portfolios') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analyze portfolio' }).click();
  const http = await created;
  expect(http.status()).toBe(201);
  const snapshot = await http.json();
  await expect(page.getByRole('heading', { name: 'My synthetic portfolio', exact: true })).toBeVisible();
  const total = snapshot.valuation.metrics.find((m: { metric_id: string; view: string }) => m.metric_id === 'portfolio_value' && m.view === 'REPORTING');
  await expect(page.locator('.metric-grid .metric-card').first().locator('.metric-value > span').first()).toHaveText(total.value);
  const observations = page.locator('.observation');
  expect(await observations.count()).toBe(snapshot.insights.packets.length);
  await expect(observations.filter({ hasText: 'Scope: Cash' }).first()).toBeVisible();
  await expect(observations.filter({ hasText: 'Scope: Equity' }).first()).toBeVisible();

  const opener = observations.first().getByRole('button', { name: 'View evidence' });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Evidence & methodology' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(snapshot.insights.packets[0].insight_id, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Reproduce recorded result' }).click();
  await expect(dialog.locator('.reproduction-result')).toContainText('Reproduced');
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();

  await page.getByRole('button', { name: 'Professional', exact: true }).click();
  await expect(page.locator('.metric-card').first()).toContainText('performance.valuation/cp3b');
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh-CN');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.getByRole('link', { name: '总览', exact: true })).toBeVisible();
  await expect(observations.filter({ hasText: '范围: 现金' }).first()).toBeVisible();
  const zhOpener = observations.first().getByRole('button', { name: '查看证据' });
  await zhOpener.click();
  const zhDialog = page.getByRole('dialog', { name: '证据与方法' });
  await expect(zhDialog).toContainText('现金和应收项目使用零本币利息');
  await zhDialog.getByRole('button', { name: '复现已记录结果' }).click();
  await expect(zhDialog.locator('.reproduction-result')).toContainText('已复现');
  await zhDialog.getByRole('button', { name: '关闭证据' }).click();
  await expect(zhOpener).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('link', { name: '投资组合', exact: true }).click();
  await expect(page.getByRole('heading', { name: '持仓与活动' })).toBeVisible();
  await expect(page.getByRole('region', { name: '持仓与活动' })).toBeVisible();
  await page.getByRole('link', { name: '情景实验室' }).click();
  await expect(page.getByRole('heading', { name: '情景实验室暂未开放' })).toBeVisible();
});

test('cash-only and mixed cash/security retain distinct engine-issued scope and states', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Use example quantities' })).toBeEnabled();
  await page.getByLabel('Portfolio name', { exact: true }).fill('Cash only');
  await page.getByLabel('Opening cash (USD)', { exact: true }).fill('1');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Analyze portfolio' }).click();
  await expect(page.getByRole('heading', { name: 'Cash only', exact: true })).toBeVisible();
  const securityCard = page.locator('.metric-card').filter({ hasText: 'Largest security weight' });
  await expect(securityCard).toContainText('Insufficient data');
  await expect(securityCard.locator('.metric-value')).toHaveCount(0);
  await expect(securityCard).toContainText('This portfolio has no security positions.');
  await page.getByRole('link', { name: 'Analytics', exact: true }).click();
  await page.getByRole('button', { name: 'Professional', exact: true }).click();
  const volatilityCard = page.locator('.metric-card').filter({ hasText: 'Modeled volatility' });
  await expect(volatilityCard.locator('.state-badge')).toHaveText('Available');
  await expect(volatilityCard.locator('.metric-value > span').first()).toHaveText('0');
  await expect(volatilityCard).toContainText('Squared-value witness');
  await expect(volatilityCard).toContainText('0/1');
  await expect(volatilityCard).not.toContainText('Insufficient data');
  await page.getByRole('button', { name: 'New guest portfolio' }).click();
  await page.getByLabel('Portfolio name', { exact: true }).fill('Cash is largest');
  await page.locator('#quantity-SYN-A').fill('1');
  await page.getByLabel('Opening cash (USD)', { exact: true }).fill('900');
  await page.getByRole('checkbox').check();
  const result = page.waitForResponse((response) => response.url().endsWith('/api/v1/guest-portfolios') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analyze portfolio' }).click();
  const snapshot = await (await result).json();
  await page.getByRole('link', { name: 'Analytics', exact: true }).click();
  for (const id of ['largest_position_weight', 'largest_security_weight']) {
    const metric = snapshot.diversification.metrics.find((m: { metric_id: string }) => m.metric_id === id);
    const label = id === 'largest_position_weight' ? 'Largest capital position' : 'Largest security weight';
    await expect(page.locator('.metric-card').filter({ hasText: label }).locator('.metric-value > span').first()).toHaveText(metric.value);
  }
});
