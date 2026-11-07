# Phase 8.1 Evidence Model: Authoritative Learning Evidence

## 1. Role as an Architectural Firewall

In autonomous commerce systems, feeding raw, uncontrolled data directly into a learner results in catastrophic instability, reward hacking, and security vulnerabilities.

The `PolicyLearningEvidence` model acts as an **authoritative firewall**:
1. **Provenance Enforcement**: Every datum traces to an immutable experiment, observation, policy snapshot, and buyer intent.
2. **Deterministic Validation**: Eligibility is derived exclusively by deterministic application code; the LLM has zero authority to declare data "eligible".
3. **Economic Separation**: Prevents downstream learning algorithms from mistaking simulated model expectations for observed financial cash inflows.

---

## 2. Deterministic Eligibility Derivation (`learning_eligible`)

The `learning_eligible` boolean indicates whether a learning algorithm is permitted to update policy weights or policy memory from this evidence record.

### Derivation Rules:
$$\text{learning\_eligible} \iff \begin{cases}
\text{evidence\_status} == \text{VALID} \\
\land \quad \text{experiment\_status} == \text{COMPLETED} \\
\land \quad \text{guardrail\_failures} == 0 \\
\land \quad \text{provenance\_complete} == \text{True} \\
\land \quad \text{source} \in \{\text{SIMULATED}, \text{TEST\_MODE\_OBSERVED}\} \\
\land \quad \text{sample\_size} \ge 1
\end{cases}$$

### Rejection Triggers:
- `INSUFFICIENT_SAMPLE`: Sample size below minimum threshold.
- `INCONCLUSIVE`: Experiment failed to demonstrate a meaningful effect.
- `GUARDRAIL_FAILURE`: Treatment violated merchant safety guardrails (disqualified from positive learning).
- `INVALID`: Missing provenance or corrupted economic figures.

---

## 3. Buyer Context Key (`buyer_context_key`)

Commercial policy learning must be context-sensitive, answering:
> "How does Policy A perform for buyers seeking a 15.6 inch laptop compartment with budget $\le$ ₹4,000?"

### Deterministic, Non-Demographic Construction:
```python
raw_signature = (
    f"cat={dims.category};"
    f"tier={dims.budget_tier};"
    f"reqs={dims.hard_requirement_signature};"
    f"prefs={dims.preference_signature};"
    f"excls={dims.exclusion_signature}"
)
digest = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()[:12]
buyer_context_key = f"bck_{dims.category}_{dims.budget_tier}_{digest}"
```

### Privacy & Anti-Surveillance Invariant:
The context key strictly forbids demographic profiling:
- Forbidden attributes: `age`, `gender`, `income`, `race`, `religion`, `zipcode`, `health`, `politics`.
- Attempted injection of demographic fields raises an immediate `SecurityBoundaryError`.

---

## 4. Policy Identity & Aggregation Key

To evaluate policies over time without conflating materially different strategies:
- **Policy Identity**: Composed of `policy_id`, `policy_version`, and experimental `variant`.
- **Canonical Aggregation Key**:
  $$\text{aggregation\_key} = \text{merchant\_id} : \text{buyer\_context\_key} : \text{policy\_id} : \text{policy\_version}$$

This key allows future learners to group evidence deterministically without cross-merchant leakage or collapsing distinct policy versions.
