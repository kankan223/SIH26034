"""Seed demo user accounts per prd.md §41."""

import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

DEMO_USERS = [
    {
        "email": "inspector@docket.gov.in",
        "password": "inspector123",
        "full_name": "Rahul Kumar",
        "role": "inspector",
        "region": "Delhi",
    },
    {
        "email": "senior@docket.gov.in",
        "password": "senior123",
        "full_name": "Meena Sharma",
        "role": "senior_officer",
        "region": "Delhi",
    },
    {
        "email": "admin@docket.gov.in",
        "password": "admin123",
        "full_name": "Dept Admin",
        "role": "admin",
        "region": None,
    },
]


async def seed_users(session: AsyncSession) -> int:
    """Insert demo users. Idempotent — skips existing users."""
    result = await session.execute(text("SELECT COUNT(*) FROM users"))
    count = result.scalar()
    if count and count > 0:
        print(f"Users already seeded ({count} rows). Skipping.")
        return 0

    inserted = 0
    for user in DEMO_USERS:
        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(user["password"].encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        await session.execute(
            text("""INSERT INTO users (id, email, password_hash, full_name, role, region, is_active)
                     VALUES (:id, :email, :password_hash, :full_name, :role, :region, true)"""),
            {
                "id": user_id,
                "email": user["email"],
                "password_hash": password_hash,
                "full_name": user["full_name"],
                "role": user["role"],
                "region": user["region"],
            },
        )
        inserted += 1

    await session.commit()
    print(f"Seeded {inserted} users.")
    return inserted
