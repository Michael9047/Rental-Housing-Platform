"""Score all SG properties with safety data"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.services.safety_scoring import SafetyScoringService
from app.models.poi import PropertyPOI
from datetime import datetime, timezone

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    sess = async_sessionmaker(engine, expire_on_commit=False)

    async with sess() as s:
        r = await s.execute(text('''
            SELECT r.id, r.latitude, r.longitude
            FROM rooms r
            WHERE r.latitude IS NOT NULL AND r.longitude IS NOT NULL
            AND (r.country = :c1 OR r.country = :c2)
        '''), {"c1": "SG", "c2": "sg"})
        rows = r.all()

    print(f"Scoring {len(rows)} SG properties...")
    svc = SafetyScoringService()

    for i, (pid, lat, lng) in enumerate(rows):
        lat_f, lng_f = float(lat), float(lng)
        result = await svc.score_single(pid, lat=lat_f, lng=lng_f, country="SG")

        async with sess() as s:
            from sqlalchemy import select as sa_select
            r2 = await s.execute(sa_select(PropertyPOI).where(PropertyPOI.property_id == pid))
            poi = r2.scalar_one_or_none()
            d = result.to_dict()
            if poi:
                poi.safety_data = d
            else:
                s.add(PropertyPOI(
                    property_id=pid, content="", safety_data=d,
                    generated_at=datetime.now(timezone.utc), reviewed=False,
                ))
            await s.commit()

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(rows)}...")

    # Summary
    async with sess() as s:
        r = await s.execute(text('''
            SELECT r.title, p.safety_data
            FROM property_pois p JOIN rooms r ON r.id = p.property_id
            WHERE p.safety_data IS NOT NULL
        '''))
        results = [(row[0], row[1]) for row in r.all()]

    print(f"\nDone! {len(results)} scored:")
    for title, sd in sorted(results, key=lambda x: x[1].get("safety_score", 0)):
        npc_raw = sd.get("npc", "?")
        npc_short = npc_raw.split(" - ")[-1].replace(" NPC", "") if " - " in npc_raw else npc_raw
        name = (title or f"#{sd.get('property_id','?')}")[:40]
        print(f"  {name:42s} main={sd['safety_score']} om={sd['om_score']} | {npc_short}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
