"""Experiment Runner: Orchestrates simulation and execution of policy variants across populations."""

import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.intent_schemas import BuyerIntent
from services.buyer_lab.schemas import BuyerOffer, BuyerPersonaType
from services.buyer_lab.simulator import BuyerSimulator
from services.buyer_lab.competitors import get_synthetic_competitor_offers
from services.execution.gate import ExecutionGate
from services.execution.schemas import PolicyExecuteRequest
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentObservation,
    VariantType,
    OutcomeType,
    AssignmentStrategy
)
from services.experiments.assignment import AssignmentEngine

logger = structlog.get_logger()


class ExperimentRunner:
    """Executes experiments by assigning scenarios, simulating buyer choice, and recording observations."""

    def __init__(
        self,
        buyer_simulator: Optional[BuyerSimulator] = None,
        execution_gate: Optional[ExecutionGate] = None
    ):
        self.simulator = buyer_simulator or BuyerSimulator()
        self.gate = execution_gate or ExecutionGate()

    def candidate_to_buyer_offer(
        self,
        candidate: Dict[str, Any],
        merchant_id: str,
        merchant_label: str = "Atlas Travel Gear"
    ) -> BuyerOffer:
        """Convert an internal policy proposal candidate into a buyer-visible BuyerOffer.
        
        Strictly excludes internal financials (COGS, margin %, objective, policy score).
        """
        econ = candidate.get("economics", {})
        price_paise = econ.get("proposed_price_paise") or candidate.get("price_paise", 0)

        return BuyerOffer(
            offer_id=f"off_{candidate.get('candidate_id', 'cand_01')}",
            merchant_id=merchant_id,
            merchant_label=merchant_label,
            product_id=candidate.get("product_id", "prod_01"),
            product_name=candidate.get("product_name", "Travel Gear"),
            category=candidate.get("category", "luggage"),
            price_paise=price_paise,
            currency=candidate.get("currency", "INR"),
            availability=candidate.get("availability", True),
            relevant_attributes=candidate.get("relevant_attributes") or candidate.get("attributes", {}),
            included_items=candidate.get("included_items", []),
            warranty_months=candidate.get("warranty_months", 12),
            delivery_days=candidate.get("delivery_days", 3),
            incentives=candidate.get("incentives", []),
            is_synthetic=False
        )

    async def run_scenario(
        self,
        experiment: PolicyExperiment,
        scenario_id: str,
        intent: BuyerIntent,
        assigned_variant: VariantType,
        competitors: Optional[List[BuyerOffer]] = None,
        persona: BuyerPersonaType = BuyerPersonaType.BALANCED,
        db: Optional[AsyncSession] = None,
        execute_test_mode_orders: bool = False
    ) -> ExperimentObservation:
        """Execute a single scenario under an assigned experimental variant."""
        # 1. Select the assigned proposal candidate
        proposal = (
            experiment.control_proposal_snapshot
            if assigned_variant == VariantType.CONTROL
            else experiment.treatment_proposal_snapshot
        )
        selected_cand = proposal.get("selected_candidate") or proposal.get("candidates", [{}])[0]
        cand_econ = selected_cand.get("economics", {})

        # 2. Build buyer-visible offer
        merchant_offer = self.candidate_to_buyer_offer(
            candidate=selected_cand,
            merchant_id=experiment.merchant_id
        )

        # 3. Competing market offers
        competing_offers = competitors if competitors is not None else get_synthetic_competitor_offers()
        all_candidate_offers = [merchant_offer] + competing_offers

        # 4. Simulate Buyer Choice in AI Buyer Lab (Phase 6)
        sim_result = self.simulator.simulate_selection(
            intent=intent,
            offers=all_candidate_offers,
            persona=persona,
            scenario_id=scenario_id
        )

        is_selected = (sim_result.selected_offer_id == merchant_offer.offer_id)

        # Calculate commercial figures for observation
        revenue = merchant_offer.price_paise if is_selected else 0
        cogs = cand_econ.get("cogs_paise", 0)
        contribution = (revenue - cogs) if is_selected else 0
        margin = float(cand_econ.get("margin_percent", 0.0)) if is_selected else 0.0

        # Optional Phase 5 Execution Gate integration:
        # Executes the assigned variant (Control or Treatment) for this shopper when selected by buyer
        execution_id = None
        order_id = None
        razorpay_order_id = None
        payment_outcome = None
        outcome_type = OutcomeType.SIMULATED

        if is_selected and execute_test_mode_orders and db is not None:
            try:
                exec_req = PolicyExecuteRequest(
                    merchant_id=experiment.merchant_id,
                    proposal_id=proposal.get("proposal_id", f"prop_{uuid.uuid4().hex[:8]}"),
                    candidate_id=selected_cand.get("candidate_id", "cand_01"),
                    idempotency_key=f"exp_{experiment.experiment_id}_{scenario_id}_{assigned_variant.value}"
                )
                exec_res = await self.gate.execute_policy(db=db, request=exec_req)
                execution_id = exec_res.execution_id
                order_id = exec_res.order_id
                razorpay_order_id = exec_res.razorpay_order_id
                payment_outcome = "PENDING"
                outcome_type = OutcomeType.TEST_MODE_OBSERVED
            except Exception as e:
                logger.error("test_mode_execution_failed_in_experiment", error=str(e))

        idempotency_key = f"obs_{experiment.experiment_id}_{scenario_id}_{assigned_variant.value}"

        return ExperimentObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:12]}",
            experiment_id=experiment.experiment_id,
            scenario_id=scenario_id,
            variant=assigned_variant,
            outcome_type=outcome_type,
            buyer_selection_result_id=sim_result.scenario_id,
            selected_offer_id=sim_result.selected_offer_id,
            is_selected=is_selected,
            execution_id=execution_id,
            order_id=order_id,
            razorpay_order_id=razorpay_order_id,
            payment_outcome=payment_outcome,
            revenue_paise=revenue,
            contribution_paise=contribution,
            margin_percent=margin,
            guardrail_violations=[],
            idempotency_key=idempotency_key
        )
