# Phase 3 Reproducibility Report

**Date**: September 3, 2026  
**Test**: `tests/integration/test_intent_reproducibility.py`

---

## Methodology

Each of the 40 golden benchmark cases was executed **5 consecutive times** through the `IntentExtractor.parse_utterance()` pipeline. For each case:

1. The same input text was passed identically 5 times
2. Each execution's output was serialized via `BuyerIntent.model_dump()`
3. The serialized output of runs 2-5 was compared byte-for-byte against run 1

For multi-turn cases (5 cases with `turns` key), the first turn was used as the reproducibility baseline.

## Results

| Metric | Value |
|:---|:---|
| Cases tested | 40 |
| Repetitions per case | 5 |
| Total executions | 200 |
| Semantic stability | **100%** |
| Schema version stability | **100%** (`buyer-intent/v1` on all 200 runs) |
| Prompt version stability | **100%** (`intent-extractor/v1` on all 200 runs) |
| Failures | **0** |

## Why Reproducibility is Guaranteed

The Buyer Intent Engine is **fully deterministic** — it contains zero LLM calls, zero stochastic sampling, and zero random state. Every extraction path is a hand-authored regex pattern or string match. This means:

1. **No temperature variance**: No neural network inference occurs
2. **No sampling**: No top-k or top-p sampling
3. **No external API calls**: No network-dependent results
4. **Stateless per-utterance**: Each `parse_utterance()` call operates on the input text alone
5. **Deterministic normalization**: `parse_raw_amount_to_paise()` uses `int(float(...))` — same bits in, same bits out

## Conclusion

The Phase 3 Buyer Intent Engine produces **byte-identical output across repeated executions** on the same input. Reproducibility is structurally guaranteed by the deterministic architecture.
