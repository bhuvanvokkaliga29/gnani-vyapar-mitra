import asyncio
import sys
import os
import json

sys.path.insert(0, os.getcwd())

from apps.api.core.database import AsyncSessionLocal
from domain.models import PolicyMemoryRecord, CanonicalDecisionRecord
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        dec_stmt = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.merchant_id == "merch_atlas_travel")
        dec_rows = (await db.execute(dec_stmt)).scalars().all()
        print(f"Decisions for Atlas: {len(dec_rows)}")
        seen = {}
        for d in dec_rows:
            pol_id = d.selected_policy_id
            if pol_id not in seen:
                seen[pol_id] = {
                    "strategy": d.selected_strategy_type,
                    "mode": d.decision_mode,
                    "price": d.proposed_price_paise,
                }
        for pol, info in seen.items():
            print(f"  Policy: {pol:25} | Strat: {str(info['strategy']):20} | Price: {info['price']}")

if __name__ == "__main__":
    asyncio.run(main())
