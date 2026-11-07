import { test, expect } from '@playwright/test';

test.describe('Commercial Policy Lifecycle & Governance UX Refinement', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/policies');
    await page.waitForLoadState('networkidle');
  });

  test('1. Active Baseline Card: Human hierarchy, secondary ID, and governed baseline notes', async ({ page }) => {
    // Page Title
    await expect(page.getByRole('heading', { name: 'Commercial Policy Lifecycle' })).toBeVisible();

    // Verify TEST MODE badge
    await expect(page.locator('text=TEST MODE').first()).toBeVisible();

    // Verify Active Baseline human-readable primary title
    await expect(page.getByRole('heading', { name: /NO_OFFER — Active Baseline/i })).toBeVisible();

    // Verify Policy ID is displayed as secondary technical identity
    await expect(page.locator('text=Policy ID:').first()).toBeVisible();
    await expect(page.locator('text=cand_base_no_offer').first()).toBeVisible();

    // Verify Contract Version
    await expect(page.locator('text=merchant-policy/v1').first()).toBeVisible();

    // Verify Metric grid labels & zero-evidence disambiguation
    await expect(page.locator('text=ACTIVE BASELINE').first()).toBeVisible();
    await expect(page.locator('text=baseline control policy').first()).toBeVisible();
    await expect(page.locator('text=No policy-specific observations').first()).toBeVisible();

    // Verify Explanatory Baseline Note
    await expect(
      page.locator('text=NO_OFFER is the governed baseline control policy. Learned candidates do not replace the active policy until promotion requirements are satisfied.')
    ).toBeVisible();
  });

  test('2. Mental Model Signposts: "Learning and activation are separate" & Compact Lifecycle Legend', async ({ page }) => {
    // Verify Active vs Learned clarity callout
    await expect(page.locator('h3:has-text("Learning and activation are separate.")')).toBeVisible();
    await expect(
      page.locator('text=Learned candidates may show promising evidence without becoming the active policy.')
    ).toBeVisible();

    // Verify Compact Lifecycle Legend
    await expect(page.locator('text=Lifecycle Roles:')).toBeVisible();
    await expect(page.locator('text=Being evaluated')).toBeVisible();
    await expect(page.locator('text=Passed promotion gates')).toBeVisible();
    await expect(page.locator('text=Currently governed')).toBeVisible();
    await expect(page.locator('text=No longer active')).toBeVisible();
    await expect(page.locator('text=Previously active; reverted')).toBeVisible();
  });

  test('3. Policy Version Registry: Human naming, [Not Eligible] semantics, and zero-evidence contribution', async ({ page }) => {
    // Registry header and improved subtitle
    await expect(page.getByRole('heading', { name: 'Policy Version Registry' })).toBeVisible();
    await expect(
      page.locator('text=Registered commercial policies and their current lifecycle state. Candidates require verified evidence and fresh safety checks before promotion.')
    ).toBeVisible();

    const registryTable = page.locator('table').first();

    // Active baseline row in registry
    const baselineRow = registryTable.locator('tr:has-text("cand_base_no_offer")');
    await expect(baselineRow).toBeVisible();
    await expect(baselineRow.locator('text=Baseline — Not Applicable')).toBeVisible();
    await expect(baselineRow.locator('text=Currently Active')).toBeVisible();

    // Candidate row in registry (e.g. Complementary Bundle Offer)
    const candidateRow = registryTable.locator('tr:has-text("Complementary Bundle Offer")');
    await expect(candidateRow).toBeVisible();

    // Verify Policy ID is visible in candidate row
    await expect(candidateRow.locator('text=/cand_[a-z0-9]+/i')).toBeVisible();

    // Verify "Pending Evidence" criteria
    await expect(candidateRow.locator('text=Pending Evidence')).toBeVisible();

    // Verify contribution displays "No policy-specific observations" for zero evidence
    await expect(candidateRow.locator('text=No policy-specific observations')).toBeVisible();

    // CRUCIAL UX REQUIREMENT: Unevidenced candidate must show disabled [Not Eligible] button, NOT active Promote!
    const notEligibleBtn = candidateRow.getByRole('button', { name: 'Not Eligible' });
    await expect(notEligibleBtn).toBeVisible();
    await expect(notEligibleBtn).toBeDisabled();

    // Verify tooltip on [Not Eligible] button
    const titleAttr = await notEligibleBtn.getAttribute('title');
    expect(titleAttr).toContain('Requires sufficient verified evidence and successful safety/governance checks.');
  });

  test('4. Governance Audit History: "Governance Evaluations" framing and active policy unchanged notes', async ({ page }) => {
    // Verify "Governance Evaluations" title and count (NOT "Recorded Transitions")
    await expect(page.getByRole('heading', { name: 'Lifecycle Governance Audit History' })).toBeVisible();
    await expect(page.locator('text=/\\d+ Governance Evaluations/i')).toBeVisible();
    await expect(page.locator('text=Recorded Transitions')).not.toBeVisible();

    // Verify explanatory subtitle
    await expect(
      page.locator('text=Append-only record of promotion evaluations, lifecycle changes, rollbacks, and safety decisions.')
    ).toBeVisible();

    // Verify repeated INSUFFICIENT_EVIDENCE rows remain preserved and show supplemental "Promotion rejected; active policy unchanged"
    const rejectRows = page.locator('tr:has-text("INSUFFICIENT_EVIDENCE")');
    const count = await rejectRows.count();
    expect(count).toBeGreaterThan(0);

    // Check first rejection row
    const firstRejectRow = rejectRows.first();
    await expect(firstRejectRow.locator('text=Promotion rejected; active policy unchanged')).toBeVisible();
    await expect(firstRejectRow.locator('text=cand_base_no_offer').first()).toBeVisible();
  });
});
