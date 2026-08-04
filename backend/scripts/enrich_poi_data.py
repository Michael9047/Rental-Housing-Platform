# -*- coding: utf-8 -*-
"""POI 富化 — Google Places API 批量搜索所有 Institute 周边信息"""
import asyncio, json, sys, os
from pathlib import Path
from datetime import datetime, timezone

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root)); os.chdir(backend_root)

from sqlalchemy import select, text as sqla_text
from app.db.session import async_session_maker
from app.models.institute import Institute
from app.models.poi import InstitutePOI
from app.services.google_poi_service import GooglePOIService, KW_ORDER, CATEGORIES, POIItem


async def main(dry_run: bool = False, limit: int = 0):
    async with async_session_maker() as session:
        # 加载所有有坐标的 Institute
        rows = await session.execute(
            select(Institute.id, Institute.name, Institute.latitude, Institute.longitude, Institute.country)
            .where(Institute.latitude.is_not(None), Institute.longitude.is_not(None))
            .order_by(Institute.id)
        )
        institutes = [(r.id, r.name, float(r.latitude), float(r.longitude), r.country) for r in rows.all()]
        if limit > 0:
            institutes = institutes[:limit]

        print(f"共 {len(institutes)} 栋 Institute 待 POI 搜索\n")
        svc = GooglePOIService()
        updated = 0

        for i, (inst_id, name, lat, lng, country) in enumerate(institutes):
            print(f"[{i+1}/{len(institutes)}] {name[:30]} ({lat}, {lng}) ...")
            if dry_run:
                continue

            try:
                # 全量搜索
                result_map = await svc.search_all(lat, lng, radius_m=2000)
                # 转为 POIItem
                item_map = {}
                for kw, pois in result_map.items():
                    item_map[kw] = [POIItem(**p) if isinstance(p, dict) else p for p in pois]
                item_map = svc.apply_all_dedup(item_map)

                # 组装 map_poi_data
                map_categories: dict[str, list[dict]] = {}
                for kw in KW_ORDER:
                    if kw in item_map and item_map[kw]:
                        items = [{"id": p.place_id or p.name, "name": p.name, "lat": p.lat, "lng": p.lng,
                                  "distance": p.distance_m,
                                  "line": [ln.get("ref", "") for ln in p.transit_lines] if p.transit_lines else []}
                                 for p in item_map[kw]]
                        if items:
                            parent = next((cat for cat, kws in CATEGORIES.items() if kw in kws), "Other")
                            map_categories.setdefault(parent, []).extend(items)

                map_poi_data = {"search_radius_m": 2000, "categories": map_categories}

                # 组装 poi_data
                poi_data: dict[str, list[dict]] = {}
                for cat, kws in CATEGORIES.items():
                    if cat == "Landmark" or cat == "地标":
                        continue
                    cat_items = []
                    for kw in kws:
                        if kw in item_map:
                            for p in item_map[kw][:5]:
                                cat_items.append({"name": p.name, "distance": f"{p.distance_m}m",
                                                  "keyword": kw, "rating": p.rating})
                    if cat_items:
                        poi_data[cat] = sorted(cat_items, key=lambda x: int(x["distance"].rstrip("m")))

                # 组装 content
                lines = [f"{name} 周边设施："]
                for cat, items in poi_data.items():
                    if items:
                        names = "、".join(i["name"] for i in items[:3])
                        lines.append(f"{cat}：{names}等{len(items)}项")
                content = "\n".join(lines)

                # Upsert via raw SQL (model has id column DB doesn't)
                existing = await session.execute(
                    sqla_text("SELECT institute_id FROM institute_pois WHERE institute_id=:iid"),
                    {"iid": inst_id},
                )
                exists = existing.fetchone() is not None

                if exists:
                    await session.execute(
                        sqla_text("""UPDATE institute_pois SET content=:c, poi_data=:pd, map_poi_data=:mp,
                                     generated_at=:t WHERE institute_id=:iid"""),
                        {"c": content, "pd": json.dumps(poi_data), "mp": json.dumps(map_poi_data),
                         "t": datetime.now(timezone.utc), "iid": inst_id},
                    )
                else:
                    await session.execute(
                        sqla_text("""INSERT INTO institute_pois (institute_id, content, poi_data, map_poi_data,
                                     safety_data, generated_at, reviewed)
                                     VALUES (:iid, :c, :pd, :mp, :sd, :t, false)"""),
                        {"iid": inst_id, "c": content, "pd": json.dumps(poi_data),
                         "mp": json.dumps(map_poi_data), "sd": json.dumps({"crime_rate": "pending"}),
                         "t": datetime.now(timezone.utc)},
                    )

                await session.commit()
                total_pois = sum(len(v) for v in map_categories.values())
                print(f"  -> {len(map_categories)} categories, {total_pois} POIs")
                updated += 1

            except Exception as e:
                print(f"  FAIL: {e}")
                await session.rollback()

        print(f"\nDone: {updated}/{len(institutes)} institutes enriched with real POI data")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    limit = 0
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    asyncio.run(main(dry_run=dry, limit=limit))
