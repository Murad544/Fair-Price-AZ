import { test, expect } from '@playwright/test';

test('manual estimate matches the running FastAPI model', async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.API_SMOKE,
    'Set API_SMOKE=1 with FastAPI running to verify real integration',
  );
  const phone = {
    brand: 'Apple',
    model: 'iPhone 13',
    condition: 'used',
    storage_gb: 128,
    actual_price_azn: 650,
  };
  const response = await request.post('/api/predict', { data: phone });
  expect(response.ok()).toBeTruthy();
  const prediction = await response.json();
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto('/');
  await page.screenshot({
    path: 'test-results/desktop-link.png',
    fullPage: true,
  });
  await page.getByRole('tab', { name: 'Enter details' }).click();
  await page.getByLabel('Model', { exact: true }).fill('iPhone 13');
  await page.getByLabel('Storage').selectOption('128');
  await page.getByLabel('Asking price').fill('650');
  await page.getByRole('button', { name: 'Get price estimate' }).click();
  const price = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
  }).format(prediction.predicted_price_azn);
  await expect(page.locator('.price-estimate>div')).toContainText(price);
  await expect(page.getByText('Seller’s asking price')).toBeVisible();
  await page.screenshot({
    path: 'test-results/desktop-result.png',
    fullPage: true,
  });
});
