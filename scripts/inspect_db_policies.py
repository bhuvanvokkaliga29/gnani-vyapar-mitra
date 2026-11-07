import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())

from apps.api.core.database import AsyncSessionLocal
from domain.models import MerchantPolicyVersionRecord, MerchantActivePolicy, PolicyMemoryRecord, PolicyLifecycleAuditRecord
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        v_rows = (await db.execute(select(MerchantPolicyVersionRecord))).scalars().all()
        print(f"=== Total Version Records: {len(v_rows)} ===")
        for v in v_rows:
            print(f"  Merch: {v.merchant_id:20} | Pol: {v.policy_id:22} | Ver: {v.policy_version:15} | Status: {v.lifecycle_status}")

        a_rows = (await db.execute(select(MerchantActivePolicy))).scalars().all()
        print(f"\n=== Active Policies: {len(a_rows)} ===")
        for a in a_rows:
            print(f"  Merch: {a.merchant_id:20} | Pol: {a.policy_id:22} | Ver: {a.policy_version:15} | PromId: {a.promotion_id}")

        aud_rows = (await db.execute(select(PolicyLifecycleAuditRecord))).scalars().all()
        print(f"\n=== Audit Transitions: {len(aud_rows)} ===")
        for aud in aud_rows:
            print(f"  Merch: {aud.merchant_id:20} | Id: {aud.id:20} | Type: {aud.transition_type:10} | Prev: {str(aud.previous_active_policy_id):20} | Result: {str(aud.resulting_active_policy_id):20} | Status: {aud.promotion_status}")

        m_rows = (await db.execute(select(PolicyMemoryRecord))).scalars().all()
        print(f"\n=== Policy Memory Records: {len(m_rows)} ===")
        by_pol = {}
        for r in m_rows:
            key = (r.merchant_id, r.policy_id)
            by_pol[key] = by_pol.get(key, 0) + 1
        for (m, p), count in sorted(by_pol.items()):
            print(f"  Memory: Merch={m:20} | Pol={p:25} | Count={count}")

if __name__ == "__main__":
    asyncio.run(main())
