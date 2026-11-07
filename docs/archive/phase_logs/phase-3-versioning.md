# Phase 3 Versioning Specification

**Date**: September 3, 2026  
**Status**: FROZEN

---

## Active Versions

| Component | Version | Status | Introduced |
|:---|:---|:---|:---|
| BuyerIntent schema | `buyer-intent/v1` | **FROZEN** | Phase 3 |
| Intent Extractor prompt | `intent-extractor/v1` | **FROZEN** | Phase 3 |

## Version Fields in BuyerIntent

Every `BuyerIntent` object emitted by the engine carries two version fields:

```python
schema_version: str = "buyer-intent/v1"   # Contract schema version
prompt_version: str = "intent-extractor/v1"  # System prompt version
```

These fields enable:
1. **Downstream compatibility checks** — Phase 4 Policy Agent can assert it receives a compatible schema version
2. **Audit trail** — Every intent record can be traced to the exact extraction pipeline that produced it
3. **Migration safety** — When v2 is introduced, v1 consumers can gracefully reject incompatible schemas

## Versioning Change Process

### When to Bump `schema_version`

Bump to `buyer-intent/v2` when ANY of the following changes occur:

| Change Type | Example | Action |
|:---|:---|:---|
| Field added (required) | New `brand` field | **MAJOR** bump → v2 |
| Field removed | Removing `use_case` | **MAJOR** bump → v2 |
| Field type changed | `quantity: int` → `quantity: str` | **MAJOR** bump → v2 |
| Enum value removed | Removing `BudgetType.TARGET` | **MAJOR** bump → v2 |
| Field added (optional, with default) | New `gift_wrapping: bool = False` | Backward-compatible, but still bump |
| Enum value added | Adding `BudgetType.EXACT` | Backward-compatible, still bump |

### When to Bump `prompt_version`

Bump to `intent-extractor/v2` when the extraction logic changes in a way that would produce different outputs for the same input:

| Change Type | Example | Action |
|:---|:---|:---|
| New regex pattern added | Supporting `₹1 crore` | Bump prompt version |
| Pattern priority changed | Budget matching order reordered | Bump prompt version |
| Injection pattern added | New adversarial defense pattern | Bump prompt version |
| Category keyword added | Supporting `"briefcase"` → `briefcase` | Bump prompt version |

### Change Process

1. Create a migration document in `docs/` describing the change
2. Update the version string in both `intent_schemas.py` and `prompts.py`
3. Update golden test fixtures if expected outputs change
4. Run full regression suite
5. Notify Phase 4 consumers of the version change

## Frozen Contract

As of this hardening pass, `buyer-intent/v1` and `intent-extractor/v1` are **FROZEN**. No further changes will be made to these versions. Future work starts at v2.
