"""One-off script to seed the Codex E2E org + user for /cases/summary testing.

Usage:
  cd backend && source .venv/bin/activate && python scripts/seed_test_data.py [--with-cases]
"""
from __future__ import annotations

import asyncio
import sys

from prisma import Prisma


ORG_ID = "codex_e2e_org"
USER_ID = "codex_e2e_user"
EMAIL = "codex-e2e@example.local"
NAME = "Codex E2E User"


async def main(with_cases: bool) -> None:
    db = Prisma()
    await db.connect()
    try:
        org = await db.organization.find_unique(where={"id": ORG_ID})
        if not org:
            await db.organization.create(data={"id": ORG_ID, "name": "Codex E2E Org"})
            print(f"created org {ORG_ID}")
        else:
            print(f"org {ORG_ID} already exists")

        user = await db.user.find_unique(where={"id": USER_ID})
        if not user:
            await db.user.create(
                data={
                    "id": USER_ID,
                    "email": EMAIL,
                    "name": NAME,
                    "org_id": ORG_ID,
                    "role": "admin",
                }
            )
            print(f"created user {USER_ID}")
        else:
            print(f"user {USER_ID} already exists")

        if with_cases:
            seed_cases = [
                {"applicant_name": "Test Collecting Alice", "status": "collecting"},
                {"applicant_name": "Test Finalized Bob", "status": "finalized"},
                {"applicant_name": "Test Draft Carol", "status": "draft"},
            ]
            for seed in seed_cases:
                created = await db.case.create(
                    data={
                        "applicant_name": seed["applicant_name"],
                        "status": seed["status"],
                        "user_id": USER_ID,
                        "org_id": ORG_ID,
                        "name": seed["applicant_name"],
                    }
                )
                print(f"created case id={created.id} status={seed['status']} name={seed['applicant_name']}")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    with_cases = "--with-cases" in sys.argv
    asyncio.run(main(with_cases))
