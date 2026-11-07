"""Policy Diff Engine: Deterministically isolates structural and economic differences between Control and Treatment."""

from typing import Dict, Any, List
from services.experiments.schemas import PolicyDiff


class PolicyDiffEngine:
    """Computes deterministic comparative difference between two policy proposals."""

    @staticmethod
    def compute_diff(
        control_snapshot: Dict[str, Any],
        treatment_snapshot: Dict[str, Any]
    ) -> PolicyDiff:
        """Compute structural, product, price, and incentive diff between Control and Treatment."""
        # Extract selected candidate from control proposal
        ctrl_cand = control_snapshot.get("selected_candidate") or (
            control_snapshot.get("candidates", [{}])[0] if control_snapshot.get("candidates") else {}
        )
        ctrl_econ = ctrl_cand.get("economics", {})

        # Extract selected candidate from treatment proposal
        treat_cand = treatment_snapshot.get("selected_candidate") or (
            treatment_snapshot.get("candidates", [{}])[0] if treatment_snapshot.get("candidates") else {}
        )
        treat_econ = treat_cand.get("economics", {})

        ctrl_strategy = ctrl_cand.get("strategy_type", "UNKNOWN")
        treat_strategy = treat_cand.get("strategy_type", "UNKNOWN")

        ctrl_price = ctrl_econ.get("proposed_price_paise") or ctrl_cand.get("price_paise", 0)
        treat_price = treat_econ.get("proposed_price_paise") or treat_cand.get("price_paise", 0)
        price_delta = treat_price - ctrl_price

        ctrl_margin = float(ctrl_econ.get("margin_percent", 0.0))
        treat_margin = float(treat_econ.get("margin_percent", 0.0))
        margin_delta = round(treat_margin - ctrl_margin, 2)

        ctrl_items = ctrl_cand.get("included_items") or []
        treat_items = treat_cand.get("included_items") or []
        added_items = [item for item in treat_items if item not in ctrl_items]

        ctrl_warranty = ctrl_cand.get("warranty_months", 0)
        treat_warranty = treat_cand.get("warranty_months", 0)
        warranty_delta = treat_warranty - ctrl_warranty

        treat_incentives = treat_cand.get("incentives") or []

        # Construct human-readable summary
        summary_parts = []
        if ctrl_strategy != treat_strategy:
            summary_parts.append(f"Strategy: {ctrl_strategy} -> {treat_strategy}")
        if price_delta != 0:
            direction = "+" if price_delta > 0 else ""
            summary_parts.append(f"Price: {direction}₹{price_delta / 100:.2f}")
        if added_items:
            summary_parts.append(f"Added items: {', '.join(added_items)}")
        if warranty_delta != 0:
            direction = "+" if warranty_delta > 0 else ""
            summary_parts.append(f"Warranty: {direction}{warranty_delta} mo")
        if treat_incentives:
            summary_parts.append(f"Incentives: {', '.join(treat_incentives)}")

        summary = "; ".join(summary_parts) if summary_parts else "No material policy difference"

        return PolicyDiff(
            control_strategy=ctrl_strategy,
            treatment_strategy=treat_strategy,
            control_price_paise=ctrl_price,
            treatment_price_paise=treat_price,
            price_delta_paise=price_delta,
            control_margin_percent=ctrl_margin,
            treatment_margin_percent=treat_margin,
            margin_delta_percent=margin_delta,
            control_included_items=ctrl_items,
            treatment_included_items=treat_items,
            added_items=added_items,
            control_warranty_months=ctrl_warranty,
            treatment_warranty_months=treat_warranty,
            warranty_delta_months=warranty_delta,
            treatment_incentives=treat_incentives,
            summary=summary
        )
