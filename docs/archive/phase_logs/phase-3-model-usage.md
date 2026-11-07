# Phase 3 Model Usage Discipline

**Date**: September 3, 2026  
**Applies to**: Buyer Intent Engine (Phase 3)

---

## Current Model Usage: ZERO

The Phase 3 Buyer Intent Engine makes **zero LLM API calls**.

| Component | LLM Calls | Technique |
|:---|:---|:---|
| `normalizer.py` | 0 | Regex + string matching |
| `validator.py` | 0 | Arithmetic + set operations |
| `extractor.py` | 0 | Regex + pattern cascade |
| `conversation.py` | 0 | Field-by-field merge logic |
| `prompts.py` | 0 | Static string constants only |
| `intent.py` (router) | 0 | HTTP handler only |

### Why Zero LLM

The v1 engine was deliberately designed to use zero LLM calls for the following reasons:

1. **Determinism**: LLM outputs are stochastic (temperature > 0). Regex is deterministic.
2. **Latency**: LLM inference adds 200-2000ms per call. Regex runs in < 1ms.
3. **Cost**: LLM inference costs money per token. Regex is free.
4. **Testability**: Deterministic code can be unit-tested exhaustively. LLM outputs require probabilistic evaluation.
5. **Reproducibility**: Same input → same output, always. Required for the Buildathon evaluation.

### Trade-offs

| Dimension | Regex-Based (Current) | LLM-Based (Future) |
|:---|:---|:---|
| Coverage | Limited to predefined patterns | Broad natural language understanding |
| False negatives | High for unseen phrasings | Low |
| False positives | Low (precise patterns) | Medium (hallucination risk) |
| Latency | < 1ms | 200-2000ms |
| Cost per request | $0 | $0.001-0.01 |
| Determinism | Perfect | Stochastic |

## Future Phase 4 Model Usage

Phase 4 (Policy Agent) will introduce LLM inference for:

1. Product recommendation reasoning
2. Bundle construction
3. Dynamic pricing optimization
4. Offer generation and negotiation

Phase 4 LLM calls will operate on the **BuyerIntent v1 output** — never on raw buyer text. This separation ensures the intent layer remains auditable and deterministic.

## Model Usage Accounting

| Phase | LLM Provider | Model | Calls per Request | Token Budget |
|:---|:---|:---|:---|:---|
| Phase 3 (current) | None | None | 0 | 0 |
| Phase 4 (planned) | TBD | TBD | 1-3 | TBD |
