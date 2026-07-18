# -*- coding: utf-8 -*-
"""
为所有市场的公寓楼（Property）添加 Unsplash 室内/建筑照片

与 v1 (seed_property_images.py) 的区别：
  - v1: 只为 SG 10套 + UK 10套 = 20套添加图片（每套20张）
  - v2: 为 80%+ 的 Property 添加图片（每套4-8张建筑级照片）

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_images.py
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_images.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_images.py --clear-existing
"""

import asyncio, os, random, sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.property import Property
from app.models.property_image import PropertyImage

# ═══════════════════════════════════════════════
# Unsplash 精选照片库 — 按建筑/室内类型分类
# ═══════════════════════════════════════════════

UNSPLASH = {
    # 公寓外观
    "exterior": [
        "https://images.unsplash.com/photo-1460317442991-0ec209397118?w=800&fit=crop",
        "https://images.unsplash.com/photo-1475855581690-80accde3ae2b?w=800&fit=crop",
        "https://images.unsplash.com/photo-1448630360428-65456659c146?w=800&fit=crop",
        "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&fit=crop",
        "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&fit=crop",
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800&fit=crop",
        "https://images.unsplash.com/photo-1480074568708-e7b720bb3f09?w=800&fit=crop",
        "https://images.unsplash.com/photo-1494526585095-c41746259356?w=800&fit=crop",
    ],
    # 大堂/入口
    "lobby": [
        "https://images.unsplash.com/photo-1545324417-2c3cb20a15c9?w=800&fit=crop",
        "https://images.unsplash.com/photo-1574362848149-11496d93a7c7?w=800&fit=crop",
        "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=800&fit=crop",
        "https://images.unsplash.com/photo-1576941089060-54dea5b2e120?w=800&fit=crop",
        "https://images.unsplash.com/photo-1531971589569-0d9370c42ee2?w=800&fit=crop",
    ],
    # 客厅
    "living": [
        "https://images.unsplash.com/photo-1560185893-a5d57337e5c0?w=800&fit=crop",
        "https://images.unsplash.com/photo-1585412727339-54e4bae3bbf9?w=800&fit=crop",
        "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800&fit=crop",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800&fit=crop",
        "https://images.unsplash.com/photo-1600585152220-90363fe7e115?w=800&fit=crop",
        "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=800&fit=crop",
        "https://images.unsplash.com/photo-1600573472550-8090b5e0745e?w=800&fit=crop",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800&fit=crop",
    ],
    # 厨房
    "kitchen": [
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&fit=crop",
        "https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=800&fit=crop",
        "https://images.unsplash.com/photo-1565538810643-b5bdb714032a?w=800&fit=crop",
        "https://images.unsplash.com/photo-1588854337236-6889d631faa8?w=800&fit=crop",
        "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?w=800&fit=crop",
    ],
    # 卧室
    "bedroom": [
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&fit=crop",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=800&fit=crop",
        "https://images.unsplash.com/photo-1540518614846-7eded433c457?w=800&fit=crop",
        "https://images.unsplash.com/photo-1560185007-5f0bb1866cab?w=800&fit=crop",
        "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800&fit=crop",
        "https://images.unsplash.com/photo-1505693314120-0d443867891c?w=800&fit=crop",
    ],
    # 景观/阳台
    "view": [
        "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=800&fit=crop",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&fit=crop",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=800&fit=crop",
        "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&fit=crop",
    ],
    # 公共区域/健身房/泳池
    "common": [
        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800&fit=crop",
        "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=800&fit=crop",
        "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?w=800&fit=crop",
        "https://images.unsplash.com/photo-1593079831268-3381b0db4a77?w=800&fit=crop",
        "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800&fit=crop",
    ],
    # 书房/自习室
    "study": [
        "https://images.unsplash.com/photo-1593476550610-87baa746101b?w=800&fit=crop",
        "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?w=800&fit=crop",
        "https://images.unsplash.com/photo-1593062096033-9a26b09da705?w=800&fit=crop",
    ],
}

# 公寓楼照片组合：外观×2 + 大堂×1 + 客厅×1 + 厨房×1 + 公共区域×1 + 景观×1 + 卧室×1
BUILDING_PLAN = [
    ("exterior", 2), ("lobby", 1), ("living", 1), ("kitchen", 1),
    ("common", 1), ("view", 1), ("bedroom", 1),
]


def generate_building_images(seed: int, count: int = 8) -> list[str]:
    """为一个公寓楼生成照片 URL 列表"""
    urls = []
    rng = random.Random(seed)
    for category, n in BUILDING_PLAN:
        pool = UNSPLASH[category]
        picks = rng.sample(pool, min(n, len(pool)))
        urls.extend(picks)
    while len(urls) < count:
        urls.append(rng.choice(UNSPLASH["living"]))
    return urls[:count]


async def seed_images_v2(dry_run=False, clear_existing=False, coverage=0.85):
    """
    为每个市场 80%+ 的 Property 添加图片

    coverage: 带图比例（0.0 ~ 1.0），默认 85%
    """
    async with async_session_maker() as session:
        # ── 获取所有 Property ──
        result = await session.execute(
            select(Property.id, Property.country)
            .order_by(Property.id)
        )
        all_props = [(r[0], r[1]) for r in result.all()]

        if not all_props:
            print("[ERROR] 没有房源！请先运行 seed_v2_properties.py")
            return

        # 按市场统计
        from collections import Counter
        cnt = Counter(p[1] for p in all_props)

        # 选择带图的 Property（每个市场 coverage 比例）
        selected = []
        for country in cnt:
            market_props = [p for p in all_props if p[1] == country]
            n_select = max(1, int(len(market_props) * coverage))
            rng = random.Random(hash(country) + 42)
            selected.extend(rng.sample(market_props, n_select))

        # 每套 4-8 张
        images_per_prop = {pid: random.Random(pid).randint(4, 8) for pid, _ in selected}

        total_images = sum(images_per_prop.values())
        print(f"Property 总数: {len(all_props)}")
        print(f"  SG={cnt.get('SG',0)}, GB={cnt.get('GB',0)}, US={cnt.get('US',0)}, HK={cnt.get('HK',0)}")
        print(f"带图 Property (coverage={coverage:.0%}): {len(selected)}")
        print(f"图片总数: {total_images}\n")

        if dry_run:
            print("=== DRY RUN ===\n")
            for pid, country in selected[:5]:
                n = images_per_prop[pid]
                urls = generate_building_images(pid, n)
                print(f"  [{country}] Property #{pid}: {n} 张")
                for i, url in enumerate(urls[:3]):
                    print(f"    [{i+1}] {url[:80]}...")
                if len(urls) > 3:
                    print(f"    ... +{len(urls)-3} more")
            print(f"\n[DRY RUN] {len(selected)} 套 × 4-8 = {total_images} 张")
            return

        # ── 清除旧外部图片 ──
        if clear_existing:
            dr = await session.execute(
                delete(PropertyImage).where(
                    PropertyImage.filename.like("https://images.unsplash.com/%")
                )
            )
            print(f"[CLEAR] 已删除 {dr.rowcount} 张 Unsplash 图片\n")
            await session.flush()

        # ── 写入 ──
        created = 0
        for pid, country in selected:
            n = images_per_prop[pid]
            urls = generate_building_images(pid, n)
            for sort_order, url in enumerate(urls):
                is_primary = (sort_order == 0)
                unique_url = f"{url}&seed={pid}_{sort_order}"
                img = PropertyImage(
                    property_id=pid,
                    filename=unique_url,
                    original_name=f"unsplash_v2_{country}_{pid}_{sort_order+1:02d}.jpg",
                    mime_type="image/jpeg",
                    file_size=0,
                    sort_order=sort_order,
                    is_primary=is_primary,
                )
                session.add(img)
                created += 1
            if created % 200 == 0:
                print(f"  [{created:04d}] ...")

        await session.commit()
        print(f"\n{'='*60}")
        print(f"[DONE] {len(selected)} 套公寓楼 × 4-8 = {created} 张 Unsplash 照片")
        print(f"{'='*60}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clear = "--clear-existing" in sys.argv
    asyncio.run(seed_images_v2(dry_run=dry, clear_existing=clear))
