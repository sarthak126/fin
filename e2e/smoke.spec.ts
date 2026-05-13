import { test, expect } from '@playwright/test';

test('homepage loads and has title', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
    await expect(page.getByRole('heading', { name: /loan document review/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /book a pilot/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /book a demo/i }).first()).toBeVisible();
    await expect(page.getByRole('navigation').getByRole('link', { name: /features/i })).toBeVisible();
    await expect(page.getByRole('navigation').getByRole('link', { name: /security/i })).toBeVisible();
});
