"""Seed product categories per prd.md §13.1 taxonomy."""

import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


CATEGORIES = [
    {"name": "Food & Beverage", "children": [
        {"name": "Packaged Food"},
        {"name": "Beverages"},
        {"name": "Edible Oils & Fats"},
    ]},
    {"name": "Personal Care & Cosmetics", "children": [
        {"name": "Cosmetics"},
        {"name": "Toiletries"},
    ]},
    {"name": "Household", "children": [
        {"name": "Cleaning Products"},
        {"name": "Home Care"},
    ]},
    {"name": "Health & Pharma", "children": [
        {"name": "OTC/Medical Device-adjacent"},
    ]},
    {"name": "Industrial/Bulk"},
    {"name": "Other/Uncategorized"},
]


async def seed_categories(session: AsyncSession) -> int:
    """Insert category taxonomy. Idempotent — skips existing categories."""
    result = await session.execute(text("SELECT COUNT(*) FROM categories"))
    count = result.scalar()
    if count and count > 0:
        print(f"Categories already seeded ({count} rows). Skipping.")
        return 0

    inserted = 0
    for cat in CATEGORIES:
        parent_id = str(uuid.uuid4())
        await session.execute(
            text("INSERT INTO categories (id, name, parent_id) VALUES (:id, :name, NULL)"),
            {"id": parent_id, "name": cat["name"]},
        )
        inserted += 1
        for child in cat.get("children", []):
            child_id = str(uuid.uuid4())
            await session.execute(
                text("INSERT INTO categories (id, name, parent_id) VALUES (:id, :name, :parent_id)"),
                {"id": child_id, "name": child["name"], "parent_id": parent_id},
            )
            inserted += 1

    await session.commit()
    print(f"Seeded {inserted} categories.")
    return inserted
