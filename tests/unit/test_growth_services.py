"""
Unit tests for Merchant Growth Agent Services:
- MarketplaceGrowthService (Multi-channel unit economics & listing generation)
- OwnerPolicyService (Natural language policy parser)
- SalesAgentService (Adversarial injection protection & margin guardrails)
- CampaignService (Community group deals margin verification)
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from domain.models import Merchant, Product
from domain.growth_models import ChannelConfig
from services.marketplace.service import MarketplaceGrowthService
from services.owner_policy.service import OwnerPolicyService
from services.campaigns.service import CampaignService
from services.sales_agent.service import SalesAgentService


@pytest.fixture
def sample_merchant():
    return Merchant(
        id="merch_test_growth",
        name="Artisan Crafts Co",
        currency="INR",
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("20.00")
    )


@pytest.fixture
def sample_product(sample_merchant):
    return Product(
        id="prod_bag_01",
        merchant_id=sample_merchant.id,
        name="Handcrafted Leather Messenger Bag",
        sku="BAG-LTH-01",
        cost_paise=120000,    # ₹1200
        price_paise=249900,   # ₹2499
        is_active=True,
        inventory_quantity=25
    )


@pytest.fixture
def sample_channels(sample_merchant):
    amazon = ChannelConfig(
        merchant_id=sample_merchant.id,
        channel_id="AMAZON",
        name="Amazon India",
        fee_percent=Decimal("15.00"),
        fixed_fee_paise=2500,
        shipping_base_paise=7000,
        return_rate_percent=Decimal("18.00"),
        return_cost_paise=5000,
        ad_cost_paise=12000,
        verification_status="VERIFY",
        audience_fit="Broad national reach",
        is_active=True
    )
    direct = ChannelConfig(
        merchant_id=sample_merchant.id,
        channel_id="DIRECT_WHATSAPP",
        name="Direct WhatsApp",
        fee_percent=Decimal("2.00"),
        fixed_fee_paise=0,
        shipping_base_paise=5000,
        return_rate_percent=Decimal("5.00"),
        return_cost_paise=2000,
        ad_cost_paise=8000,
        verification_status="SAMPLE",
        audience_fit="Repeat buyers",
        is_active=True
    )
    return [amazon, direct]


class TestMarketplaceGrowthService:
    def test_unit_economics_amazon_vs_direct(self, sample_product, sample_channels):
        amazon_cfg = next(c for c in sample_channels if c.channel_id == "AMAZON")
        direct_cfg = next(c for c in sample_channels if c.channel_id == "DIRECT_WHATSAPP")

        amazon_econ = MarketplaceGrowthService.calculate_unit_economics(
            price_paise=sample_product.price_paise,
            cost_paise=sample_product.cost_paise,
            channel=amazon_cfg,
            min_margin_percent=Decimal("25.00")
        )

        direct_econ = MarketplaceGrowthService.calculate_unit_economics(
            price_paise=sample_product.price_paise,
            cost_paise=sample_product.cost_paise,
            channel=direct_cfg,
            min_margin_percent=Decimal("25.00")
        )

        # Amazon has higher total fees (15% + 2500 paise) than Direct WhatsApp (2% gateway)
        assert amazon_econ["fees_paise"] > direct_econ["fees_paise"]
        # Direct WhatsApp delivers higher net contribution
        assert direct_econ["net_contribution_paise"] > amazon_econ["net_contribution_paise"]
        # Direct WhatsApp decision is DIRECT_CHANNEL
        assert direct_econ["decision"] == "DIRECT_CHANNEL"

    def test_hold_decision_when_margin_floor_violated(self, sample_channels):
        amazon_cfg = next(c for c in sample_channels if c.channel_id == "AMAZON")

        # Low price relative to high COGS: ₹1000 price, ₹800 COGS
        # Margin will be severely below 25% floor once Amazon fees & shipping are deducted
        econ = MarketplaceGrowthService.calculate_unit_economics(
            price_paise=100000,
            cost_paise=80000,
            channel=amazon_cfg,
            min_margin_percent=Decimal("25.00")
        )

        assert econ["decision"] == "HOLD"
        assert econ["net_contribution_paise"] < 0 or econ["margin_percent"] < 25.0

    def test_listing_pack_generation_no_hallucination(self, sample_product):
        pack = MarketplaceGrowthService.generate_listing_pack(
            product=sample_product,
            channel_id="AMAZON"
        )

        assert pack["product_id"] == sample_product.id
        assert pack["sku"] == sample_product.sku
        assert len(pack["bullet_points"]) >= 3
        # Grounded in real product name
        assert sample_product.name in pack["title"]
        assert len(pack["photo_checklist"]) >= 3

    def test_ondc_beckn_json_schema_compliance(self, sample_product, sample_merchant):
        beckn = MarketplaceGrowthService.export_ondc_beckn_json(
            product=sample_product,
            merchant=sample_merchant
        )

        assert "context" in beckn
        assert beckn["context"]["domain"] == "nic2004:52110"
        assert beckn["context"]["action"] == "on_search"
        catalog = beckn["message"]["catalog"]
        assert catalog["bpp/descriptor"]["name"] == sample_merchant.name
        items = catalog["bpp/providers"][0]["items"]
        assert items[0]["id"] == sample_product.id
        assert items[0]["price"]["value"] == f"{sample_product.price_paise / 100:.2f}"


class TestOwnerPolicyService:
    def test_natural_language_parsing(self):
        text = "Never sell below 20% margin, max discount of 15%, and ask approval for discounts above 8%"
        parsed = OwnerPolicyService.parse_natural_language_policy(text)

        assert parsed["minimum_margin_percent"] == 20.0
        assert parsed["maximum_discount_percent"] == 15.0
        assert parsed["approval_threshold_percent"] == 8.0

    def test_natural_language_default_fallback(self):
        text = "Just make sure we make good profits"
        parsed = OwnerPolicyService.parse_natural_language_policy(text)

        # Defaults to safe conservative guardrails
        assert parsed["minimum_margin_percent"] == 25.0
        assert parsed["maximum_discount_percent"] == 10.0


class TestCampaignService:
    @pytest.mark.asyncio
    async def test_group_deal_margin_floor_enforcement(self, sample_merchant, sample_product):
        mock_db = AsyncMock()

        # Mock DB queries
        mock_exec_merchant = MagicMock()
        mock_exec_merchant.scalar_one_or_none.return_value = sample_merchant

        mock_exec_product = MagicMock()
        mock_exec_product.scalar_one_or_none.return_value = sample_product

        mock_db.execute.side_effect = [mock_exec_merchant, mock_exec_product]

        # Product COGS = ₹1200 (120,000 paise). 25% margin requires price >= ₹1600 (160,000 paise)
        # Attempt group deal at ₹1300 (130,000 paise) -> Margin is (1300-1200)/1300 = 7.7% < 25% floor
        with pytest.raises(ValueError) as excinfo:
            await CampaignService.create_group_deal(
                db=mock_db,
                merchant_id=sample_merchant.id,
                target_group_name="College Batch",
                product_id=sample_product.id,
                min_threshold_units=10,
                discounted_price_paise=130000
            )

        assert "violating merchant minimum margin floor" in str(excinfo.value)
