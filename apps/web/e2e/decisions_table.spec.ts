import { test, expect } from '@playwright/test';

test.describe('AI Decisions Ledger Layout & Responsiveness', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');
  });

  test('1. Desktop 1440px: All 9 columns fit cleanly with zero page-level horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // Verify page title
    await expect(page.locator('h1')).toContainText('AI Decisions Ledger');

    // Verify all 9 headers are visible
    const headers = [
      'Decision ID',
      'Opportunity ID',
      'Buyer Context',
      'Strategy',
      'Mode',
      'Proposed Price',
      'Execution Status',
      'Outcome',
      'Created',
    ];
    for (const h of headers) {
      await expect(page.locator(`th:has-text("${h}")`)).toBeVisible();
    }

    // Verify NO page-level horizontal scrollbar
    const isPageOverflowing = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(isPageOverflowing).toBe(false);

    // Verify Proposed Price is visible and formatted
    await expect(page.locator('tbody').locator('text=/₹[\\d,]+/').first()).toBeVisible();

    // Verify Execution status badge is visible in table body
    await expect(page.locator('tbody').getByText('PENDING_EXECUTION_GATE').first()).toBeVisible();

    // Verify Outcome status badge is visible in table body
    await expect(page.locator('tbody').getByText('PAID (Test Mode)').first()).toBeVisible();
  });

  test('2. Long Identifier Truncation & Accessible Tooltips', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // Buyer context should have truncate class and full title attribute
    const buyerContextCell = page.locator('tbody span[title^="bck_"]').first();
    await expect(buyerContextCell).toBeVisible();

    const titleAttr = await buyerContextCell.getAttribute('title');
    expect(titleAttr).toContain('bck_');
    expect(titleAttr?.length).toBeGreaterThan(30);

    // Opportunity ID should also be truncated with title
    const oppCell = page.locator('tbody span[title^="opp_"]').first();
    await expect(oppCell).toBeVisible();
    expect(await oppCell.getAttribute('title')).toContain('opp_');
  });

  test('3. Responsive Viewport Check: 1280px, 1024px, and Mobile 375px', async ({ page }) => {
    const viewports = [
      { width: 1280, height: 800 },
      { width: 1024, height: 768 },
      { width: 375, height: 812 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);

      // Verify NO page-level horizontal overflow
      const isPageOverflowing = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth;
      });
      expect(isPageOverflowing).toBe(false);

      // Verify table scroll container exists
      const scrollContainer = page.locator('.overflow-x-auto');
      await expect(scrollContainer).toBeVisible();

      // Decision ID remains sticky on the left
      const stickyCell = page.locator('td.sticky').first();
      await expect(stickyCell).toBeVisible();
    }
  });

  test('4. Row Click Opens Decision Detail Drawer', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // Click on the first row
    const firstRow = page.locator('tbody tr[role="button"]').first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();

    // Decision detail drawer opens
    const drawerTitle = page.locator('text=Autonomous Decision Inspection');
    await expect(drawerTitle).toBeVisible({ timeout: 5000 });

    // Close the drawer
    const closeBtn = page.locator('button[aria-label="Close drawer"]').first();
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(drawerTitle).not.toBeVisible();
  });

  test('5. Keyboard Navigation on Table Rows', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const firstRow = page.locator('tbody tr[role="button"]').first();
    await firstRow.focus();

    // Press Enter to open drawer
    await page.keyboard.press('Enter');
    const drawerTitle = page.locator('text=Autonomous Decision Inspection');
    await expect(drawerTitle).toBeVisible({ timeout: 5000 });

    // Press Escape to close drawer
    await page.keyboard.press('Escape');
    await expect(drawerTitle).not.toBeVisible();
  });

  test('6. Filters and Pagination Controls', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // Filter select elements are visible and interactable
    const modeSelect = page.locator('select').first();
    await expect(modeSelect).toBeVisible();
    await modeSelect.selectOption('EXPLOIT');

    // Page updates table with exploit rows
    await expect(page.locator('tbody').getByText('EXPLOIT').first()).toBeVisible();

    // Reset filter
    await modeSelect.selectOption('ALL');
  });
});
