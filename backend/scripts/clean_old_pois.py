"""清理旧的假 POI 数据"""
import asyncio
from app.db.session import async_session_maker
from sqlalchemy import text

async def clean():
    async with async_session_maker() as db:
        r = await db.execute(text("DELETE FROM property_pois"))
        await db.commit()
        print(f"Deleted {r.rowcount} old POI records")

asyncio.run(clean())
