import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://rental:rental@localhost:5432/rental_housing")
    async with engine.connect() as conn:
        # delete GB commutes
        await conn.execute(text("DELETE FROM institute_commutes WHERE institute_id IN (SELECT id FROM institutes WHERE country='GB')"))
        # delete GB POIs
        await conn.execute(text("DELETE FROM institute_pois WHERE institute_id IN (SELECT id FROM institutes WHERE country='GB')"))
        # delete GB unit types
        await conn.execute(text("DELETE FROM unit_types WHERE institute_id IN (SELECT id FROM institutes WHERE country='GB')"))
        # delete GB institutes
        r = await conn.execute(text("DELETE FROM institutes WHERE country='GB' RETURNING id"))
        deleted = len(r.fetchall())
        await conn.commit()
        print(f"Deleted {deleted} London institutes + children")

asyncio.run(main())
