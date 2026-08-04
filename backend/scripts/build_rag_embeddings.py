# -*- coding: utf-8 -*-
"""RAG Embedding 批量生成脚本

遍历所有 UnitType，拼接富文本描述 → 智谱 embedding-3 向量化 → 写入 DB。
运行: cd backend && .venv/Scripts/python.exe scripts/build_rag_embeddings.py
"""

import asyncio
import json
import sys
import os
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker
from app.models.unit_type import UnitType
from app.models.institute import Institute
from app.models.poi import InstitutePOI
from app.models.institute_commute import InstituteCommute
from app.models.university import University
from app.services.agentic.agents.search_agent import build_unit_type_search_text
from app.services.embedding_service import EmbeddingService


async def build_all(dry_run: bool = False, limit: int = 0):
    embed_svc = EmbeddingService()
    if not embed_svc.is_available:
        print("❌ 没有可用的 Embedding Provider！请检查 ZHIPU_API_KEY 或 OPENAI_API_KEY")
        return

    async with async_session_maker() as session:
        # 加载所有 UnitType + Institute
        stmt = (
            select(UnitType, Institute)
            .join(Institute, UnitType.institute_id == Institute.id)
            .where(UnitType.deleted_at.is_(None))
            .order_by(UnitType.id)
        )
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        rows = result.all()
        total = len(rows)

        # 批量加载所有 POI、Commute、Safety
        inst_ids = list(set(r[1].id for r in rows))
        poi_rows = await session.execute(
            select(InstitutePOI.institute_id, InstitutePOI.map_poi_data, InstitutePOI.safety_data)
            .where(InstitutePOI.institute_id.in_(inst_ids))
        )
        poi_map = {}
        safety_map = {}
        for r in poi_rows.all():
            poi_map[r.institute_id] = r.map_poi_data or {}
            # Parse JSON safety_data if stored as string
            sd = r.safety_data
            if isinstance(sd, str):
                try: sd = json.loads(sd)
                except: sd = None
            elif isinstance(sd, dict):
                pass
            else:
                sd = None
            safety_map[r.institute_id] = sd

        commute_rows = await session.execute(
            select(InstituteCommute, University.name, University.abbreviation)
            .join(University, InstituteCommute.university_id == University.id)
            .where(InstituteCommute.institute_id.in_(inst_ids))
        )
        commute_map: dict[int, list] = {}
        for c, uni_name, uni_abbr in commute_rows.all():
            if c.institute_id not in commute_map:
                commute_map[c.institute_id] = []
            commute_map[c.institute_id].append((uni_abbr or uni_name, c.transit_min, c.walk_min))

        print(f"📊 共 {total} 个户型, {len(poi_map)} 个有 POI, {len(commute_map)} 个有 Commute\n")

        success = 0
        failed = 0

        for i, (ut, inst) in enumerate(rows):
            # 构建 commute 文本
            commutes = commute_map.get(inst.id, [])
            commute_text = ""
            if commutes:
                c_parts = []
                for uni_abbr, transit_min, walk_min in commutes[:3]:
                    if transit_min:
                        c_parts.append(f"到{uni_abbr}地铁{transit_min}分钟")
                    if walk_min and walk_min < 60:
                        c_parts.append(f"步行{walk_min}分钟")
                if c_parts:
                    commute_text = "；".join(c_parts)

            # 构建富文本（含 POI + Commute + Safety）
            text = build_unit_type_search_text(
                inst, ut,
                poi_map=poi_map.get(inst.id),
                commute_text=commute_text,
                safety_data=safety_map.get(inst.id),
            )

            if dry_run:
                print(f"[{i+1}/{total}] {inst.name_cn or inst.name} — {ut.name}")
                print(f"  📝 {text[:200]}...")
                print(f"  📏 {len(text)} 字符")
                if commute_text:
                    print(f"  🚇 {commute_text}")
                success += 1
                continue

            try:
                vec = await embed_svc.generate_embedding(text)
                await session.execute(
                    update(UnitType)
                    .where(UnitType.id == ut.id)
                    .values(embedding=json.dumps(vec))
                )
                success += 1
                if (i + 1) % 10 == 0 or i == total - 1:
                    await session.commit()
                    print(f"  ✅ [{i+1}/{total}] {inst.name_cn or inst.name} — {ut.name} ({len(text)} 字符, 1536 维)")

            except Exception as e:
                failed += 1
                print(f"  ❌ [{i+1}/{total}] {inst.name_cn or inst.name} — {ut.name}: {e}")

        if not dry_run:
            await session.commit()
            print(f"\n✅ 完成: {success} 成功, {failed} 失败, {total} 总计\n")
        else:
            print(f"\n🔍 Dry-run 完成: {success} 条预览\n")


async def main():
    dry_run = "--dry-run" in sys.argv
    limit = 0
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
    await build_all(dry_run=dry_run, limit=limit)


if __name__ == "__main__":
    asyncio.run(main())
