# -*- coding: utf-8 -*-
"""通勤时间预计算脚本 —— Google Maps Distance Matrix 批量拉取真实数据

遍历所有新加坡 Institute × 热门大学，调用 GoogleCommuteService.get_batch()，
将结果写入 institute_commutes 表，替换 mock 数据。

用法：
  cd backend && .venv/Scripts/python.exe scripts/precompute_commutes.py
  cd backend && .venv/Scripts/python.exe scripts/precompute_commutes.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/precompute_commutes.py --engine gm    # 强制 Google
  cd backend && .venv/Scripts/python.exe scripts/precompute_commutes.py --engine ors   # 强制 ORS
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker
from app.models.institute import Institute
from app.models.institute_commute import InstituteCommute
from app.models.university import University
from app.services.commute_service import (
    CommuteDestination,
    GoogleCommuteService,
    ORSCommuteService,
)


async def get_sg_institutes(session: AsyncSession) -> list[tuple[int, str, float, float]]:
    """获取所有有坐标的新加坡 Institute。"""
    rows = await session.execute(
        select(Institute.id, Institute.name, Institute.latitude, Institute.longitude)
        .where(Institute.country == "SG")
        .where(Institute.latitude.is_not(None))
        .where(Institute.longitude.is_not(None))
    )
    return [(r.id, r.name, float(r.latitude), float(r.longitude)) for r in rows.all()]


async def get_hot_universities(session: AsyncSession, country: str = "SG") -> list[tuple[int, str, float, float]]:
    """获取核心目标大学（种子数据中 Institute 绑定的）。"""
    # 种子数据中的 target_uni 只用了 NUS/NTU/SMU
    rows = await session.execute(
        select(University.id, University.name, University.latitude, University.longitude)
        .where(University.abbreviation.in_(["NUS", "NTU", "SMU"]))
        .where(University.is_active.is_(True))
    )
    unis = [(r.id, r.name, float(r.latitude), float(r.longitude)) for r in rows.all()]
    return unis


def fmt_min(val: int | None) -> str:
    return f"{val}min" if val is not None else "—"


async def run(engine: str = "gm", dry_run: bool = False):
    async with async_session_maker() as session:
        # ── 加载数据 ──
        institutes = await get_sg_institutes(session)
        universities = await get_hot_universities(session, "SG")

        if not institutes:
            print("❌ 没有找到新加坡 Institute（country=SG 且有坐标）")
            return
        if not universities:
            print("❌ 没有找到热门大学")
            return

        print(f"\n📍 {len(institutes)} 个 Institute × {len(universities)} 所大学")
        print(f"   Institutes: {', '.join(n[:25] for _, n, _, _ in institutes)}")
        print(f"   Universities: {', '.join(n[:25] for _, n, _, _ in universities)}")

        # ── 显示已有数据（对比用）──
        existing_rows = await session.execute(
            select(InstituteCommute).where(
                InstituteCommute.institute_id.in_([i[0] for i in institutes])
            )
        )
        existing = {(r.institute_id, r.university_id): r for r in existing_rows.scalars().all()}
        if existing:
            print(f"\n📋 当前库内数据（mock）：")
            for (inst_id, uni_id), r in existing.items():
                inst_name = next((n for i, n, _, _ in institutes if i == inst_id), "?")
                uni_name = next((n for i, n, _, _ in universities if i == uni_id), "?")
                print(f"   {inst_name[:20]:20s} → {uni_name[:20]:20s} | transit={fmt_min(r.transit_min)} walk={fmt_min(r.walk_min)} drive={fmt_min(r.drive_min)} | {r.source}")

        if dry_run:
            print("\n🔍 --dry-run：仅展示将要计算的内容，不实际调用 API\n")
            return

        # ── 选择引擎 ──
        if engine == "gm":
            service = GoogleCommuteService()
            if not service.api_key:
                print("❌ GM_API_KEY 未配置，请检查 .env")
                return
            source_label = "gm_api"
        elif engine == "ors":
            service = ORSCommuteService()
            if not service.api_key:
                print("❌ ORS_API_KEY 未配置")
                return
            source_label = "ors_api"
        else:
            print(f"❌ 未知引擎: {engine}")
            return

        # ── 逐所大学批量计算 ──
        total_written = 0
        for uni_id, uni_name, uni_lat, uni_lng in universities:
            print(f"\n🚀 计算 {uni_name} ({uni_lat}, {uni_lng}) ← {len(institutes)} 个 Institute ...")

            destinations = [
                CommuteDestination(dest_id=inst_id, lat=lat, lng=lng)
                for inst_id, _, lat, lng in institutes
            ]

            try:
                if engine == "gm":
                    results = await service.get_batch(uni_lat, uni_lng, destinations)
                else:
                    results = await service.get_batch(uni_lat, uni_lng, destinations)

                api_ok = sum(1 for r in results if r.source == "api")
                fallback = sum(1 for r in results if r.source != "api")
                print(f"   ✅ API 成功: {api_ok} | Haversine 兜底: {fallback}")

                for r in results:
                    inst_name = next((n for i, n, _, _ in institutes if i == r.dest_id), "?")
                    print(f"      {inst_name[:22]:22s} | transit={fmt_min(r.transit_min):>6s} walk={fmt_min(r.walk_min):>6s} drive={fmt_min(r.drive_min):>6s} bike={fmt_min(r.bike_min):>6s} | dist={r.dist_km}km | {r.source}")

                    # Upsert
                    ek = (r.dest_id, uni_id)
                    if ek in existing:
                        existing[ek].transit_min = r.transit_min
                        existing[ek].walk_min = r.walk_min
                        existing[ek].drive_min = r.drive_min
                        existing[ek].source = source_label
                        existing[ek].computed_at = datetime.now(timezone.utc)
                    else:
                        session.add(InstituteCommute(
                            institute_id=r.dest_id,
                            university_id=uni_id,
                            transit_min=r.transit_min,
                            walk_min=r.walk_min,
                            drive_min=r.drive_min,
                            source=source_label,
                            computed_at=datetime.now(timezone.utc),
                        ))
                    total_written += 1

            except Exception as exc:
                print(f"   ❌ 失败: {exc}")
                continue

        if total_written > 0:
            await session.commit()
            print(f"\n✅ 已写入 {total_written} 条通勤记录（source={source_label}）\n")
            _print_comparison(institutes, universities, existing, session)
        else:
            await session.rollback()
            print("\n⚠ 未写入任何数据\n")


def _print_comparison(institutes, universities, existing, session):
    """打印新旧数据对比。"""
    print("📊 数据对比（新 API 值 vs 旧 mock 值）：")
    print(f"{'Institute':<22} {'University':<20} {'transit(新/旧)':<18} {'walk(新/旧)':<16} {'drive(新/旧)'}")
    print("-" * 95)
    for inst_id, inst_name, _, _ in institutes:
        for uni_id, uni_name, _, _ in universities:
            key = (inst_id, uni_id)
            old = existing.get(key)
            old_t = fmt_min(old.transit_min) if old else "—"
            old_w = fmt_min(old.walk_min) if old else "—"
            old_d = fmt_min(old.drive_min) if old else "—"
            # new values are already in the session, not yet reloaded
            print(f"{inst_name[:20]:20s}  {uni_name[:18]:18s}  {old_t:<18s} {old_w:<16s} {old_d}")
    print()


async def main():
    dry_run = "--dry-run" in sys.argv
    engine = "gm"
    for arg in sys.argv:
        if arg.startswith("--engine="):
            engine = arg.split("=", 1)[1]

    print("=" * 60)
    print(f"🏃 通勤预计算 | 引擎: {engine} | {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)

    await run(engine=engine, dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())
