import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from apps.api.core.database import AsyncSessionLocal
from domain.models import MerchantPolicyVersionRecord
from sqlalchemy import select, and_

async def main():
    candidates = [
        # Atlas Travel Gear Candidates
        {
            "merchant_id": "merch_atlas_travel",
            "policy_id": "cand_54256751",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "CANDIDATE",
            "strategy_type": "COMPLEMENTARY_BUNDLE",
            "product_ids_json": ["prod_atlas_daypack", "prod_atlas_raincover"],
            "incentive_json": {"incentive_type": "bundle", "discount_percent": "0.00"},
            "rationale": "Explored candidate: Daypack + Raincover bundle recommendation"
        },
        {
            "merchant_id": "merch_atlas_travel",
            "policy_id": "cand_1c7187fd",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "CANDIDATE",
            "strategy_type": "SINGLE_PRODUCT",
            "product_ids_json": ["prod_atlas_daypack"],
            "incentive_json": {"incentive_type": "none"},
            "rationale": "Explored candidate: Direct Daypack offering"
        },
        {
            "merchant_id": "merch_atlas_travel",
            "policy_id": "cand_cdc51d6d",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "CANDIDATE",
            "strategy_type": "ALTERNATIVE_PRODUCT",
            "product_ids_json": ["prod_atlas_organizer"],
            "incentive_json": {"incentive_type": "none"},
            "rationale": "Explored candidate: Packing cubes alternative"
        },
        # Alpha Outfitters Candidates & History
        {
            "merchant_id": "merch_alpha",
            "policy_id": "cand_base_no_offer",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "ROLLED_BACK",
            "strategy_type": "NO_OFFER",
            "product_ids_json": [],
            "incentive_json": None,
            "rationale": "Previous active baseline prior to roll_25cd3c747f66"
        },
        {
            "merchant_id": "merch_alpha",
            "policy_id": "cand_41a31201",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "CANDIDATE",
            "strategy_type": "SINGLE_PRODUCT",
            "product_ids_json": [],
            "incentive_json": None,
            "rationale": "Explored candidate: Alpha single product offer"
        },
        {
            "merchant_id": "merch_alpha",
            "policy_id": "cand_561b87c7",
            "policy_version": "merchant-policy/v1",
            "lifecycle_status": "CANDIDATE",
            "strategy_type": "SINGLE_PRODUCT",
            "product_ids_json": [],
            "incentive_json": None,
            "rationale": "Explored candidate: Alpha alternative product offer"
        }
    ]

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        added = 0
        for c in candidates:
            stmt = select(MerchantPolicyVersionRecord).where(
                and_(
                    MerchantPolicyVersionRecord.merchant_id == c["merchant_id"],
                    MerchantPolicyVersionRecord.policy_id == c["policy_id"],
                    MerchantPolicyVersionRecord.policy_version == c["policy_version"]
                )
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if not existing:
                rec = MerchantPolicyVersionRecord(
                    id=f"pver_{c['merchant_id']}_{c['policy_id']}_{c['policy_version']}",
                    merchant_id=c["merchant_id"],
                    policy_id=c["policy_id"],
                    policy_version=c["policy_version"],
                    lifecycle_status=c["lifecycle_status"],
                    strategy_type=c["strategy_type"],
                    product_ids_json=c["product_ids_json"],
                    incentive_json=c["incentive_json"],
                    rationale=c["rationale"],
                    provenance_json={"origin": "catalog_exploration", "seeded": True},
                    created_at=now,
                    updated_at=now
                )
                db.add(rec)
                added += 1
        await db.commit()
        print(f"Added {added} candidate version records.")

if __name__ == "__main__":
    asyncio.run(main())
