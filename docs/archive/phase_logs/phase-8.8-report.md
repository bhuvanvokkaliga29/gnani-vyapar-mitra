# Phase 8.8 — Policy Promotion & Lifecycle Versioning — Report

## 1. Phase Identifier
Phase 8.8 — Evidence-Gated Merchant Policy Lifecycle Management

## 2. Contract Versions
- `policy-lifecycle/v1`
- `promotion-policy/v1`

## 3. Objective
Determine whether an observed merchant policy has accumulated sufficient trustworthy evidence and satisfied all promotion requirements to become an active merchant policy version, and manage that lifecycle safely and immutably.

## 4. Core Rule
```
PREDICTION ≠ PROMOTION
EXPLORATION ≠ PROMOTION
EXECUTION ≠ PROMOTION
PAYMENT SUCCESS ≠ AUTOMATIC PROMOTION
```

## 5. Lifecycle State Machine
`CANDIDATE → ELIGIBLE_FOR_PROMOTION → ACTIVE → RETIRED / ROLLED_BACK`
- Single active policy per merchant enforced at database level (PK constraint on `MerchantActivePolicy.merchant_id`).
- Immutable version records — never updated in place.

## 6. Evidence Threshold Requirements
| Criterion | Threshold | Source |
|-----------|-----------|--------|
| Minimum sample | N ≥ 20 qualifying observations | Phase 8.3 memory |
| Safety violations | 0 in historical memory | Phase 8.3 memory |
| Observed contribution | > 0 paise | Phase 8.3 memory |
| Baseline outperformance | candidate_avg > baseline_avg | Phase 8.3 memory |
| Controlled experiment | COMPLETED + SUFFICIENT_EVIDENCE + winner=TREATMENT + 0 guardrails | Phase 8.7 (when present) |
| Fresh safety | Phase 8.6 ADMISSIBLE against current DB state | Phase 8.6 |

## 7. Database Schema Additions
- `MerchantActivePolicy` — single-row-per-merchant active pointer (PK = `merchant_id`)
- `MerchantPolicyVersionRecord` — immutable version history (unique: `merchant_id + policy_id + policy_version`)
- `PolicyLifecycleAuditRecord` — append-only audit trail

## 8. Promotion Decision Flow
1. Schema version guard
2. Merchant existence verification
3. Row-level `SELECT ... FOR UPDATE` on `MerchantActivePolicy`
4. Optimistic concurrency via `expected_previous_policy_id`
5. Idempotency check (return stored result if already promoted)
6. Evidence evaluation via `PolicyPromotionEvaluator`
7. Fresh Phase 8.6 safety gate via `PolicySafetyService.validate_policy`
8. Atomic transition: retire previous → activate candidate → update pointer → persist audit

## 9. Rollback Decision Flow
1. Schema version guard + row-level lock
2. Idempotency check
3. Target version retrieval + merchant ownership verification
4. Fresh Phase 8.6 safety check on target historical version
5. Atomic transition: current → `ROLLED_BACK`, target → `ACTIVE`, update pointer, audit

## 10. API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/policy-lifecycle/promote` | Evidence-gated promotion |
| `POST` | `/api/v1/policy-lifecycle/rollback` | Safety-checked rollback |
| `GET` | `/api/v1/policy-lifecycle/active/{merchant_id}` | Current active policy |
| `GET` | `/api/v1/policy-lifecycle/history/{merchant_id}` | Audit trail |
| `GET` | `/api/v1/policy-lifecycle/versions/{merchant_id}` | Version records |

## 11. Failure Taxonomy
`INSUFFICIENT_SAMPLE_SIZE`, `NEGATIVE_CONTRIBUTION`, `NO_IMPROVEMENT_OVER_BASELINE`, `GUARDRAIL_BREACH`, `INCONCLUSIVE_EXPERIMENT`, `EXPERIMENT_NOT_WON`, `SAFETY_GATE_REJECTED`, `PREDECESSOR_MISMATCH`, `CROSS_MERCHANT_FORBIDDEN`, `NO_OPPORTUNITY_EVIDENCE`, `UNSUPPORTED_VERSION`

## 12. Concurrency Model
- Row-level `SELECT ... FOR UPDATE` on `MerchantActivePolicy` prevents simultaneous promotions.
- Optimistic locking via `expected_previous_policy_id` (promotions) and `expected_current_policy_id` (rollbacks).

## 13. Idempotency Semantics
- Same `(merchant_id, candidate_policy_id)` already promoted → return stored `PolicyPromotionResult`.
- Same rollback target already active → return stored `PolicyRollbackResult`.

## 14. Safety Integration
- Promotion requires fresh Phase 8.6 `ADMISSIBLE` against **current** database commerce context.
- Rollback requires fresh Phase 8.6 `ADMISSIBLE` on the **target historical** policy version.
- Stale safety results cannot authorize lifecycle transitions.

## 15. Immutability Guarantees
- `MerchantPolicyVersionRecord` rows are never updated in place; new versions create new rows.
- `PolicyLifecycleAuditRecord` is append-only.
- `PolicyMemoryRecord` is never modified by promotion or rollback operations.

## 16. Tenant Isolation
- All queries scoped by `merchant_id`.
- Cross-merchant product references caught by Phase 8.6 `MERCHANT_SCOPE_MISMATCH`.
- Rollback target must belong to the requesting merchant.

## 17. Execution Authority
**ZERO.** Phase 8.8 cannot:
- Create Razorpay orders or payments
- Capture payments
- Reserve inventory
- Update learning models or prediction parameters
- Modify historical reward/evidence records
- Invoke n8n workflows
- Static AST boundary audit confirms compliance.

## 18. Test Results

| Suite | Count | Status |
|-------|-------|--------|
| Unit (evaluator) | 9 | ✅ ALL PASS |
| Integration (service + API) | 7 | ✅ ALL PASS |
| Adversarial (invariants A–O + AST) | 7 | ✅ ALL PASS |
| **Full Regression** | **582** | **✅ ALL PASS** |

## 19. Invariants Verified
- **A**: Ineligible policy never becomes ACTIVE
- **B/C**: High prediction/UCB cannot bypass evidence criteria
- **D**: Stale safety cannot authorize promotion
- **E**: Failed promotion leaves active policy unchanged
- **F**: Exactly one active policy per merchant (PK enforced)
- **G**: Historical versions immutable
- **H**: Promotions create auditable transitions
- **I**: Rollback preserves all historical versions
- **J**: Concurrent promotions protected via row lock
- **K/L**: Repeated promotion/rollback is idempotent
- **M**: Merchant tenant isolation enforced
- **N**: Zero execution authority (AST verified)
- **O**: Historical memory immutable across promotion

## 20. Files Added/Modified

| File | Action | Purpose |
|------|--------|---------|
| `domain/models.py` | MODIFIED | Added 3 SQLAlchemy models |
| `services/lifecycle/__init__.py` | NEW | Package init |
| `services/lifecycle/schemas.py` | NEW | Pydantic contracts |
| `services/lifecycle/errors.py` | NEW | Domain exceptions |
| `services/lifecycle/evaluator.py` | NEW | Deterministic promotion evaluator |
| `services/lifecycle/service.py` | NEW | Lifecycle service |
| `apps/api/routers/policy_lifecycle.py` | NEW | FastAPI router |
| `apps/api/main.py` | MODIFIED | Router registration |
| `tests/unit/test_policy_lifecycle_evaluator.py` | NEW | 9 unit tests |
| `tests/integration/test_policy_lifecycle_service.py` | NEW | 7 integration tests |
| `tests/integration/test_policy_lifecycle_adversarial.py` | NEW | 7 adversarial tests |
| `docs/phase-8.8-policy-lifecycle.md` | NEW | Technical documentation |
| `docs/phase-8.8-report.md` | NEW | This report |

## 21. Dependencies
- Phase 8.3 (`PolicyMemoryRecord`) — evidence source
- Phase 8.6 (`PolicySafetyService`) — fresh safety gate
- Phase 8.7 (`ExperimentResult`) — optional controlled experiment validation

## 22. Regressions
**None.** 582/582 tests pass including all prior phase tests.

## 23. Known Limitations
- SQLite (test mode) does not enforce `SELECT ... FOR UPDATE`; concurrency semantics verified logically.
- Experiment validation is optional; when no experiment exists, promotion proceeds on memory evidence alone.

## 24. Migration Notes
Three new tables: `merchant_active_policies`, `merchant_policy_version_records`, `policy_lifecycle_audit_records`. Run `Base.metadata.create_all()` or equivalent migration.

## 25. Contract Freeze
- `policy-lifecycle/v1` — FROZEN
- `promotion-policy/v1` — FROZEN

## 26. Phase 8.9 Status
**NOT STARTED. HARD STOP ENFORCED.** Awaiting explicit user approval before Phase 8.9.
