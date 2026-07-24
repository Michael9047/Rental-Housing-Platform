"""一次性补全数据库缺失的列。"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import text
from app.db.session import async_session_maker

NEEDED = [
    ("female_only", "BOOLEAN DEFAULT FALSE"),
    ("safety_score", "NUMERIC(3,2)"),
    ("min_stay_months", "INTEGER"),
    ("min_lease_months", "INTEGER"),
    ("max_lease_months", "INTEGER"),
    ("available_from", "DATE"),
    ("city", "VARCHAR(100)"),
    ("institute_name", "VARCHAR(200)"),
    ("institute_amenities", "TEXT"),
    ("inventory_reserved", "BOOLEAN DEFAULT FALSE"),
    ("payment_expires_at", "TIMESTAMP WITH TIME ZONE"),
    ("total_rent", "INTEGER"),
    ("lease_months", "INTEGER"),
]


async def main():
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'properties'")
        )
        existing = {row[0] for row in result}
        print(f"DB has {len(existing)} columns")
        for col_name, col_type in NEEDED:
            if col_name not in existing:
                sql = f"ALTER TABLE properties ADD COLUMN {col_name} {col_type}"
                print(f"  + {col_name} ({col_type})")
                await session.execute(text(sql))
            else:
                print(f"  ✓ {col_name} (exists)")
        await session.commit()
        print("Done.")


asyncio.run(main())
