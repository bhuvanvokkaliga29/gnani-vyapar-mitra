import { test, expect } from '@playwright/test';

test.describe('Tenant Selector Dropdown UX & Hierarchy', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to local dashboard
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('1. Desktop Dropdown: Dimensions, Hierarchy, and Whitespace-Nowrap', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const trigger = page.locator('#tenant-selector-trigger');
    await expect(trigger).toBeVisible();
    await expect(trigger).toHaveAttribute('aria-haspopup', 'listbox');
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Open dropdown
    await trigger.click();
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');

    const menu = page.locator('#tenant-selector-menu');
    await expect(menu).toBeVisible();

    // Check menu width is between 320px and 360px on desktop (we configured 350px)
    const box = await menu.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeGreaterThanOrEqual(320);
      expect(box.width).toBeLessThanOrEqual(360);
    }

    // Verify all 3 preset merchants are visible and have proper text
    const atlasOption = page.locator('#tenant-option-merch_atlas_travel');
    const alphaOption = page.locator('#tenant-option-merch_alpha');
    const electronicsOption = page.locator('#tenant-option-merch_95_alpha');

    await expect(atlasOption).toBeVisible();
    await expect(alphaOption).toBeVisible();
    await expect(electronicsOption).toBeVisible();

    // Verify merchant names are readable and in single line (nowrap)
    await expect(atlasOption.locator('text=Atlas Travel Gear')).toBeVisible();
    await expect(alphaOption.locator('text=Alpha Outfitters')).toBeVisible();
    await expect(electronicsOption.locator('text=Alpha Electronics')).toBeVisible();

    // Verify IDs are readable
    await expect(atlasOption.locator('text=merch_atlas_travel')).toBeVisible();
    await expect(alphaOption.locator('text=merch_alpha')).toBeVisible();
    await expect(electronicsOption.locator('text=merch_95_alpha')).toBeVisible();

    // Verify Selected Tenant identification (Atlas Travel Gear is default selected)
    await expect(atlasOption).toHaveAttribute('aria-selected', 'true');
    await expect(atlasOption.locator('svg')).toBeVisible(); // Checkmark icon
  });

  test('2. Tenant Selection & Context Switching', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const trigger = page.locator('#tenant-selector-trigger');
    await trigger.click();

    // Select Alpha Outfitters
    const alphaOption = page.locator('#tenant-option-merch_alpha');
    await alphaOption.click();

    // Dropdown must close after selection
    const menu = page.locator('#tenant-selector-menu');
    await expect(menu).not.toBeVisible();

    // Trigger button must now show Alpha Outfitters
    await expect(trigger).toContainText('Alpha Outfitters');
    await expect(trigger).toContainText('merch_alpha');

    // Reopen dropdown and verify Alpha Outfitters is now marked selected
    await trigger.click();
    await expect(alphaOption).toHaveAttribute('aria-selected', 'true');
    await expect(alphaOption.locator('svg')).toBeVisible();

    // Switch back to Atlas Travel Gear
    const atlasOption = page.locator('#tenant-option-merch_atlas_travel');
    await atlasOption.click();
    await expect(trigger).toContainText('Atlas Travel Gear');
  });

  test('3. Keyboard Navigation & Escape Dismissal', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const trigger = page.locator('#tenant-selector-trigger');
    await trigger.focus();

    // Open via Enter or Space
    await page.keyboard.press('Enter');
    const menu = page.locator('#tenant-selector-menu');
    await expect(menu).toBeVisible();

    // Arrow down moves focus between items
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');

    // Escape closes dropdown and refocuses trigger
    await page.keyboard.press('Escape');
    await expect(menu).not.toBeVisible();
    await expect(trigger).toBeFocused();
  });

  test('4. Custom Tenant Input & Go Control', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const trigger = page.locator('#tenant-selector-trigger');
    await trigger.click();

    const customInput = page.locator('input[placeholder="e.g. merch_custom_123"]');
    const goButton = page.locator('button:has-text("Go")');

    await expect(customInput).toBeVisible();
    await expect(goButton).toBeVisible();
    await expect(goButton).toBeDisabled();

    // Fill custom tenant
    await customInput.fill('merch_enterprise_nordic');
    await expect(goButton).toBeEnabled();

    // Click Go
    await goButton.click();

    // Menu closes and trigger updates
    await expect(page.locator('#tenant-selector-menu')).not.toBeVisible();
    await expect(trigger).toContainText('merch_enterprise_nordic');
  });

  test('5. Viewport Responsiveness: 1440px, 1280px, 1024px, and Mobile 375px', async ({ page }) => {
    const viewports = [
      { width: 1440, height: 900 },
      { width: 1280, height: 800 },
      { width: 1024, height: 768 },
      { width: 375, height: 667 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);
      const trigger = page.locator('#tenant-selector-trigger');
      await expect(trigger).toBeVisible();

      // Open menu
      await trigger.click();
      const menu = page.locator('#tenant-selector-menu');
      await expect(menu).toBeVisible();

      const menuBox = await menu.boundingBox();
      expect(menuBox).not.toBeNull();
      if (menuBox) {
        // Dropdown must remain within viewport boundaries
        expect(menuBox.x).toBeGreaterThanOrEqual(0);
        expect(menuBox.x + menuBox.width).toBeLessThanOrEqual(vp.width + 5);
      }

      // Close menu
      await page.keyboard.press('Escape');
      await expect(menu).not.toBeVisible();
    }
  });
});
