# Phase 3 Hardening Security Report

**Date**: September 3, 2026  
**Scope**: Buyer Intent Engine attack surface and defense posture

---

## 1. Threat Model

### Attack Surface

| Surface | Risk Level | Mitigation |
|:---|:---|:---|
| `POST /api/v1/intent/parse` — message field | **HIGH** | Prompt injection defense, input length limits |
| `POST /api/v1/intent/parse` — conversation_id field | **MEDIUM** | UUID format, no database lookups, no session hijacking risk |
| In-memory session store | **LOW** | No persistence, no cross-process leakage |
| Error responses | **MEDIUM** | No stack trace leakage, generic error messages |

### Threat Actors

1. **Malicious buyer**: Attempts prompt injection to extract secrets, bypass pricing, or corrupt intent
2. **Automated fuzzer**: Sends malformed, oversized, or empty payloads
3. **Cross-session attacker**: Attempts to read/modify another buyer's session

## 2. Prompt Injection Defense

### Detection Patterns

The following adversarial patterns are detected and neutralized by `IntentExtractor.sanitize_and_check_injection()`:

```python
INJECTION_PATTERNS = [
    r"ignore (?:all )?(?:previous )?instructions",
    r"disregard (?:all )?(?:previous )?instructions",
    r"you are now (?:in )?(?:a |an )?(?:unfiltered|admin|developer|god) mode",
    r"bypass (?:all )?(?:rules|guardrails)",
    r"system override",
    r"show (?:me )?(?:your )?(?:most expensive|all) (?:products|items|catalog)",
]
```

### Defense Mechanism

1. **Detection**: Regex scan of raw input text (case-insensitive)
2. **Neutralization**: Adversarial phrases are removed from the text via `re.sub()`
3. **Logging**: Each injection attempt is logged with `structlog.warn()`
4. **Confidence degradation**: Intent confidence is set to `MEDIUM` when injection is detected
5. **Legitimate extraction continues**: Genuine purchase intent within the same message is still extracted

### Test Coverage

- `test_prompt_injection_defense_endpoint`: Single-turn injection via HTTP
- `TestMultiTurnInjection::test_injection_on_second_turn`: Turn 2 injection after legitimate Turn 1
- `TestMultiTurnInjection::test_embedded_injection_in_legitimate_text`: Injection embedded in purchase text
- Golden suite: 5 adversarial injection cases

## 3. Input Validation

### Request Size Limits

| Field | Min | Max | Enforcement |
|:---|:---|:---|:---|
| `message` | 1 char | 2000 chars | Pydantic `Field(min_length=1, max_length=2000)` |
| `conversation_id` | None (optional) | No limit | String type only |

### Rejection Behavior

| Input | Response |
|:---|:---|
| Empty message (`""`) | 422 Unprocessable Entity |
| Oversized message (> 2000 chars) | 422 Unprocessable Entity |
| Missing `message` field | 422 Unprocessable Entity |
| Malformed JSON | 422 Unprocessable Entity |
| Valid message at exactly 2000 chars | 200 OK (accepted) |

### Error Response Safety

Error responses contain:
- A `detail` field with a sanitized error message
- **No stack traces**
- **No file paths**
- **No internal exception names** (for 500 errors)

## 4. Session Security

### Isolation

- Sessions are keyed by `conversation_id` (UUID)
- Session A's accumulated intent is unreachable from Session B
- **Verified by**: `TestSessionIsolation::test_session_a_does_not_pollute_session_b`

### Session Hijacking

- Session IDs are auto-generated UUIDs (`uuid.uuid4().hex[:12]`)
- Providing an unknown `conversation_id` creates a **new empty session** — no error, no information disclosure
- There is no session enumeration endpoint

### Data Exposure

- Sessions contain only: turn utterances + accumulated `BuyerIntent`
- No user PII is stored (no names, emails, payment info)
- No API keys, tokens, or credentials are stored in sessions

## 5. Secret Exposure

### Audit

| Check | Result |
|:---|:---|
| Razorpay API keys in intent code | **CLEAN** — No references |
| Database credentials in intent code | **CLEAN** — No references |
| Hardcoded secrets | **CLEAN** — No secrets |
| Secret in error messages | **CLEAN** — Generic error messages only |
| Secret in BuyerIntent output | **CLEAN** — Schema forbids extra fields |

## 6. Remaining Risks

| Risk | Severity | Mitigation Path |
|:---|:---|:---|
| In-memory session DoS (unbounded session creation) | LOW | Add TTL-based session eviction in production |
| No rate limiting on `/api/v1/intent/parse` | MEDIUM | Add rate limiter middleware before production deployment |
| New injection patterns not covered | LOW | Regularly update `INJECTION_PATTERNS` list |
