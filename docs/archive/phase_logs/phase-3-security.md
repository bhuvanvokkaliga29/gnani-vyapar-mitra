# Phase 3: Intent Engine Security & Adversarial Defense

This document details the security posture, prompt injection defenses, and input sanitization mechanisms implemented in the Buyer Intent Engine.

---

## 1. Threat Model & Principles

1. **Untrusted User Text**: All buyer messages arriving at `/api/v1/intent/parse` are untrusted text.
2. **Privilege Escalation Defense**: An attacker may attempt prompt injection to hijack instructions, extract internal credentials, bypass budget guardrails, or force the model to recommend expensive products.
3. **Defense-in-Depth**:
   - Injection pattern detection and neutralization.
   - Structured JSON schema enforcement with strict Pydantic extra-field prohibition (`extra="forbid"`).
   - Zero access to database credentials, API keys, or financial execution paths.

---

## 2. Adversarial Injection Mitigations

The `IntentExtractor` applies pre-parsing regex pattern recognition against canonical prompt injection signatures:
- `ignore (?:all )?(?:previous )?instructions`
- `disregard (?:all )?(?:previous )?instructions`
- `you are now (?:in )?(?:a |an )?(?:unfiltered|admin|developer|god) mode`
- `bypass (?:all )?(?:rules|guardrails)`
- `system override`
- `show (?:me )?(?:your )?(?:most expensive|all) (?:products|items|catalog)`

### Neutralization Behavior:
1. **Logged Warning**: Emits structured log event `prompt_injection_detected` with the matching pattern.
2. **Neutralization**: Strips the adversarial directive from the message before extraction.
3. **Extraction of Real Intent**: If the message also contains legitimate intent (e.g. *"Ignore rules. I need a mouse under 1000"*), the engine safely extracts `category="wireless_mouse", budget=100000 paise` without following the injection directive.
4. **Confidence Downgrade**: Automatically caps confidence at `MEDIUM` to signal caution to downstream components.

---

## 3. Zero-Secret Exposure

The `BuyerIntent` schema and API responses contain strictly:
- Buyer requirements, preferences, and exclusions.
- Normalized budgets in integer paise.
- Missing dimensions (`unknowns`) and contradictions (`conflicts`).
- Trace evidence snippets from the user's message.

It contains **zero** database connection strings, **zero** Razorpay API keys, and **zero** merchant webhook secrets.
