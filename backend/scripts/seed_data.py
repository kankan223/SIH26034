"""Master seed runner — seeds all demo data in order."""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from scripts.seed_categories import seed_categories
from scripts.seed_users import seed_users
from scripts.seed_rules import seed_rules


async def main():
    """Run all seed scripts in order."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("=== Docket Seed Data Runner ===")
        print()

        print("1. Seeding categories...")
        await seed_categories(session)

        print("2. Seeding users...")
        await seed_users(session)

        print("3. Seeding rules...")
        await seed_rules(session)

        print()
        print("=== Seeding complete ===")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
