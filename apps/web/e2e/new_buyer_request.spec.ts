import { test, expect } from '@playwright/test';

test.describe('New Buyer Request Flow & Progressive Disclosure', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');
  });

  test('1. Step 1 (Composer): Clicking "+ New Buyer Request" opens clean composer with preset chips and hygiene badge', async ({ page }) => {
    // Locate and click "+ New Buyer Request" button
    const newRequestBtn = page.locator('button:has-text("+ New Buyer Request")');
    await expect(newRequestBtn).toBeVisible();
    await newRequestBtn.click();

    // Verify modal overlay and Step 1 Composer headline
    await expect(page.getByRole('heading', { name: 'What does the buyer want?' })).toBeVisible();
    await expect(
      page.locator('text=Describe the buyer inquiry or shopping context in natural language.')
    ).toBeVisible();

    // Verify Information Hygiene badge
    await expect(
      page.locator('text=COGS, margins, and policy internals remain protected')
    ).toBeVisible();

    // Verify all 5 preset chips are rendered
    const expectedPresets = [
      'Weekend Backpack',
      'Laptop Sleeve Bundle',
      'Strict Budget Pack',
      'Commuter Pack',
      'Low Budget NO_OFFER',
    ];
    for (const preset of expectedPresets) {
      await expect(page.locator(`button:has-text("${preset}")`)).toBeVisible();
    }

    // Verify Evaluate button is initially disabled when prompt is empty
    const evalBtn = page.locator('button:has-text("Evaluate Request")');
    await expect(evalBtn).toBeVisible();
    await expect(evalBtn).toBeDisabled();

    // Verify Escape key closes modal
    await page.keyboard.press('Escape');
    await expect(page.getByRole('heading', { name: 'What does the buyer want?' })).not.toBeVisible();
  });

  test('2. Step 2 (Evaluation Result): Evaluating request renders Sections A-F with strict information hygiene', async ({ page }) => {
    // Open modal
    await page.locator('button:has-text("+ New Buyer Request")').click();
    await expect(page.getByRole('heading', { name: 'What does the buyer want?' })).toBeVisible();

    // Click "Weekend Backpack" preset chip
    const presetBtn = page.locator('button:has-text("Weekend Backpack")');
    await presetBtn.click();

    // Verify textarea populated
    const textarea = page.locator('textarea');
    await expect(textarea).toHaveValue('Looking for a durable weekend travel backpack under 4000');

    // Evaluate button is now enabled
    const evalBtn = page.locator('button:has-text("Evaluate Request")');
    await expect(evalBtn).toBeEnabled();

    // Submit evaluation and wait for network response
    const evalPromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/decisions/evaluate') && resp.status() === 200
    );
    await evalBtn.click();
    const evalResponse = await evalPromise;
    const evalJson = await evalResponse.json();
    const decisionId = evalJson.decision_id;
    expect(decisionId).toBeTruthy();

    // Verify transition to Step 2: "Buyer Request Evaluation"
    await expect(page.getByRole('heading', { name: 'Buyer Request Evaluation' })).toBeVisible({ timeout: 10000 });
    // Verify it is NOT showing internal "Autonomous Decision Inspection"
    await expect(page.locator('text=Autonomous Decision Inspection')).not.toBeVisible();

    const modal = page.locator('[data-testid="new-buyer-request-modal"]');

    // Section A: Original Buyer Request quote card
    await expect(modal.getByText(/Section A/i)).toBeVisible();
    await expect(modal.getByText('Looking for a durable weekend travel backpack under 4000')).toBeVisible();

    // Section B: What We Understood (Structured Intent)
    await expect(modal.getByText(/Section B/i)).toBeVisible();
    await expect(modal.getByText('Category')).toBeVisible();

    // Section C: Authoritative Recommended Offer
    await expect(modal.getByText(/Section C/i)).toBeVisible();
    await expect(modal.getByText(/delivery/i)).toBeVisible();
    await expect(modal.getByText(/warranty/i)).toBeVisible();

    // Section D: Commercial Rationale
    await expect(modal.getByText(/Section D/i)).toBeVisible();

    // Section E: Safety & Checkout Gate
    await expect(modal.getByText(/Section E/i)).toBeVisible();
    await expect(modal.getByText('ADMISSIBLE')).toBeVisible();

    // Section F: Primary & Secondary Actions
    const checkoutBtn = modal.getByRole('button', { name: 'Open Test Checkout' });
    await expect(checkoutBtn).toBeVisible();

    const traceBtn = modal.getByRole('button', { name: 'View Full Decision Trace' });
    await expect(traceBtn).toBeVisible();

    // STRICT INFORMATION HYGIENE AUDIT:
    // Ensure merchant-private economics (COGS, gross margin, LinUCB uncertainty, contribution)
    // are completely excluded from the Buyer Request Evaluation modal text.
    const modalText = await page.locator('[role="dialog"]').innerText();
    expect(modalText).not.toMatch(/cogs_paise/i);
    expect(modalText).not.toMatch(/gross_margin_percent/i);
    expect(modalText).not.toMatch(/composite_ranking_score/i);
    expect(modalText).not.toMatch(/uncertainty\s*:\s*\d/i);
    expect(modalText).not.toMatch(/11-stage/i);
  });

  test('3. Progressive Transition: "View Full Decision Trace" transitions to 11-stage Autonomous Decision Inspection', async ({ page }) => {
    // Open modal and evaluate
    await page.locator('button:has-text("+ New Buyer Request")').click();
    await page.locator('button:has-text("Laptop Sleeve Bundle")').click();
    await page.locator('button:has-text("Evaluate Request")').click();

    // Wait for Step 2
    await expect(page.getByRole('heading', { name: 'Buyer Request Evaluation' })).toBeVisible({ timeout: 10000 });

    // Click "View Full Decision Trace"
    const traceBtn = page.locator('button:has-text("View Full Decision Trace")');
    await traceBtn.click();

    // Verify modal closed
    await expect(page.getByRole('heading', { name: 'Buyer Request Evaluation' })).not.toBeVisible();

    // Verify DecisionDetailDrawer opened with 11-stage trace
    await expect(page.locator('text=Autonomous Decision Inspection')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=11-STAGE END-TO-END IDENTITY CHAIN')).toBeVisible();
    await expect(page.locator('text=Merchant Unit Economics (Private)')).toBeVisible();
  });

  test('4. NO_OFFER Evaluation: Evaluates gracefully without checkout button', async ({ page }) => {
    // Open modal
    await page.locator('button:has-text("+ New Buyer Request")').click();

    // Click "Low Budget NO_OFFER" preset
    await page.locator('button:has-text("Low Budget NO_OFFER")').click();
    await page.locator('button:has-text("Evaluate Request")').click();

    // Wait for Step 2
    await expect(page.getByRole('heading', { name: 'Buyer Request Evaluation' })).toBeVisible({ timeout: 10000 });

    // Verify NO_OFFER badge is displayed
    await expect(page.locator('text=NO OFFER').first()).toBeVisible();

    // Verify Open Test Checkout is NOT visible / not enabled
    await expect(page.locator('button:has-text("Open Test Checkout")')).not.toBeVisible();

    // Verify explanation indicates no matching offer
    await expect(
      page.locator('text=No current catalog option satisfies the buyer\'s stated requirements')
    ).toBeVisible();

    // Can still view full trace or edit request
    await expect(page.locator('button:has-text("View Full Decision Trace")')).toBeVisible();
    await expect(page.locator('button:has-text("Edit Request")')).toBeVisible();
  });
});
