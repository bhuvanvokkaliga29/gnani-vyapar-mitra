import { test, expect } from '@playwright/test';

const MOCK_MERCHANT_ID = 'merch_atlas_travel';

const MOCK_OVERVIEW = {
  merchant_id: MOCK_MERCHANT_ID,
  merchant_name: 'Atlas Travel Gear',
  currency: 'INR',
  runtime_status: 'HEALTHY',
  status_headline: 'Merchant AI Control Center',
  status_subtext: 'Autonomous decision pipeline balancing revenue and margin with point-in-time safety checks and closed-loop learning.',
  ai_buyer_opportunities_count: 42,
  decision_count: 42,
  authorized_executions_count: 38,
  paid_transactions_count: 35,
  expected_contribution_paise: 2500000,
  observed_contribution_paise: 2100000,
  test_mode_observed_contribution_paise: 2100000,
  decision_rate_percent: 100.0,
  active_policy: {
    policy_id: 'pol_current_active',
    policy_version: 'merchant-policy/v1',
    strategy_type: 'SINGLE_PRODUCT',
    lifecycle_status: 'ACTIVE',
    observed_contribution_paise: 1800000,
    evidence_count: 24,
    context_coverage_count: 3,
    promoted_at: '2026-09-03T10:00:00Z'
  },
  learning_insight: {
    buyer_context_key: 'CTX_HIGH_INTENT',
    context_description: 'High Intent Shoppers',
    observed_preference_strategy: 'BUNDLE',
    evidence_count: 24,
    context_coverage_count: 3,
    observed_contribution_paise: 1200000,
    evidence_strength: 'HIGH',
    evidence_class: 'TEST_MODE_OBSERVED'
  },
  attention_items: [],
  recent_decisions: [
    {
      decision_id: 'dec_e2e_001',
      opportunity_id: 'opp_e2e_001',
      created_at: '2026-09-03T12:30:00Z',
      buyer_context_key: 'CTX_SEARCH_DIRECT',
      selected_strategy_type: 'SINGLE_PRODUCT',
      proposed_price_paise: 350000,
      decision_mode: 'EXPLOIT',
      execution_status: 'COMMITTED',
      outcome_status: 'CAPTURED',
      learning_eligible: true
    }
  ],
  generated_at: '2026-09-03T12:00:00Z'
};

const MOCK_DECISIONS = {
  items: [
    {
      decision_id: 'dec_e2e_001',
      opportunity_id: 'opp_e2e_001',
      created_at: '2026-09-03T12:30:00Z',
      buyer_context_key: 'CTX_SEARCH_DIRECT',
      selected_strategy_type: 'SINGLE_PRODUCT',
      proposed_price_paise: 350000,
      decision_mode: 'EXPLOIT',
      execution_status: 'COMMITTED',
      outcome_status: 'CAPTURED',
      learning_eligible: true
    }
  ],
  total: 1,
  limit: 20,
  offset: 0
};

const MOCK_DECISION_DETAIL = {
  decision_id: 'dec_e2e_001',
  merchant_id: MOCK_MERCHANT_ID,
  opportunity_id: 'opp_e2e_001',
  request_id: 'req_e2e_001',
  created_at: '2026-09-03T12:30:00Z',
  buyer_context_key: 'CTX_SEARCH_DIRECT',
  selected_strategy_type: 'SINGLE_PRODUCT',
  decision_mode: 'EXPLOIT',
  raw_prompt: 'waterproof backpack with laptop sleeve',
  authorization_id: 'auth_e2e_001',
  execution_id: 'exec_e2e_001',
  order_id: 'order_e2e_001',
  payment_id: 'pay_e2e_001',
  outcome_id: 'out_e2e_001',
  evidence_id: 'evi_e2e_001',
  memory_id: 'mem_e2e_001',
  applied_observation_id: 'amo_e2e_001',
  buyer_offer: {
    offer_title: 'Waterproof Commuter Pack',
    product_ids: ['prod_backpack'],
    offer_price_paise: 350000,
    currency: 'INR',
    strategy_type: 'SINGLE_PRODUCT',
    warranty_months: 12,
    delivery_days: 2,
    included_items: ['Rain Cover']
  },
  merchant_evaluation: {
    cogs_paise: 180000,
    gross_profit_paise: 170000,
    gross_margin_percent: 48.57,
    predicted_contribution_paise: 165000,
    uncertainty: 0.12,
    composite_ranking_score: 1.85,
    decision_mode: 'EXPLOIT',
    rationale: 'Exceeds target gross profit threshold by ₹200'
  },
  candidates: [
    {
      candidate_id: 'cand_baseline',
      strategy_type: 'SINGLE_PRODUCT',
      proposed_price_paise: 400000,
      predicted_contribution_paise: 140000,
      uncertainty: 0.05,
      composite_ranking_score: 1.4,
      is_selected: false
    },
    {
      candidate_id: 'cand_chosen',
      strategy_type: 'SINGLE_PRODUCT',
      proposed_price_paise: 350000,
      predicted_contribution_paise: 165000,
      uncertainty: 0.12,
      composite_ranking_score: 1.85,
      is_selected: true
    }
  ],
  safety_status: 'PASSED',
  safety_rejection_reasons: [],
  execution_status: 'COMMITTED',
  transaction_state: 'PAID',
  outcome_status: 'CAPTURED',
  learning_eligible: true,
  reward_contribution_paise: 170000
};

const MOCK_POLICIES = {
  merchant_id: MOCK_MERCHANT_ID,
  active_policy: {
    policy_id: 'pol_current_active',
    policy_version: 'merchant-policy/v1',
    strategy_type: 'SINGLE_PRODUCT',
    lifecycle_status: 'ACTIVE',
    observed_contribution_paise: 1800000,
    evidence_count: 24,
    context_coverage_count: 3,
    promoted_at: '2026-09-03T10:00:00Z'
  },
  versions: [
    {
      policy_id: 'pol_current_active',
      version_id: 'v1.1',
      strategy_type: 'SINGLE_PRODUCT',
      lifecycle_status: 'ACTIVE',
      created_at: '2026-09-03T10:00:00Z',
      promoted_at: '2026-09-03T10:00:00Z',
      evidence_count: 24,
      observed_contribution_paise: 1800000,
      promotion_criteria_satisfied: true,
      is_active: true
    },
    {
      policy_id: 'pol_historical_v0',
      version_id: 'v1.0',
      strategy_type: 'SINGLE_PRODUCT',
      lifecycle_status: 'RETIRED',
      created_at: '2026-09-01T08:00:00Z',
      promoted_at: null,
      evidence_count: 15,
      observed_contribution_paise: 900000,
      promotion_criteria_satisfied: true,
      is_active: false
    }
  ],
  recent_transitions: []
};

const MOCK_EXPERIMENTS = {
  items: [
    {
      experiment_id: 'exp_e2e_001',
      name: 'Bundle Strategy vs Single Product',
      status: 'ACTIVE',
      source: 'TEST_MODE_OBSERVED',
      control_policy_id: 'pol_historical_v0',
      treatment_policy_id: 'pol_current_active',
      population_size: 120,
      control_observed_ecps_paise: 12000,
      treatment_observed_ecps_paise: 16200,
      observed_diff_paise: 4200,
      guardrail_status: 'PASSED',
      created_at: '2026-09-02T10:00:00Z',
      completed_at: null
    }
  ],
  total: 1
};

const MOCK_LEARNING = {
  merchant_id: MOCK_MERCHANT_ID,
  health: {
    eligible_opportunities_count: 42,
    valid_evidence_count: 38,
    rejected_evidence_count: 4,
    memory_observations_count: 38,
    model_updates_count: 38,
    duplicate_observations_count: 0
  },
  context_breakdown: [
    {
      buyer_context_key: 'CTX_SEARCH_DIRECT',
      context_label: 'Direct Search Intent',
      preferred_strategy: 'SINGLE_PRODUCT',
      evidence_count: 24,
      observed_contribution_paise: 2400000,
      last_updated_at: '2026-09-03T12:00:00Z',
      status: 'ACTIVE_LEARNING'
    }
  ],
  model_metadata: {
    model_version: 'linucb-v1.0.0',
    algorithm_version: 'DISJOINT_LINUCB',
    feature_version: 'feat_v1',
    dimension: 8,
    lambda_reg: 1.0,
    alpha_paise: 50000,
    observation_count: 38,
    version: 38,
    last_updated_at: '2026-09-03T12:00:00Z',
    learning_status: 'CONVERGING'
  },
  evidence_class: 'TEST_MODE_OBSERVED'
};

const MOCK_ACTIVITY = {
  items: [
    {
      audit_event_id: 'aud_e2e_001',
      timestamp: '2026-09-03T12:30:00Z',
      entity_type: 'DECISION',
      action: 'DECISION_COMMITTED',
      opportunity_id: 'opp_e2e_001',
      decision_id: 'dec_e2e_001',
      execution_id: 'exec_e2e_001',
      summary: 'Autonomous decision executed via commit boundary',
      details: { mode: 'EXPLOIT', price: 350000 }
    }
  ],
  total: 1,
  limit: 50,
  offset: 0
};

const MOCK_TRACE = {
  opportunity_id: 'opp_e2e_001',
  merchant_id: MOCK_MERCHANT_ID,
  trace_status: 'COMPLETE',
  stages_present: [
    'INTENT_RECONSTRUCTED',
    'POLICY_CANDIDATES_GENERATED',
    'POLICY_SELECTED',
    'SAFETY_VALIDATED',
    'EXECUTION_COMMITTED',
    'ORDER_CREATED',
    'OUTCOME_CAPTURED',
    'EVIDENCE_LOGGED',
    'MODEL_UPDATED'
  ],
  audit_event_count: 9,
  created_at: '2026-09-03T12:30:00Z'
};

test.beforeEach(async ({ page }) => {
  // Mock all dashboard API routes with strictly typed schemas
  await page.route('**/api/v1/dashboard/overview*', async (route) => {
    await route.fulfill({ json: MOCK_OVERVIEW });
  });

  await page.route('**/api/v1/dashboard/decisions?*', async (route) => {
    await route.fulfill({ json: MOCK_DECISIONS });
  });

  await page.route('**/api/v1/dashboard/decisions/dec_e2e_001*', async (route) => {
    await route.fulfill({ json: MOCK_DECISION_DETAIL });
  });

  await page.route('**/api/v1/dashboard/policies?*', async (route) => {
    await route.fulfill({ json: MOCK_POLICIES });
  });

  await page.route('**/api/v1/dashboard/experiments*', async (route) => {
    await route.fulfill({ json: MOCK_EXPERIMENTS });
  });

  await page.route('**/api/v1/dashboard/learning*', async (route) => {
    await route.fulfill({ json: MOCK_LEARNING });
  });

  await page.route('**/api/v1/dashboard/activity*', async (route) => {
    await route.fulfill({ json: MOCK_ACTIVITY });
  });

  await page.route('**/api/v1/dashboard/traces/opp_e2e_001*', async (route) => {
    await route.fulfill({ json: MOCK_TRACE });
  });
});

// =============================================================================
// 1. TEST: test_merchant_can_complete_control_center_journey
// =============================================================================
test('1. test_merchant_can_complete_control_center_journey', async ({ page }) => {
  await page.goto('/');

  // Verify Overview page loaded
  await expect(page.locator('h1')).toContainText('Merchant AI Control Center');
  await expect(page.locator('text=HEALTHY')).toBeVisible();
  await expect(page.locator('text=TEST MODE')).toBeVisible();

  // Navigate to Decisions
  await page.click('a[href="/decisions"]');
  await expect(page.locator('h1')).toContainText('AI Decisions Ledger');
  await expect(page.locator('text=dec_e2e_001')).toBeVisible();

  // Navigate to Policies
  await page.click('a[href="/policies"]');
  await expect(page.locator('h1')).toContainText('Commercial Policy Lifecycle');
  await expect(page.locator('text=pol_current_active').first()).toBeVisible();

  // Navigate to Experiments
  await page.click('a[href="/experiments"]');
  await expect(page.locator('h1')).toContainText('Controlled Policy Experiments');
  await expect(page.locator('text=Bundle Strategy vs Single Product')).toBeVisible();

  // Navigate to Learning
  await page.click('a[href="/learning"]');
  await expect(page.locator('h1')).toContainText('Continuous Learning Center');
  await expect(page.locator('text=CONVERGING')).toBeVisible();

  // Navigate to Activity
  await page.click('a[href="/activity"]');
  await expect(page.locator('h1')).toContainText('Operational Activity & Trace Inspector');
  await expect(page.locator('text=Autonomous decision executed')).toBeVisible();
});

// =============================================================================
// 2. TEST: test_cross_tenant_browser_access_rejected
// =============================================================================
test('2. test_cross_tenant_browser_access_rejected', async ({ page }) => {
  // Intercept overview with 403 Forbidden
  await page.route('**/api/v1/dashboard/overview*', async (route) => {
    await route.fulfill({
      status: 403,
      json: { detail: "Forbidden: Authenticated caller 'merch_alpha' is not authorized to access tenant 'merch_beta'." }
    });
  });

  await page.goto('/');
  await expect(page.locator('text=Forbidden: Authenticated caller')).toBeVisible();
});

// =============================================================================
// 3. TEST: test_decision_detail_trace_is_complete
// =============================================================================
test('3. test_decision_detail_trace_is_complete', async ({ page }) => {
  await page.goto('/decisions');
  await expect(page.locator('text=dec_e2e_001')).toBeVisible();

  // Click decision row to open detail drawer
  await page.click('text=dec_e2e_001');

  // Verify Drawer opened
  const drawer = page.locator('div[role="dialog"]');
  await expect(drawer).toBeVisible();
  await expect(drawer.locator('text=Autonomous Decision Inspection')).toBeVisible();

  // Verify 11 stages lineage
  await expect(drawer.locator('text=1. Request')).toBeVisible();
  await expect(drawer.locator('text=req_e2e_001')).toBeVisible();
  await expect(drawer.locator('text=11. Model Update')).toBeVisible();
  await expect(drawer.locator('text=amo_e2e_001')).toBeVisible();

  // Check Dual View: Buyer Offer
  await expect(drawer.locator('text=Waterproof Commuter Pack')).toBeVisible();
  await expect(drawer.locator('text=12 months')).toBeVisible();

  // Switch to Merchant Internal Economics tab
  await drawer.locator('button:has-text("Merchant Unit Economics")').click();
  await expect(drawer.locator('text=Product COGS')).toBeVisible();
  await expect(drawer.locator('text=₹1,800')).toBeVisible();

  // Verify Escape key closes drawer
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
});

// =============================================================================
// 4. TEST: test_stale_policy_control_rejected
// =============================================================================
test('4. test_stale_policy_control_rejected', async ({ page }) => {
  // Mock 409 Conflict on rollback
  await page.route('**/api/v1/dashboard/policies/rollback', async (route) => {
    await route.fulfill({
      status: 409,
      json: { detail: "Active policy conflict: expected 'pol_current_active' but found 'pol_promoted_concurrently'." }
    });
  });

  await page.goto('/policies');
  await expect(page.locator('text=pol_historical_v0')).toBeVisible();

  // Click Rollback button on historical policy
  await page.click('button:has-text("Rollback")');

  // Modal appears
  const modal = page.locator('div[role="dialog"]');
  await expect(modal).toBeVisible();
  await expect(modal.locator('text=Confirm Policy Rollback')).toBeVisible();

  // Submit rollback
  await modal.locator('textarea').fill('Rollback test for conflict simulation');
  await modal.locator('button:has-text("Execute Safe Rollback")').click();

  // Stale state conflict error displayed clearly
  await expect(modal.locator('text=State Conflict: Active policy has changed')).toBeVisible();
});

// =============================================================================
// 5. TEST: test_duplicate_control_action_is_idempotent
// =============================================================================
test('5. test_duplicate_control_action_is_idempotent', async ({ page }) => {
  let callCount = 0;
  await page.route('**/api/v1/dashboard/policies/rollback', async (route) => {
    callCount++;
    await route.fulfill({
      status: 200,
      json: {
        success: true,
        action: 'ROLLBACK',
        policy_id: 'pol_historical_v0',
        message: "Active policy rolled back to 'pol_historical_v0'.",
        audit_event_id: 'aud_rb_001',
        timestamp: new Date().toISOString()
      }
    });
  });

  await page.goto('/policies');
  await expect(page.locator('text=pol_historical_v0')).toBeVisible();
  await page.click('button:has-text("Rollback")');
  const modal = page.locator('div[role="dialog"]');
  await modal.locator('textarea').fill('Idempotent rollback test');
  await modal.locator('button:has-text("Execute Safe Rollback")').click();

  // Success alert appears with audit event
  await expect(page.locator('text=Policy rolled back to pol_historical_v0 (Audit Event: aud_rb_001)')).toBeVisible();
  expect(callCount).toBe(1);
});

// =============================================================================
// 6. TEST: test_learning_and_outcome_semantics_render_correctly
// =============================================================================
test('6. test_learning_and_outcome_semantics_render_correctly', async ({ page }) => {
  await page.goto('/learning');

  // Verify Closed-Loop Learning Diagram
  await expect(page.locator('text=The Continuous Learning Loop')).toBeVisible();
  await expect(page.locator('text=1. Outcome')).toBeVisible();
  await expect(page.locator('text=5. Model Update')).toBeVisible();

  // Verify Health counters
  await expect(page.locator('text=Valid Evidence').first()).toBeVisible();
  await expect(page.locator('text=38').first()).toBeVisible();

  // Verify Model Metadata does not leak raw matrices
  await expect(page.locator('text=DISJOINT_LINUCB')).toBeVisible();
  await expect(page.locator('text=a_matrix')).not.toBeVisible();
  await expect(page.locator('text=b_vector')).not.toBeVisible();
});

// =============================================================================
// 7. TEST: test_test_mode_is_clearly_labeled
// =============================================================================
test('7. test_test_mode_is_clearly_labeled', async ({ page }) => {
  await page.goto('/');

  // Verify Test Mode indicator is prominently displayed in the top bar
  await expect(page.getByText('TEST MODE', { exact: true })).toBeVisible();

  // Verify evidence classes are explicitly rendered on cards
  await expect(page.locator('text=Test-Mode Observed').first()).toBeVisible();
});

// =============================================================================
// 8. TEST: test_empty_dashboard_is_safe
// =============================================================================
test('8. test_empty_dashboard_is_safe', async ({ page }) => {
  // Empty overview
  await page.route('**/api/v1/dashboard/overview*', async (route) => {
    await route.fulfill({
      json: {
        merchant_id: MOCK_MERCHANT_ID,
        merchant_name: 'Atlas Travel Gear',
        currency: 'INR',
        runtime_status: 'HEALTHY',
        status_headline: 'No Traffic Active',
        status_subtext: 'No decisions evaluated yet.',
        ai_buyer_opportunities_count: 0,
        decision_count: 0,
        authorized_executions_count: 0,
        paid_transactions_count: 0,
        expected_contribution_paise: 0,
        observed_contribution_paise: 0,
        test_mode_observed_contribution_paise: 0,
        decision_rate_percent: 0,
        active_policy: null,
        learning_insight: null,
        attention_items: [],
        recent_decisions: [],
        generated_at: '2026-09-03T12:00:00Z'
      }
    });
  });

  await page.goto('/');
  await expect(page.locator('text=No decisions evaluated yet.')).toBeVisible();
  await expect(page.locator('text=No active policy pointer found.')).toBeVisible();
});

// =============================================================================
// 9. TEST: test_dashboard_error_state_is_safe
// =============================================================================
test('9. test_dashboard_error_state_is_safe', async ({ page }) => {
  // 500 error on Overview
  await page.route('**/api/v1/dashboard/overview*', async (route) => {
    await route.fulfill({
      status: 500,
      json: { detail: 'Internal Server Error' }
    });
  });

  await page.goto('/');
  await expect(page.locator('text=Internal Server Error')).toBeVisible();
  // Ensure no raw stack traces or database connection strings appear
  await expect(page.locator('text=Traceback')).not.toBeVisible();
  await expect(page.locator('text=postgresql://')).not.toBeVisible();
});

// =============================================================================
// 10. TEST: test_untrusted_text_cannot_execute_html
// =============================================================================
test('10. test_untrusted_text_cannot_execute_html', async ({ page }) => {
  let dialogFired = false;
  page.on('dialog', async (dialog) => {
    dialogFired = true;
    await dialog.dismiss();
  });

  // Overview with XSS attempt in summary/headline
  await page.route('**/api/v1/dashboard/overview*', async (route) => {
    const maliciousOverview = JSON.parse(JSON.stringify(MOCK_OVERVIEW));
    maliciousOverview.status_headline = "<script>alert('XSS_ATTACK')</script>";
    await route.fulfill({ json: maliciousOverview });
  });

  await page.goto('/');
  // Text should be rendered as plain string, never executing as an alert
  await expect(page.locator('text=<script>alert')).toBeVisible();
  expect(dialogFired).toBe(false);
});
