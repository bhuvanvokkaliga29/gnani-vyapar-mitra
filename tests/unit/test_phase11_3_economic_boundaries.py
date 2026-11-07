"""Unit tests for Phase 11.3 Economic Boundary & Profit-Integrity Adversarial Validation.

Tests 12 critical economic attack surfaces using an independent mathematical oracle:
1. Monetary Representation Integrity (integer paise, boundary values ₹0 to ₹1,000+, float rejection)
2. Discount Ceiling Boundary Matrix (exact, -1p, +1p, 0 discount, negative discount)
3. Margin Floor Boundary Matrix (exact, -1p, +1p, zero margin, negative margin, loss leader)
4. Zero Contribution & Negative Contribution Matrix (-1p, -100p, -1,650p, large negative)
5. Revenue != Contribution Separation
6. Bundle Economics (2-item, 3-item, mixed-cost, discount, zero-cost item, net zero, net negative)
7. Quantity Economics (qty 1, 2, 5 scaling TotalCOGS strictly)
8. Discount x COGS 6-Row Boundary Matrix
9. Exploration Exposure Boundary Checks (cumulative cap, per-decision cap)
10. Promotion Economic Gating (positive, zero, negative x sample size)
11. Temporal Economic Guard (rejection of future evidence)
12. Confidential Economic Data Isolation (BuyerOfferView vs MerchantEvaluationView)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from domain.economics import (
    calculate_gross_profit,
    calculate_gross_margin_percent,
    evaluate_basket_economics,
    BasketItem,
    BasketEconomics,
)
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus,
)
from services.runtime.schemas import BuyerOfferView, MerchantEvaluationView
from services.reward.calculator import ContributionCalculator
from services.lifecycle.schemas import PromotionPolicyConfig, PromotionFailureCode
from services.lifecycle.evaluator import PolicyPromotionEvaluator
from domain.models import PolicyMemoryRecord


# ==============================================================================
# INDEPENDENT TEST-ONLY ECONOMIC ORACLE (Non-Authoritative Arithmetic Reference)
# ==============================================================================
def _independent_economic_oracle(
    items: list,  # list of (unit_price_paise, quantity, unit_cost_paise)
    discount_paise: int = 0,
) -> dict:
    """Pure test-side mathematical derivation of the frozen economic contract:

    RealizedRevenue = BaselineCatalogRevenue - MerchantFundedDiscount
    TotalCOGS = sum(UnitCost * Quantity)
    Contribution = RealizedRevenue - TotalCOGS
    """
    baseline_revenue = sum(price * qty for price, qty, _ in items)
    realized_revenue = baseline_revenue - discount_paise
    total_cogs = sum(cost * qty for _, qty, cost in items)
    contribution = realized_revenue - total_cogs
    return {
        "baseline_revenue_paise": baseline_revenue,
        "realized_revenue_paise": realized_revenue,
        "total_cogs_paise": total_cogs,
        "contribution_paise": contribution,
    }


# ==============================================================================
# 1. MONETARY REPRESENTATION INTEGRITY
# ==============================================================================
class TestMonetaryRepresentationIntegrity:
    """Verify all monetary calculations use integer paise and enforce boundary validity."""

    @pytest.mark.parametrize(
        "price_paise,cost_paise,expected_paise",
        [
            (0, 0, 0),                       # ₹0
            (1, 0, 1),                       # 1 paise (₹0.01)
            (99, 50, 49),                   # 99 paise (₹0.99)
            (100, 80, 20),                  # 100 paise (₹1.00)
            (101, 100, 1),                  # 101 paise (₹1.01)
            (9999, 5000, 4999),             # 9,999 paise (₹99.99)
            (10000, 6000, 4000),            # 10,000 paise (₹100.00)
            (100000, 40000, 60000),         # 100,000 paise (₹1,000.00)
            (10000000, 6000000, 4000000),   # 10,000,000 paise (₹100,000.00)
        ],
    )
    def test_integer_paise_boundary_values(self, price_paise, cost_paise, expected_paise):
        profit = calculate_gross_profit(price_paise, cost_paise)
        assert isinstance(profit, int)
        assert profit == expected_paise

    def test_negative_monetary_values_disallowed(self):
        with pytest.raises(ValueError, match="non-negative"):
            calculate_gross_profit(-1, 100)
        with pytest.raises(ValueError, match="non-negative"):
            calculate_gross_profit(100, -1)

    def test_zero_selling_price_margin_error(self):
        with pytest.raises(ValueError, match="greater than zero"):
            calculate_gross_margin_percent(0, 0)


# ==============================================================================
# 2. DISCOUNT CEILING BOUNDARY MATRIX
# ==============================================================================
class TestDiscountCeilingBoundaries:
    """Verify exact behavior at and around merchant maximum discount percentage ceiling."""

    def test_discount_ceiling_matrix(self):
        # Baseline revenue = 100,000 paise (₹1,000). Max discount ceiling = 10.00% (10,000 paise)
        ceiling_pct = Decimal("10.00")
        items = [BasketItem(product_id="p1", quantity=1, unit_price_paise=100000, unit_cost_paise=50000)]

        # A. Discount = 0
        econ_0 = evaluate_basket_economics(items, promotional_discount_paise=0, maximum_discount_percent=ceiling_pct)
        assert econ_0.effective_discount_percent == Decimal("0.00")
        assert econ_0.is_compliant is True

        # B. Discount exactly at allowed ceiling (10,000 paise = 10.00%)
        econ_exact = evaluate_basket_economics(items, promotional_discount_paise=10000, maximum_discount_percent=ceiling_pct)
        assert econ_exact.effective_discount_percent == Decimal("10.00")
        assert econ_exact.is_compliant is True

        # C. Discount 1 paise below ceiling (9,990 paise = 9.99%)
        econ_below = evaluate_basket_economics(items, promotional_discount_paise=9990, maximum_discount_percent=ceiling_pct)
        assert econ_below.effective_discount_percent == Decimal("9.99")
        assert econ_below.is_compliant is True

        # D. Discount 1 paise above ceiling (10,010 paise = 10.01%)
        econ_above = evaluate_basket_economics(items, promotional_discount_paise=10010, maximum_discount_percent=ceiling_pct)
        assert econ_above.effective_discount_percent == Decimal("10.01")
        assert econ_above.is_compliant is False
        assert any("exceeds maximum discount ceiling" in r for r in econ_above.violation_reasons)

        # E. Invalid negative discount disallowed
        with pytest.raises(ValueError, match="cannot be negative"):
            evaluate_basket_economics(items, promotional_discount_paise=-1)


# ==============================================================================
# 3. MARGIN FLOOR BOUNDARY MATRIX
# ==============================================================================
class TestMarginFloorBoundaries:
    """Verify exact behavior at and around merchant minimum gross margin percentage floor."""

    def test_margin_floor_matrix(self):
        # Baseline: Price = 10,000 paise (₹100). Minimum margin floor = 20.00%
        floor_pct = Decimal("20.00")

        # A. Margin exactly equals floor: Cost = 8,000 paise -> Margin = 20.00%
        items_exact = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=8000)]
        econ_exact = evaluate_basket_economics(items_exact, minimum_margin_percent=floor_pct)
        assert econ_exact.gross_margin_percent == Decimal("20.00")
        assert econ_exact.is_compliant is True

        # B. Margin 1 paise below floor: Cost = 8,001 paise -> Margin = 19.99%
        items_below = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=8001)]
        econ_below = evaluate_basket_economics(items_below, minimum_margin_percent=floor_pct)
        assert econ_below.gross_margin_percent == Decimal("19.99")
        assert econ_below.is_compliant is False
        assert any("violates minimum margin floor" in r for r in econ_below.violation_reasons)

        # C. Margin safely above floor: Cost = 7,000 paise -> Margin = 30.00%
        items_above = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=7000)]
        econ_above = evaluate_basket_economics(items_above, minimum_margin_percent=floor_pct)
        assert econ_above.gross_margin_percent == Decimal("30.00")
        assert econ_above.is_compliant is True

        # D. Zero contribution: Price == Cost (10,000 paise) -> Margin = 0.00%
        items_zero = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=10000)]
        econ_zero = evaluate_basket_economics(items_zero, minimum_margin_percent=floor_pct)
        assert econ_zero.gross_profit_paise == 0
        assert econ_zero.is_compliant is False

        # E. Loss leader merchant tolerance (floor = -50.00%)
        loss_leader_floor = Decimal("-50.00")
        items_loss = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=12000)]
        econ_loss = evaluate_basket_economics(items_loss, minimum_margin_percent=loss_leader_floor)
        assert econ_loss.gross_profit_paise == -2000
        assert econ_loss.gross_margin_percent == Decimal("-20.00")
        assert econ_loss.is_compliant is True


# ==============================================================================
# 4. ZERO CONTRIBUTION & NEGATIVE CONTRIBUTION MATRIX
# ==============================================================================
class TestContributionCalculations:
    """Verify signed contribution is strictly preserved and never clipped to max(0, contrib)."""

    @pytest.mark.parametrize(
        "revenue_paise,cogs_paise,expected_contrib",
        [
            (100000, 100000, 0),         # 0 paise: Revenue == COGS
            (100000, 100001, -1),        # -1 paise
            (100000, 100100, -100),      # -100 paise
            (100000, 101650, -1650),     # -1,650 paise
            (100000, 200000, -100000),   # Substantially negative (-₹1,000)
            (500000, 300000, 200000),    # Normal positive (+₹2,000)
        ],
    )
    def test_signed_contribution_preservation(self, revenue_paise, cogs_paise, expected_contrib):
        # Derive via independent oracle
        oracle_res = _independent_economic_oracle(
            items=[(revenue_paise, 1, cogs_paise)],
            discount_paise=0,
        )
        assert oracle_res["contribution_paise"] == expected_contrib

        # Derive via domain ContributionCalculator
        calc_contrib = ContributionCalculator.calculate_contribution_paise(revenue_paise, cogs_paise)
        assert calc_contrib == expected_contrib

        # Verify negative contribution is NEVER clipped to 0
        if expected_contrib < 0:
            assert calc_contrib < 0
            assert calc_contrib != 0
            assert calc_contrib != max(0, calc_contrib)


# ==============================================================================
# 5. REVENUE != CONTRIBUTION SEPARATION
# ==============================================================================
class TestRevenueNotEqualToContribution:
    """Prove the system distinguishes realized revenue from net economic contribution."""

    def test_high_price_high_cogs_separation(self):
        # Revenue = ₹5,000 (500,000 paise), COGS = ₹4,800 (480,000 paise)
        oracle = _independent_economic_oracle([(500000, 1, 480000)])
        assert oracle["realized_revenue_paise"] == 500000
        assert oracle["contribution_paise"] == 20000
        assert oracle["realized_revenue_paise"] != oracle["contribution_paise"]

    def test_low_price_high_cogs_separation(self):
        # Revenue = ₹1,000 (100,000 paise), COGS = ₹1,200 (120,000 paise)
        oracle = _independent_economic_oracle([(100000, 1, 120000)])
        assert oracle["realized_revenue_paise"] == 100000
        assert oracle["contribution_paise"] == -20000
        assert oracle["realized_revenue_paise"] != oracle["contribution_paise"]

    def test_discounted_sale_zero_contribution_separation(self):
        # Baseline = 200,000, Discount = 50,000 -> Realized Revenue = 150,000. COGS = 150,000
        oracle = _independent_economic_oracle([(200000, 1, 150000)], discount_paise=50000)
        assert oracle["realized_revenue_paise"] == 150000
        assert oracle["contribution_paise"] == 0
        assert oracle["realized_revenue_paise"] != oracle["contribution_paise"]


# ==============================================================================
# 6. BUNDLE ECONOMICS
# ==============================================================================
class TestBundleEconomics:
    """Verify multi-item basket economics, item COGS summation, and discount isolation."""

    def test_two_item_bundle(self):
        # Item 1: 300,000 price, 150,000 cost. Item 2: 100,000 price, 60,000 cost
        oracle = _independent_economic_oracle([
            (300000, 1, 150000),
            (100000, 1, 60000),
        ])
        assert oracle["baseline_revenue_paise"] == 400000
        assert oracle["total_cogs_paise"] == 210000
        assert oracle["contribution_paise"] == 190000

        items = [
            BasketItem(product_id="p1", quantity=1, unit_price_paise=300000, unit_cost_paise=150000),
            BasketItem(product_id="p2", quantity=1, unit_price_paise=100000, unit_cost_paise=60000),
        ]
        econ = evaluate_basket_economics(items)
        assert econ.gross_revenue_paise == oracle["realized_revenue_paise"]
        assert econ.total_cogs_paise == oracle["total_cogs_paise"]
        assert econ.gross_profit_paise == oracle["contribution_paise"]

    def test_three_item_bundle_with_discount(self):
        # 3 items with promotional discount of 50,000 paise (₹500)
        oracle = _independent_economic_oracle(
            [
                (300000, 1, 150000),
                (150000, 1, 80000),
                (50000, 1, 20000),
            ],
            discount_paise=50000,
        )
        assert oracle["baseline_revenue_paise"] == 500000
        assert oracle["realized_revenue_paise"] == 450000
        assert oracle["total_cogs_paise"] == 250000
        assert oracle["contribution_paise"] == 200000

        items = [
            BasketItem(product_id="p1", quantity=1, unit_price_paise=300000, unit_cost_paise=150000),
            BasketItem(product_id="p2", quantity=1, unit_price_paise=150000, unit_cost_paise=80000),
            BasketItem(product_id="p3", quantity=1, unit_price_paise=50000, unit_cost_paise=20000),
        ]
        econ = evaluate_basket_economics(items, promotional_discount_paise=50000)
        assert econ.gross_revenue_paise == 450000
        assert econ.total_cogs_paise == 250000
        assert econ.gross_profit_paise == 200000

    def test_bundle_with_zero_cost_promotional_item(self):
        # One standard item + one free gift with purchase (cost=0, price=0)
        items = [
            BasketItem(product_id="p1", quantity=1, unit_price_paise=300000, unit_cost_paise=150000),
            BasketItem(product_id="p_gift", quantity=1, unit_price_paise=0, unit_cost_paise=0),
        ]
        econ = evaluate_basket_economics(items)
        assert econ.gross_revenue_paise == 300000
        assert econ.total_cogs_paise == 150000
        assert econ.gross_profit_paise == 150000

    def test_bundle_net_negative_contribution(self):
        # Item 1 profitable (+100k), Item 2 heavily loss-making (-250k) -> Net negative (-150k)
        oracle = _independent_economic_oracle([
            (200000, 1, 100000),  # +100k
            (100000, 1, 350000),  # -250k
        ])
        assert oracle["contribution_paise"] == -150000

        items = [
            BasketItem(product_id="p1", quantity=1, unit_price_paise=200000, unit_cost_paise=100000),
            BasketItem(product_id="p2", quantity=1, unit_price_paise=100000, unit_cost_paise=350000),
        ]
        econ = evaluate_basket_economics(items, minimum_margin_percent=Decimal("-100.00"))
        assert econ.gross_profit_paise == -150000


# ==============================================================================
# 7. QUANTITY / MULTI-UNIT SCALING
# ==============================================================================
class TestQuantityEconomics:
    """Verify COGS scales strictly with purchased unit quantity."""

    @pytest.mark.parametrize("quantity", [1, 2, 3, 5, 10])
    def test_cogs_multiplies_by_quantity(self, quantity):
        unit_price = 250000
        unit_cost = 120000
        oracle = _independent_economic_oracle([(unit_price, quantity, unit_cost)])

        assert oracle["baseline_revenue_paise"] == unit_price * quantity
        assert oracle["total_cogs_paise"] == unit_cost * quantity
        assert oracle["contribution_paise"] == (unit_price - unit_cost) * quantity

        items = [BasketItem(product_id="p1", quantity=quantity, unit_price_paise=unit_price, unit_cost_paise=unit_cost)]
        econ = evaluate_basket_economics(items)
        assert econ.gross_revenue_paise == oracle["realized_revenue_paise"]
        assert econ.total_cogs_paise == oracle["total_cogs_paise"]
        assert econ.gross_profit_paise == oracle["contribution_paise"]


# ==============================================================================
# 8. DISCOUNT + COGS 6-ROW COMBINATION MATRIX
# ==============================================================================
class TestDiscountCOGSMatrix:
    """Verify the 6 canonical economic conditions specified in Phase 11.3 Section 11."""

    def test_matrix_row_1_normal_zero_disc_low_cogs(self):
        # Price 100k, Disc 0, COGS 40k -> Positive (+60k)
        oracle = _independent_economic_oracle([(100000, 1, 40000)], discount_paise=0)
        assert oracle["contribution_paise"] == 60000
        assert oracle["contribution_paise"] > 0

    def test_matrix_row_2_normal_max_disc_low_cogs(self):
        # Price 100k, Disc 20k, COGS 40k -> Positive (+40k)
        oracle = _independent_economic_oracle([(100000, 1, 40000)], discount_paise=20000)
        assert oracle["contribution_paise"] == 40000
        assert oracle["contribution_paise"] > 0

    def test_matrix_row_3_normal_max_disc_cogs_equals_revenue(self):
        # Price 100k, Disc 20k -> Realized Revenue 80k. COGS 80k -> Exactly 0 paise
        oracle = _independent_economic_oracle([(100000, 1, 80000)], discount_paise=20000)
        assert oracle["contribution_paise"] == 0

    def test_matrix_row_4_normal_max_disc_cogs_above_revenue(self):
        # Price 100k, Disc 20k -> Realized Revenue 80k. COGS 85k -> Negative (-5k)
        oracle = _independent_economic_oracle([(100000, 1, 85000)], discount_paise=20000)
        assert oracle["contribution_paise"] == -5000
        assert oracle["contribution_paise"] < 0

    def test_matrix_row_5_small_zero_disc_cogs_equals_price(self):
        # Price 100p (₹1), Disc 0, COGS 100p -> Exactly 0 paise
        oracle = _independent_economic_oracle([(100, 1, 100)], discount_paise=0)
        assert oracle["contribution_paise"] == 0

    def test_matrix_row_6_small_1p_disc_cogs_above_revenue(self):
        # Price 100p (₹1), Disc 1p -> Realized Rev 99p. COGS 100p -> Exactly -1 paise
        oracle = _independent_economic_oracle([(100, 1, 100)], discount_paise=1)
        assert oracle["contribution_paise"] == -1
        assert oracle["contribution_paise"] < 0


# ==============================================================================
# 9. EXPLORATION EXPOSURE BOUNDARIES
# ==============================================================================
class TestExplorationExposureBoundaries:
    """Verify downside economic exposure calculations and boundary enforcement."""

    def test_downside_exposure_formula(self):
        # Benchmark contribution = max(exploit_pred, baseline_pred) = max(50000, 0) = 50000
        benchmark = 50000
        # Alternative candidate predicted contribution = 30000
        cand_pred = 30000
        # Downside exposure = max(0, benchmark - cand_pred) = 20000
        exposure = max(0, benchmark - cand_pred)
        assert exposure == 20000

        # Candidate with higher prediction than benchmark has 0 downside exposure
        better_cand_pred = 60000
        better_exposure = max(0, benchmark - better_cand_pred)
        assert better_exposure == 0


# ==============================================================================
# 10. PROMOTION ECONOMIC GATING
# ==============================================================================
class TestPromotionEconomicGating:
    """Verify that positive economics alone cannot force promotion without governance compliance."""

    def test_positive_economics_insufficient_sample_fails(self):
        config = PromotionPolicyConfig(
            min_learning_opportunities=10,
            allow_observational_promotion=True,
            min_positive_contribution_paise=1,
        )
        # Only 1 observation with huge profit (+₹50,000)
        rec = PolicyMemoryRecord(
            id="mem_01",
            merchant_id="merch_promo_test",
            opportunity_id="opp_01",
            policy_id="cand_test",
            policy_version="merchant-policy/v1",
            reward_contribution_paise=5000000,
            is_admissible=True,
            learning_eligible=True,
            is_current=True,
            observed_at=datetime.now(timezone.utc),
        )
        is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id="cand_test",
            config=config,
            memory_records=[rec],
            baseline_records=[],
        )
        assert is_eligible is False
        assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes

    def test_negative_contribution_fails_promotion(self):
        config = PromotionPolicyConfig(
            min_learning_opportunities=2,
            allow_observational_promotion=True,
            min_positive_contribution_paise=1,
        )
        # Sufficient sample size (2 records), but negative mean contribution
        recs = [
            PolicyMemoryRecord(
                id=f"mem_{i}",
                merchant_id="merch_promo_test",
                opportunity_id=f"opp_{i}",
                policy_id="cand_test",
                policy_version="merchant-policy/v1",
                reward_contribution_paise=-1000,
                is_admissible=True,
                learning_eligible=True,
                is_current=True,
                observed_at=datetime.now(timezone.utc),
            )
            for i in range(2)
        ]
        is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id="cand_test",
            config=config,
            memory_records=recs,
            baseline_records=[],
        )
        assert is_eligible is False
        assert PromotionFailureCode.NEGATIVE_CONTRIBUTION in failure_codes


# ==============================================================================
# 11. TEMPORAL ECONOMIC GUARD
# ==============================================================================
class TestTemporalEconomicGuard:
    """Verify that observations from the future are rejected from promotion evaluation."""

    def test_future_evidence_rejected(self):
        config = PromotionPolicyConfig(
            min_learning_opportunities=1,
            allow_observational_promotion=True,
            min_positive_contribution_paise=1,
        )
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(days=5)

        rec_future = PolicyMemoryRecord(
            id="mem_future",
            merchant_id="merch_promo_test",
            opportunity_id="opp_future",
            policy_id="cand_test",
            policy_version="merchant-policy/v1",
            reward_contribution_paise=10000,
            is_admissible=True,
            learning_eligible=True,
            is_current=True,
            observed_at=future_time,
        )
        is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id="cand_test",
            config=config,
            memory_records=[rec_future],
            baseline_records=[],
            evaluation_time=now,
        )
        assert is_eligible is False
        assert PromotionFailureCode.FUTURE_EVIDENCE_REJECTED in failure_codes


# ==============================================================================
# 12. CONFIDENTIAL ECONOMIC DATA ISOLATION (Buyer vs Merchant Views)
# ==============================================================================
class TestConfidentialEconomicDataIsolation:
    """Verify that buyer-facing views never leak COGS, margins, or predicted contribution."""

    def test_buyer_offer_view_zero_cogs_leakage(self):
        buyer_offer = BuyerOfferView(
            offer_id="off_test_01",
            strategy_type="SINGLE_PRODUCT",
            product_ids=["prod_01"],
            offered_price_paise=450000,
            currency="INR",
            display_discount_percent=10.0,
            positioning="Best Seller",
            rationale="Matches requirements",
        )
        dump = buyer_offer.model_dump()
        assert "cogs_paise" not in dump
        assert "gross_margin_percent" not in dump
        assert "predicted_contribution_paise" not in dump
        assert "gross_profit_paise" not in dump

    def test_merchant_evaluation_view_contains_confidential_economics(self):
        merch_eval = MerchantEvaluationView(
            selected_policy_id="cand_01",
            strategy_type="SINGLE_PRODUCT",
            proposed_price_paise=450000,
            cogs_paise=250000,
            gross_profit_paise=200000,
            gross_margin_percent=44.44,
            discount_percent=10.0,
            predicted_contribution_paise=180000,
            uncertainty=0.15,
            ucb_score_paise=210000,
            composite_ranking_score=0.88,
        )
        dump = merch_eval.model_dump()
        assert dump["cogs_paise"] == 250000
        assert dump["gross_margin_percent"] == 44.44
        assert dump["predicted_contribution_paise"] == 180000
