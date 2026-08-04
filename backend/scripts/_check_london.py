"""检查伦敦数据"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine("postgresql+asyncpg://rental:rental@localhost:5432/rental_housing")
    async with engine.connect() as conn:
        rows = await conn.execute(text(
            "SELECT id, name, abbreviation, city, latitude, longitude "
            "FROM universities WHERE country='GB' AND is_active=true "
            "ORDER BY is_hot DESC, id LIMIT 20"
        ))
        print("=== London Universities ===")
        for r in rows.fetchall():
            print(f"  [{r[0]:2d}] {r[1][:42]:42s} {str(r[2]):8s} | ({r[4]}, {r[5]})")

    await engine.dispose()

asyncio.run(check())
