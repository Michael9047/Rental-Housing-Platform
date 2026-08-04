"""审计 POI 与通勤数据"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def audit():
    engine = create_async_engine("postgresql+asyncpg://rental:rental@localhost:5432/rental_housing")
    async with engine.connect() as conn:
        # POI
        rows = await conn.execute(text("SELECT COUNT(*) FROM institute_pois"))
        poi_total = rows.fetchone()[0]
        rows = await conn.execute(text("SELECT COUNT(*) FROM institute_pois WHERE poi_data IS NOT NULL"))
        poi_data = rows.fetchone()[0]
        rows = await conn.execute(text("SELECT COUNT(*) FROM institute_pois WHERE map_poi_data IS NOT NULL"))
        poi_map = rows.fetchone()[0]
        print(f"=== POI ({poi_total} rows) ===")
        print(f"  poi_data filled:   {poi_data}/{poi_total}")
        print(f"  map_poi_data filled: {poi_map}/{poi_total}")
        # Sample POI
        rows = await conn.execute(text("SELECT institute_id, LEFT(content,80), generated_at FROM institute_pois LIMIT 3"))
        for r in rows.fetchall():
            print(f"  inst={r[0]} | {r[1]} | {r[2]}")

        # Commute
        rows = await conn.execute(text("SELECT COUNT(*) FROM institute_commutes"))
        cm = rows.fetchone()[0]
        print(f"\n=== Commute ({cm} rows) ===")
        rows = await conn.execute(text("SELECT source, COUNT(*) FROM institute_commutes GROUP BY source"))
        for r in rows.fetchall():
            print(f"  {r[0]}: {r[1]} rows")

        # Sample commute
        rows = await conn.execute(text(
            "SELECT ic.institute_id, u.abbreviation, ic.transit_min, ic.walk_min, ic.drive_min, ic.source "
            "FROM institute_commutes ic JOIN universities u ON ic.university_id=u.id ORDER BY ic.institute_id LIMIT 5"
        ))
        for r in rows.fetchall():
            print(f"  inst={r[0]} -> {r[1]} | transit={r[2]}m walk={r[3]}m drive={r[4]}m | {r[5]}")

        # SG institutes
        rows = await conn.execute(text("SELECT COUNT(*) FROM institutes WHERE country='SG'"))
        sg = rows.fetchone()[0]
        print(f"\n  SG institutes: {sg} | has POI: {poi_total}/{sg} | commute rows: {cm}")

    await engine.dispose()

asyncio.run(audit())
