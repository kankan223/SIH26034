"""Seed initial rule versions per prd.md §12.6."""

import uuid
from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


SEED_RULES = [
    {
        "rule_key": "LM-RULE-006-MRP-FORMAT",
        "title": "MRP declaration format",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011, Rule 6(1)(f)",
        "version": 1,
        "effective_date": date(2020, 1, 1),
        "content": {
            "rule_id": "LM-RULE-006-MRP-FORMAT",
            "title": "MRP declaration format",
            "applies_when": {
                "product_categories": ["ALL"],
                "exclude_categories": ["INDUSTRIAL_CONSUMER", "BULK_OVER_25KG"],
                "package_type": "retail",
            },
            "required_field": "mrp",
            "validation": {
                "type": "regex_and_presence",
                "pattern": r"(Maximum\s+Retail\s+Price|MRP).{0,20}(Rs\.?|₹).{0,15}(inclusive\s+of\s+all\s+taxes)",
                "case_insensitive": True,
            },
            "severity": "CRITICAL",
            "evidence_required": True,
        },
    },
    {
        "rule_key": "LM-RULE-005-NET-QUANTITY",
        "title": "Net quantity declaration",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011, Rule 5",
        "version": 1,
        "effective_date": date(2020, 1, 1),
        "content": {
            "rule_id": "LM-RULE-005-NET-QUANTITY",
            "title": "Net quantity declaration",
            "applies_when": {
                "product_categories": ["ALL"],
                "exclude_categories": ["BULK_OVER_25KG"],
                "package_type": "retail",
            },
            "required_field": "net_quantity",
            "validation": {
                "type": "presence_only",
            },
            "severity": "CRITICAL",
            "evidence_required": True,
        },
    },
    {
        "rule_key": "LM-RULE-006-MANUFACTURER",
        "title": "Manufacturer/packer details",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011, Rule 6(1)(a)",
        "version": 1,
        "effective_date": date(2020, 1, 1),
        "content": {
            "rule_id": "LM-RULE-006-MANUFACTURER",
            "title": "Manufacturer/packer details",
            "applies_when": {
                "product_categories": ["ALL"],
                "package_type": "retail",
            },
            "required_field": "manufacturer_name",
            "validation": {
                "type": "presence_only",
            },
            "severity": "CRITICAL",
            "evidence_required": True,
        },
    },
    {
        "rule_key": "LM-RULE-006-DATE",
        "title": "Date of manufacture/packing",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011, Rule 6(1)(e)",
        "version": 1,
        "effective_date": date(2020, 1, 1),
        "content": {
            "rule_id": "LM-RULE-006-DATE",
            "title": "Date of manufacture/packing",
            "applies_when": {
                "product_categories": ["ALL"],
                "package_type": "retail",
            },
            "required_field": "mfg_date",
            "validation": {
                "type": "presence_only",
            },
            "severity": "CRITICAL",
            "evidence_required": True,
        },
    },
    {
        "rule_key": "LM-RULE-006-CONSUMER-CARE",
        "title": "Consumer care information",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011, Rule 6(1)(h)",
        "version": 1,
        "effective_date": date(2020, 1, 1),
        "content": {
            "rule_id": "LM-RULE-006-CONSUMER-CARE",
            "title": "Consumer care information",
            "applies_when": {
                "product_categories": ["ALL"],
                "package_type": "retail",
            },
            "required_field": "consumer_care",
            "validation": {
                "type": "presence_only",
            },
            "severity": "MAJOR",
            "evidence_required": True,
        },
    },
]


async def seed_rules(session: AsyncSession) -> int:
    """Insert seed rules and rule versions. Idempotent."""
    result = await session.execute(text("SELECT COUNT(*) FROM rules"))
    count = result.scalar()
    if count and count > 0:
        print(f"Rules already seeded ({count} rows). Skipping.")
        return 0

    inserted = 0
    for rule_data in SEED_RULES:
        rule_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        await session.execute(
            text("INSERT INTO rules (id, rule_key, title) VALUES (:id, :rule_key, :title)"),
            {"id": rule_id, "rule_key": rule_data["rule_key"], "title": rule_data["title"]},
        )

        await session.execute(
            text("""INSERT INTO rule_versions (id, rule_id, version, content, legal_reference, effective_date, published_at)
                     VALUES (:id, :rule_id, :version, :content, :legal_reference, :effective_date, NOW())"""),
            {
                "id": version_id,
                "rule_id": rule_id,
                "version": rule_data["version"],
                "content": rule_data["content"],
                "legal_reference": rule_data["legal_reference"],
                "effective_date": rule_data["effective_date"],
            },
        )
        inserted += 1

    await session.commit()
    print(f"Seeded {inserted} rules with initial versions.")
    return inserted
