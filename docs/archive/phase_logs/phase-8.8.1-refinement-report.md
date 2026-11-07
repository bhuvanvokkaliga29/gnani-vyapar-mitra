# Phase 8.8.1 Evidence-Strength & Promotion-Gate Refinement Report
## Merchant Policy Agent — Razorpay AI Buildathon 2026, Track 01

### 1. Status
- **Status**: COMPLETE, VERIFIED, ADVERSARIALLY HARDENED.
- **Contracts**:
  - `policy-lifecycle/v1` — FROZEN
  - `promotion-policy/v1` — FROZEN

### 2. Evidence Hierarchy
Explicit hierarchy established:
1. `CONTROLLED_EXPERIMENT`: Level 1 evidence with randomized or deterministic hash assignment under Phase 7. Causal attribution supported by experimental isolation.
2. `OBSERVATIONAL_HISTORY`: Level 2 evidence from Phase 8.3 memory. Weaker support subject to historical selection bias. Causal superiority is NOT claimed; explicit non-causal disclaimer attached to all outcomes.

### 3. Controlled Promotion Semantics
- Reuses Phase 7 `ExperimentService.get_experiment_result()` without duplicating evaluation logic.
- Verifies:
  - Candidate policy is the treatment arm (`treatment_policy_id == candidate_policy_id`). Mismatches rejected via `EXPERIMENT_TREATMENT_MISMATCH`.
  - Experiment status is `COMPLETED`.
  - Scientific evidence status is `SUFFICIENT_EVIDENCE`.
  - Winner variant is `TREATMENT`.
  - All experiment guardrails passed (`passed=True`).
  - Fresh Phase 8.6 safety check is `ADMISSIBLE`.

### 4. Observational Promotion Semantics
- Allowed only when `allow_observational_promotion=True` and `require_controlled_experiment=False`.
- Stricter conservative criteria:
  - Sample size threshold (configurable `min_observational_learning_opportunities`, default 20, supports higher thresholds such as 30+).
  - Outperforming `NO_OFFER` baseline.
  - Positive mean observed contribution.
  - Non-domination constraint: maximum 50% contribution share from any single opportunity (`max_opportunity_contribution_share <= 0.50`). Breaches rejected with `OBSERVATIONAL_CONCENTRATION_EXCEEDED`.
  - Minimum context diversity (`min_distinct_contexts >= 1`).
  - Recency window compliance (default 30 days).
  - Zero historical safety violations.
  - Mandatory disclaimer: *"Observational evidence only. Subject to historical selection bias. Does not establish causal superiority or guaranteed uplift."*

### 5. Sample-Size Conclusion
- `N ≥ 20` is NOT sufficient by itself.
- Only current-effective, learning-eligible, admissible, recency-compliant, and deduplicated observations count toward the sample size.
- Zero-contribution observations count toward the denominator (representing real non-purchase trials).
- Negative-contribution observations count and pull down the mean.
- Duplicate and superseded records are strictly excluded.

### 6. Evidence-Population Semantics
- Evidence is sourced strictly from Phase 8.3 `policy_memory` records.
- Records must have `learning_eligible = True`, `is_admissible = True`, and `is_current = True` (`superseded_by is None`).
- Records are deduplicated by `opportunity_id` to guarantee that no single opportunity contributes twice.

### 7. Policy-Version Integrity
- Strict scoping by `(merchant_id, policy_id, candidate_policy_version)`.
- Evidence for `merchant-policy/v1` cannot authorize `merchant-policy/v2`.
- Version mismatches are rejected via `POLICY_VERSION_MISMATCH`.
- No cross-version evidence pooling.

### 8. Baseline Semantics
- Preserves Phase 8.2 canonical baseline: `CANONICAL_BASELINE_POLICY_ID` / `cand_base_no_offer`.
- Candidate mean contribution must strictly exceed baseline mean contribution on comparable current-effective eligible baseline records within the recency window.

### 9. Recency Semantics
- Lookback window enforced via `recency_window_days` (default 30 days).
- Records older than `evaluation_time - recency_window_days` are excluded as stale. If eligible historical records exist but are excluded by recency, fails with `STALE_EVIDENCE`.
- Future evidence (`observed_at > evaluation_time`) is rejected with `FUTURE_EVIDENCE_REJECTED`.

### 10. Drift Considerations
- Exposes diagnostics in evidence summary:
  - `context_distribution`: distribution of observations across distinct buyer contexts.
  - `distinct_contexts_count`: number of distinct commercial intent contexts observed.
  - `concentration`: maximum single opportunity contribution share and threshold.
- Observational concentration limit prevents promotion driven by a single anomalous windfall opportunity.

### 11. Safety Requirements
- Fresh Phase 8.6 safety check via `PolicySafetyService.validate_policy()` against current DB commerce context is strictly mandatory before activation or rollback.
- Historical safety or stale safety cannot authorize promotion.
- If Phase 8.6 returns `REJECTED`, promotion is denied with `SAFETY_GATE_REJECTED`.

### 12. Prediction / UCB Separation
- Frozen principle:
  ```
  PREDICTION ≠ PROMOTION
  UCB ≠ PROMOTION
  EXPLORATION SUCCESS ≠ AUTOMATIC PROMOTION
  ```
- Evaluator has ZERO access to predicted contribution or UCB scores.
- Realized, admissible historical outcomes are mandatory.

### 13. Promotion Configuration Version
- Authoritative contract: `promotion-policy/v1`.
- Configuration envelope versioned and persisted in `PolicyLifecycleAuditRecord.promotion_config_version`.

### 14. Atomicity & Concurrency Verification
- `MerchantActivePolicy` row-level lock (`SELECT ... FOR UPDATE`) prevents concurrent promotion race conditions.
- Predecessor verification (`expected_previous_policy_id`) provides optimistic concurrency conflict detection (`PREDECESSOR_MISMATCH`).
- Atomic transactions ensure that retirement of old active and activation of new version succeed or fail as an indivisible unit.

### 15. Idempotency
- Repeated promotion of the same candidate version against the same expected predecessor returns the existing `PolicyPromotionResult` without creating duplicate lifecycle transitions.

### 16. Rollback Verification
- Rollback target must be an immutable historical `MerchantPolicyVersionRecord` belonging to the requesting merchant.
- Fresh Phase 8.6 safety validation is required on the historical target before reinstatement.

### 17. Adversarial Results
- 12/12 adversarial invariant tests passing in `tests/integration/test_policy_lifecycle_adversarial.py`.
- Verified Invariants A through O:
  - Invariant A/B/C: Ineligible policies, high predictions, or high UCB cannot become ACTIVE.
  - Invariant D/E: Failed promotions leave active policy unchanged; stale safety rejected.
  - Invariant E: Superseded observations cannot contribute.
  - Invariant F: Different policy versions cannot be merged.
  - Invariant F/G: Single active policy per merchant; immutable versions.
  - Invariant H/I: Auditable lifecycle trail; rollback preserves history.
  - Invariant J: Concurrency safety via row locking.
  - Invariant K/L: Promotion and rollback idempotency.
  - Invariant M: Cross-tenant isolation strictly enforced.
  - Invariant M (future): Future evidence cannot influence historical promotions.
  - Invariant N: Promotion cannot execute transactions (static AST audit: 0 violations).
  - Invariant O: Historical memory records are immutable across promotions.

### 18. Full Regression Count
- **596 passed, 0 failures, 0 regressions** across the entire project test suite.

### 19. Files Changed
| File | Action | Description |
|---|---|---|
| `services/lifecycle/schemas.py` | MODIFIED | Added `PromotionEvidenceType`, new failure codes, `STALE_EVIDENCE` status, config fields, and result fields. |
| `domain/models.py` | MODIFIED | Added `evidence_type` column to `PolicyLifecycleAuditRecord`. |
| `services/lifecycle/evaluator.py` | MODIFIED | Implemented evidence hierarchy, version integrity, population filtering, recency/staleness, concentration & diversity checks. |
| `services/lifecycle/service.py` | MODIFIED | Integrated candidate version, experiment treatment arm validation, failure code mapping, and audit persistence. |
| `tests/unit/test_policy_lifecycle_evaluator.py` | EXPANDED | Expanded to 18 unit tests covering all Phase 8.8.1 gates. |
| `tests/integration/test_policy_lifecycle_adversarial.py` | EXPANDED | Expanded to 12 adversarial tests covering Invariants A–O. |
| `docs/phase-8.8-policy-lifecycle.md` | UPDATED | Updated technical documentation. |
| `docs/phase-8.8.1-refinement-report.md` | NEW | This report. |

### 20. Remaining Limitations
- Observational evidence cannot eliminate latent selection bias; future closed-loop tracking will monitor post-promotion performance.
- Drift detection in 8.8.1 is deterministic (context distribution, opportunity concentration); advanced distribution-divergence modeling is deferred.

### 21. Explicit Confirmation
- [x] NO new learning algorithm
- [x] NO exploration logic added
- [x] NO candidate selection modified
- [x] NO reward changes
- [x] NO memory schema changes
- [x] NO Razorpay execution authority
- [x] NO n8n dependency or integration
- [x] **Phase 8.9 NOT STARTED** (Strict stop enforced)
