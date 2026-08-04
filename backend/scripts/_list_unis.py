import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://rental:rental@localhost:5432/rental_housing")
    async with engine.connect() as conn:
        rows = await conn.execute(text(
            "SELECT id, name, abbreviation, city, country, is_hot, is_active "
            "FROM universities ORDER BY is_hot DESC, country, name"
        ))
        for r in rows.fetchall():
            hot = "HOT" if r.is_hot else "   "
            abbr = r.abbreviation or "-"
            city = r.city or "-"
            country = r.country or "-"
            active = "" if r.is_active else " [OFF]"
            print(f"{hot} [{r.id:2d}] {r.name[:48]:48s} {abbr:10s} {city:16s} {country}{active}")
    await engine.dispose()

asyncio.run(main())
