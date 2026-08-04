# -*- coding: utf-8 -*-
"""安全评分批处理 — 对 SG 用 data.gov.sg NPC 数据, 对 GB 用 police.uk API"""
import asyncio, json, sys, os
from pathlib import Path
from datetime import datetime, timezone

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root)); os.chdir(backend_root)

from sqlalchemy import select, text
from app.db.session import async_session_maker
from app.models.institute import Institute
from app.services.safety_scoring import SafetyScoringService


async def main():
    async with async_session_maker() as session:
        # 加载所有有坐标的 Institute
        rows = await session.execute(
            select(Institute.id, Institute.country, Institute.latitude, Institute.longitude)
            .where(Institute.latitude.is_not(None), Institute.longitude.is_not(None))
        )
        institutes = [(r.id, r.country, float(r.latitude), float(r.longitude)) for r in rows.all()]

        # 按国家分组
        sg = [(i, lat, lng) for i, c, lat, lng in institutes if c == "SG"]
        gb = [(i, lat, lng) for i, c, lat, lng in institutes if c == "GB"]

        svc = SafetyScoringService()
        all_results = {}

        if sg:
            print(f"SG 新加坡: {len(sg)} 栋 -> data.gov.sg NPC data")
            sg_ids = [i for i, _, _ in sg]
            sg_lat = {i: lat for i, lat, _ in sg}
            sg_lng = {i: lng for i, _, lng in sg}
            results = svc._score_sg_batch(sg_ids, sg_lat, sg_lng)
            all_results.update(results)
            for pid, r in results.items():
                print(f"  [{pid}] score={r.score:.1f}/5 npc={r.npc} vs_avg={r.vs_national_avg}")

        if gb:
            print(f"GB London: {len(gb)} -> police.uk API")
            gb_ids = [i for i, _, _ in gb]
            gb_lat = {i: lat for i, lat, _ in gb}
            gb_lng = {i: lng for i, _, lng in gb}
            results = await svc._score_uk_batch(gb_ids, gb_lat, gb_lng)
            all_results.update(results)
            for pid, r in results.items():
                print(f"  [{pid}] score={r.score:.1f}/5 summary={r.summary[:80]}")

        # 写入 institute_pois.safety_data (raw SQL, model/DB column mismatch)
        updated = 0
        for pid, r in all_results.items():
            await session.execute(
                text("UPDATE institute_pois SET safety_data=:sd, generated_at=:t WHERE institute_id=:pid"),
                {"sd": json.dumps(r.to_dict()), "t": datetime.now(timezone.utc), "pid": pid},
            )
            updated += 1

        await session.commit()
        print(f"\nDone: {updated} safety scores written")


if __name__ == "__main__":
    asyncio.run(main())
