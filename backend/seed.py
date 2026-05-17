"""
Seed the database with one company and one owner (super user).

Usage (from backend/):
    python seed.py

Optional env vars (or add to .env):
    SEED_COMPANY_NAME=AutoPM
    SEED_COMPANY_SLUG=autopm
    SEED_USER_EMAIL=admin@autopm.local
    SEED_USER_NAME=Super Admin
    SEED_USER_PASSWORD=changeme123
"""

import asyncio
import os
import sys

from sqlalchemy import select

from core.database import async_session_factory
from core.security import hash_password
from modules.companies.models import Company
from modules.users.models import User

SEED_COMPANY_NAME = os.getenv("SEED_COMPANY_NAME", "AutoPM")
SEED_COMPANY_SLUG = os.getenv("SEED_COMPANY_SLUG", "autopm")
SEED_USER_EMAIL = os.getenv("SEED_USER_EMAIL", "admin@autopm.com")
SEED_USER_NAME = os.getenv("SEED_USER_NAME", "Super Admin")
SEED_USER_PASSWORD = os.getenv("SEED_USER_PASSWORD", "changeme123")


async def seed() -> None:
    async with async_session_factory() as db:
        company_result = await db.execute(select(Company).where(Company.slug == SEED_COMPANY_SLUG))
        company = company_result.scalar_one_or_none()

        if company:
            print(f"Company already exists: {company.name} ({company.slug})")
        else:
            company = Company(name=SEED_COMPANY_NAME, slug=SEED_COMPANY_SLUG)
            db.add(company)
            await db.flush()
            print(f"Created company: {company.name} ({company.slug})")

        user_result = await db.execute(select(User).where(User.email == SEED_USER_EMAIL))
        user = user_result.scalar_one_or_none()

        if user:
            print(f"Super user already exists: {user.email} (role={user.global_role})")
        else:
            user = User(
                company_id=company.id,
                email=SEED_USER_EMAIL,
                full_name=SEED_USER_NAME,
                hashed_password=hash_password(SEED_USER_PASSWORD),
                global_role="owner",
                is_active=True,
            )
            db.add(user)
            print(f"Created super user: {user.email} (role=owner)")

        await db.commit()

    print("\nSeed complete. Login credentials:")
    print(f"  Email:    {SEED_USER_EMAIL}")
    print(f"  Password: {SEED_USER_PASSWORD}")


def main() -> None:
    try:
        asyncio.run(seed())
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
