import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', async route => {
    const p = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (p === '/api/auth/me') body = {id:'test', name:'Reviewer', role:'admin', email:'test@example.org', is_active:true};
    if (p === '/api/summary') body = {critical:0,warning:0,info:0,pending:0,runbooks:0};
    if (p === '/api/incidents' || p === '/api/runbooks') body = {items:[],total:0};
    if (p === '/api/jobs') body = [];
    if (p === '/api/runbooks/import') return route.fulfill({status:202,json:{id:'drop-test'}});
    await route.fulfill({json:body});
  });
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button',{name:'База знаний'}).click();
});

test('document can be dropped on the import section', async ({page}) => {
  const transfer = await page.evaluateHandle(() => {
    const dt = new DataTransfer(); dt.items.add(new File(['[]'],'review.json',{type:'application/json'})); return dt;
  });
  const request = page.waitForRequest(r => r.url().endsWith('/api/runbooks/import') && r.method() === 'POST');
  await page.locator('.knowledge-intro').dispatchEvent('dragenter',{dataTransfer:transfer});
  await expect(page.locator('.knowledge-intro')).toHaveClass(/drag-over/);
  await page.locator('.knowledge-intro').dispatchEvent('drop',{dataTransfer:transfer});
  await request;
  await expect(page.getByRole('status').filter({hasText:'Документ принят'})).toBeVisible();
  await expect(page.locator('.knowledge-intro')).not.toHaveClass(/drag-over/);
});

test('mouse focus has no persistent frame and selected text is blue', async ({page}) => {
  const field = page.getByRole('textbox',{name:'Поиск регламентов'});
  await field.click(); await field.fill('Проверка выделения'); await field.press('ControlOrMeta+a');
  expect(await field.evaluate((e: HTMLInputElement)=>e.selectionEnd! - e.selectionStart!)).toBe(18);
  expect(await field.evaluate(e=>getComputedStyle(e,'::selection').backgroundColor)).toBe('rgb(0, 95, 204)');
  expect(await field.evaluate(e=>getComputedStyle(e).outlineStyle)).toBe('none');
  expect(await page.locator('.knowledge-search .search').evaluate(e=>getComputedStyle(e).outlineStyle)).toBe('none');
  await field.press('Tab');
  await expect(page.getByRole('button',{name:'Найти',exact:true})).toBeFocused();
  expect(await page.getByRole('button',{name:'Найти',exact:true}).evaluate(e=>getComputedStyle(e).outlineStyle)).toBe('solid');
});
test('recommendation footer belongs to events, not profile or knowledge', async ({page}) => {
  await expect(page.locator('.page-footer')).toHaveCount(0);
  await page.getByRole('navigation').getByRole('button',{name:'Мой профиль'}).click();
  await expect(page.locator('.page-footer')).toHaveCount(0);
  await page.getByRole('navigation').getByRole('button',{name:/^События/}).click();
  await expect(page.locator('.page-footer')).toContainText('Только рекомендации');
});
