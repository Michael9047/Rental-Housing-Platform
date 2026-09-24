# -*- coding: utf-8 -*-
"""
回填 UnitType.rent_period — 根据 Institute.country 自动推断

规则：
  - country == 'UK'  → 'weekly'
  - 其他             → 'monthly'（DB 默认值，保持不变）

运行方式：
  cd backend
  .venv/Scripts/python.exe scripts/seed/backfill_rent_period.py
  .venv/Scripts/python.exe scripts/seed/backfill_rent_period.py --dry-run
"""

import asyncio
import os
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, update
from app.db.session import async_session_maker
from app.models.unit_type import UnitType
from app.models.institute import Institute


async def backfill(*, dry_run: bool = False) -> None:
    async with async_session_maker() as session:
        # 找出所有 country='UK' 的 institute
        uk_institute_ids = (
            await session.scalars(
                select(Institute.id).where(Institute.country == "UK")
            )
        ).all()

        if not uk_institute_ids:
            print("✅ 没有 UK 公寓，无需回填")
            return

        print(f"找到 {len(uk_institute_ids)} 个 UK 公寓: {uk_institute_ids}")

        # 查询这些公寓下所有 rent_period != 'weekly' 的 UnitType
        stmt = select(UnitType).where(
            UnitType.institute_id.in_(uk_institute_ids),
            UnitType.rent_period != "weekly",
        )
        result = await session.scalars(stmt)
        to_fix = list(result)

        if not to_fix:
            print("✅ 所有 UK UnitType 已是 weekly，无需修改")
            return

        print(f"需要回填 {len(to_fix)} 条 UnitType:")
        for ut in to_fix:
            print(f"  UnitType id={ut.id}  name={ut.name!r}  "
                  f"rent_period={ut.rent_period.value!r}  "
                  f"institute_id={ut.institute_id}")

        if dry_run:
            print(f"\n⚠ dry-run 模式，未实际修改 {len(to_fix)} 条记录")
            return

        # 执行更新
        ids = [ut.id for ut in to_fix]
        await session.execute(
            update(UnitType)
            .where(UnitType.id.in_(ids))
            .values(rent_period="weekly")
        )
        await session.commit()
        print(f"\n✅ 已回填 {len(to_fix)} 条 UnitType → rent_period='weekly'")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    asyncio.run(backfill(dry_run=dry_run))


if __name__ == "__main__":
    main()
