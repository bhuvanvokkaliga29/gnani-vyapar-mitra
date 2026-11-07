import { test, expect } from '@playwright/test';
import crypto from 'crypto';

test.describe('Razorpay Test Mode Live Checkout & Closed-Loop Resolution', () => {
  test('Complete canonical journey: Buyer request -> Decision -> Boundary Authorization -> Test Mode Checkout -> Reconcile -> 11-Stage Closed Loop', async ({ page, request }) => {
    // Step 1: Create ONE fresh valid canonical decision through the real runtime
    const oppId = `opp_live_demo_${Date.now()}`;
    const evalRes = await request.post('http://localhost:8000/api/v1/decisions/evaluate', {
      data: {
        merchant_id: 'merch_atlas_travel',
        opportunity_id: oppId,
        raw_prompt: 'Looking for a travel pack together with laptop sleeve under 6000'
      }
    });
    expect(evalRes.status()).toBe(200);
    const evalJson = await evalRes.json();
    const freshDecisionId = evalJson.decision_id;
    expect(freshDecisionId).toBeTruthy();
    expect(evalJson.selected_policy.strategy_type).not.toBe('NO_OFFER');

    // Step 2: Open AI Decisions Ledger in Demo Dashboard
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');

    // Step 3: Select the newly created executable decision from the ledger
    const targetRow = page.locator(`tbody tr:has-text("${freshDecisionId}")`).first();
    await expect(targetRow).toBeVisible({ timeout: 10000 });
    await targetRow.click();

    // Step 4: Verify Decision Detail Drawer opened
    await expect(page.locator('text=Autonomous Decision Inspection')).toBeVisible({ timeout: 5000 });
    await expect(page.locator(`text=${freshDecisionId}`).first()).toBeVisible();

    // Step 5: Verify Open Test Checkout action button is visible for executable decision
    const checkoutBtn = page.locator('button:has-text("Open Test Checkout")');
    await expect(checkoutBtn).toBeVisible();

    // Step 6: Trigger Test Checkout & intercept boundary execution
    const execPromise = page.waitForResponse(resp => 
      resp.url().includes('/api/v1/decisions/') && resp.url().includes('/execute') && resp.status() === 200
    );

    await checkoutBtn.click();
    const execResponse = await execPromise;
    const execJson = await execResponse.json();

    expect(execJson.execution_authorized).toBe(true);
    expect(execJson.boundary_status).toBe('EXECUTION_COMPLETED');
    expect(execJson.authorization_id).toBeTruthy();
    expect(execJson.razorpay_order_id).toBeTruthy();
    expect(execJson.order_id).toBeTruthy();

    const razorpayOrderId = execJson.razorpay_order_id;

    // Step 7: Verify authentic Razorpay Test Mode checkout UI is visibly open on screen!
    await expect(page.locator('iframe.razorpay-checkout-frame')).toBeVisible({ timeout: 10000 });

    // Step 8: Deliver authentic HMAC-SHA256 signed payment.captured webhook
    // (exact signal delivered by Razorpay servers upon payment completion)
    const webhookPayload = {
      entity: "event",
      account_id: "acc_live_demo",
      event: "payment.captured",
      contains: ["payment"],
      payload: {
        payment: {
          entity: {
            id: `pay_demo_${Date.now()}`,
            order_id: razorpayOrderId,
            amount: execJson.authorized_amount_paise || 299900,
            currency: "INR",
            status: "captured",
            method: "upi"
          }
        }
      },
      created_at: Math.floor(Date.now() / 1000)
    };

    const rawBody = JSON.stringify(webhookPayload);
    const webhookSecret = 'whsec_test_buildathon_2026';
    const signature = crypto.createHmac('sha256', webhookSecret).update(rawBody).digest('hex');

    const whRes = await request.post('http://localhost:8000/webhooks/razorpay', {
      data: rawBody,
      headers: {
        'Content-Type': 'application/json',
        'X-Razorpay-Signature': signature,
        'X-Razorpay-Event-Id': `evt_demo_${Date.now()}`
      }
    });
    expect(whRes.status()).toBe(200);

    // Dismiss the Razorpay checkout modal overlay in test environment
    await page.evaluate(() => {
      const container = document.querySelector('.razorpay-container');
      if (container) container.remove();
    });
    await page.waitForTimeout(500);

    // Step 9: Refresh page to reflect the newly paid decision in the decisions table
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');

    // Click the refreshed row
    const refreshedRow = page.locator(`tbody tr:has-text("${freshDecisionId}")`).first();
    await expect(refreshedRow).toBeVisible({ timeout: 5000 });
    await expect(refreshedRow).toContainText('EXECUTION_COMPLETED');
    await expect(refreshedRow).toContainText('PAID (Test Mode)');
    await refreshedRow.click();

    const drawer = page.locator('[role="dialog"]');
    await expect(drawer).toBeVisible({ timeout: 5000 });

    // Step 10: Verify the complete 11-stage identity chain in drawer
    const expectedStages = [
      '1. Request',
      '2. Opportunity',
      '3. Decision',
      '4. Authorization',
      '5. Execution',
      '6. Order',
      '7. Payment',
      '8. Outcome',
      '9. Evidence',
      '10. Memory',
      '11. Model Update'
    ];

    for (const stage of expectedStages) {
      await expect(drawer.locator(`text=${stage}`).first()).toBeVisible();
    }

    // Step 11: Verify Boundary Execution & Learning updated inside drawer
    await expect(drawer.getByText('EXECUTION_COMPLETED').first()).toBeVisible();
    await expect(drawer.getByText('PAYMENT_SUCCESS').first()).toBeVisible();
    await expect(drawer.getByText('YES').first()).toBeVisible();

    // Step 12: Verify "Open Test Checkout" button is now hidden because decision is already PAID
    await expect(drawer.locator('button:has-text("Open Test Checkout")')).not.toBeVisible();
  });

  test('Non-executable decisions (NO_OFFER) must NOT display the checkout action button', async ({ page }) => {
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');

    // Find NO_OFFER row
    const noOfferRow = page.locator('tbody tr:has-text("NO_OFFER")').first();
    if (await noOfferRow.isVisible()) {
      await noOfferRow.click();
      await expect(page.locator('text=Autonomous Decision Inspection')).toBeVisible();

      // Open Test Checkout button must NOT appear
      await expect(page.locator('button:has-text("Open Test Checkout")')).not.toBeVisible();
    }
  });

  test('Canonical Atlas demo rehearsal: Expired decision -> Evaluate Fresh Live Opportunity -> Deterministically shows Open Test Checkout -> Initiates Razorpay checkout', async ({ page }) => {
    // 1. Navigate to decisions ledger
    await page.goto('/decisions');
    await page.waitForLoadState('networkidle');

    // 2. Open the seeded historical expired fixture (opp_probe_before)
    const expiredRow = page.locator('tbody tr:has-text("opp_probe_before")').first();
    for (let p = 0; p < 5; p++) {
      if (await expiredRow.isVisible()) break;
      const nextBtn = page.locator('button:has-text("Next")');
      if (await nextBtn.isVisible() && await nextBtn.isEnabled()) {
        await nextBtn.click();
        await page.waitForTimeout(400);
      } else {
        break;
      }
    }
    await expect(expiredRow).toBeVisible({ timeout: 10000 });
    await expiredRow.click();

    // 3. Verify drawer opens with Safety TTL Expired alert
    const drawer = page.locator('[role="dialog"]');
    await expect(drawer).toBeVisible({ timeout: 5000 });
    await expect(drawer.locator('text=Safety TTL Expired (15m)')).toBeVisible();

    // 4. Verify "Open Test Checkout" is initially NOT shown because decision is expired
    await expect(drawer.locator('button:has-text("Open Test Checkout")')).not.toBeVisible();

    // 5. Click "Evaluate Fresh Live Opportunity"
    const evalFreshBtn = drawer.locator('button:has-text("Evaluate Fresh Live Opportunity")');
    await expect(evalFreshBtn).toBeVisible();
    await evalFreshBtn.click();

    // 6. Wait for fresh evaluation to finish and success message to display
    await expect(drawer.locator('text=Ready for checkout!')).toBeVisible({ timeout: 15000 });

    // 7. Verify fresh decision semantics in drawer:
    await expect(drawer.locator('text=SINGLE_PRODUCT').or(drawer.locator('text=COMPLEMENTARY_BUNDLE')).first()).toBeVisible();
    await expect(drawer.locator('text=ADMISSIBLE').first()).toBeVisible();
    await expect(drawer.locator('text=PENDING_EXECUTION_GATE').first()).toBeVisible();

    // 8. Verify "Open Test Checkout" is now visibly rendered and enabled!
    const checkoutBtn = drawer.locator('button:has-text("Open Test Checkout")');
    await expect(checkoutBtn).toBeVisible();
    await expect(checkoutBtn).toBeEnabled();

    // 9. Click "Open Test Checkout" and verify Razorpay iframe opens
    await checkoutBtn.click();
    await expect(page.locator('iframe.razorpay-checkout-frame')).toBeVisible({ timeout: 10000 });

    // Clean up modal overlay
    await page.evaluate(() => {
      const container = document.querySelector('.razorpay-container');
      if (container) container.remove();
    });
  });
});
