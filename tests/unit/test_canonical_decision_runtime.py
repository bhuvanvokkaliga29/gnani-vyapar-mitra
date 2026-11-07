"""Unit Tests for Phase 9.1 Canonical Decision Runtime Service Layer.

Contract: canonical-decision/v1
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.runtime.service import CanonicalDecisionRuntime
from services.runtime.schemas import (
    CANONICAL_DECISION_SCHEMA_VERSION,
    CanonicalDecisionRequest
)
from services.runtime.errors import (
    IncompatibleRuntimeVersionError,
    MerchantInactiveError
)
from services.commerce_service import MerchantNotFoundError
from domain.models import Merchant


@pytest.mark.asyncio
async def test_incompatible_runtime_version_rejected():
    """Request with unsupported version raises IncompatibleRuntimeVersionError."""
    db = AsyncMock()
    req = CanonicalDecisionRequest(
        merchant_id="m1",
        raw_prompt="backpack",
        runtime_version="canonical-decision/v99"
    )
    with pytest.raises(IncompatibleRuntimeVersionError):
        await CanonicalDecisionRuntime.decide(db, req)


@pytest.mark.asyncio
async def test_merchant_not_found_raises():
    """Non-existent merchant raises MerchantNotFoundError."""
    db = AsyncMock()
    req = CanonicalDecisionRequest(merchant_id="nonexistent_m", raw_prompt="backpack")
    with patch.object(CanonicalDecisionRuntime._commerce_service, "get_merchant", return_value=None):
        with pytest.raises(MerchantNotFoundError):
            await CanonicalDecisionRuntime.decide(db, req)


@pytest.mark.asyncio
async def test_inactive_merchant_raises():
    """Inactive merchant raises MerchantInactiveError."""
    db = AsyncMock()
    inactive_merchant = Merchant(id="m_inactive", name="Inactive", currency="INR", status="SUSPENDED")
    req = CanonicalDecisionRequest(merchant_id="m_inactive", raw_prompt="backpack")
    with patch.object(CanonicalDecisionRuntime._commerce_service, "get_merchant", return_value=inactive_merchant):
        with pytest.raises(MerchantInactiveError):
            await CanonicalDecisionRuntime.decide(db, req)
