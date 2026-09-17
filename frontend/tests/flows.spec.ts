import { test, expect } from '@playwright/test';

const result = {
  predicted_price_azn: 500,
  currency: 'AZN',
  condition: 'used',
  actual_price_azn: 650,
  difference_pct: 30,
  verdict: 'Overpriced by 30%',
  model_version: 'test',
};

test('manual flow sends optional fields correctly and shows comparison', async ({
  page,
}) => {
  let payload: Record<string, unknown> = {};
  await page.route('**/api/predict', async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({ json: result });
  });
  await page.goto('/');
  await page.getByRole('tab', { name: 'Enter details' }).click();
  await page.getByLabel('Model', { exact: true }).fill('iPhone 13');
  await page.getByLabel('Storage').selectOption('128');
  await page.getByLabel('Asking price').fill('650');
  await page.getByRole('button', { name: 'Get price estimate' }).click();
  await expect(page.getByText('Priced above the estimate')).toBeVisible();
  expect(payload).toEqual({
    brand: 'Apple',
    model: 'iPhone 13',
    condition: 'used',
    storage_gb: 128,
    actual_price_azn: 650,
  });
  await expect(page.getByText('30.0% above the estimate')).toBeVisible();
  await page.getByLabel('Model', { exact: true }).fill('iPhone 14');
  await expect(page.getByText('Priced above the estimate')).not.toBeVisible();
});

test('link flow removes tracking, displays parsed features and verdict', async ({
  page,
}) => {
  let payload: unknown;
  await page.route('**/api/predict-from-url', async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({
      json: {
        ...result,
        features: {
          brand: 'Apple',
          model: 'iPhone 13',
          condition: 'used',
          storage_gb: 128,
        },
        listing_id: '123',
        url: 'https://tap.az/elanlar/elektronika/telefonlar/123',
      },
    });
  });
  await page.goto('/');
  await page
    .getByLabel('Tap.az listing link')
    .fill(
      'https://tap.az/elanlar/elektronika/telefonlar/123/?utm_source=share',
    );
  await page.getByRole('button', { name: 'Check this price' }).click();
  await expect(page.getByRole('heading', { name: 'iPhone 13' })).toBeVisible();
  expect(payload).toEqual({
    url: 'https://tap.az/elanlar/elektronika/telefonlar/123',
  });
  await expect(
    page.getByRole('link', { name: 'View original listing' }),
  ).toHaveAttribute(
    'href',
    'https://tap.az/elanlar/elektronika/telefonlar/123',
  );
});

test('invalid URL is rejected before a request', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/**', async (route) => {
    calls++;
    await route.abort();
  });
  await page.goto('/');
  await page
    .getByLabel('Tap.az listing link')
    .fill('https://tap.az.evil.com/elanlar/elektronika/telefonlar/123');
  await page.getByRole('button', { name: 'Check this price' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Use a phone listing from tap.az',
  );
  expect(calls).toBe(0);
});

test('upstream error offers manual fallback', async ({ page }) => {
  await page.route('**/api/predict-from-url', (route) =>
    route.fulfill({ status: 502, json: { detail: 'Could not reach Tap.az' } }),
  );
  await page.goto('/');
  await page
    .getByLabel('Tap.az listing link')
    .fill('https://tap.az/elanlar/elektronika/telefonlar/123');
  await page.getByRole('button', { name: 'Check this price' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'We couldn’t read Tap.az',
  );
  await page.getByRole('button', { name: 'Enter details instead' }).click();
  await expect(
    page.getByRole('heading', { name: 'Tell us about the phone' }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});

test('new-phone estimate works without an asking price', async ({ page }) => {
  let payload: Record<string, unknown> = {};
  await page.route('**/api/predict', async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({
      json: {
        ...result,
        condition: 'new',
        actual_price_azn: null,
        difference_pct: null,
        verdict: null,
      },
    });
  });
  await page.goto('/');
  await page.getByRole('tab', { name: 'Enter details' }).click();
  await page.getByLabel('Model', { exact: true }).fill('iPhone 13');
  await page.getByRole('radio', { name: /New/ }).check();
  await page.getByRole('button', { name: 'Get price estimate' }).click();
  await expect(page.getByText('Have an asking price?')).toBeVisible();
  expect(payload).toEqual({
    brand: 'Apple',
    model: 'iPhone 13',
    condition: 'new',
  });
  await expect(page.getByText('Seller’s asking price')).not.toBeVisible();
});

test('switching modes cancels pending check and ignores late response', async ({
  page,
}) => {
  let release: (() => void) | undefined;
  await page.route('**/api/predict-from-url', async (route) => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route
      .fulfill({
        json: {
          ...result,
          features: { brand: 'Apple', model: 'OLD RESULT', condition: 'used' },
        },
      })
      .catch(() => {});
  });
  await page.goto('/');
  await page
    .getByLabel('Tap.az listing link')
    .fill('https://tap.az/elanlar/elektronika/telefonlar/123');
  await page.getByRole('button', { name: 'Check this price' }).click();
  await expect(page.getByText('Taking a closer look')).toBeVisible();
  await expect.poll(() => !!release).toBeTruthy();
  await page.getByRole('tab', { name: 'Enter details' }).click();
  release!();
  await expect(
    page.getByRole('button', { name: 'Get price estimate' }),
  ).toBeEnabled();
  await expect(
    page.getByText('A little clarity before you buy.'),
  ).toBeVisible();
  await expect(page.getByText('OLD RESULT')).not.toBeVisible();
});

test('mobile layout fits viewport and keyboard tabs switch modes', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(
    page.getByRole('button', { name: 'Check this price' }),
  ).toBeVisible();
  const tab = page.getByRole('tab', { name: 'Paste a link' });
  await tab.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Enter details' })).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });
});
