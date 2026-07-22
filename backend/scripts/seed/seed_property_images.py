# -*- coding: utf-8 -*-
"""
为新加坡和英国各10套房源添加Unsplash室内照片 (每套20张)

Unsplash图片无需API Key, URL永久有效。
按房源类型匹配不同风格的室内照片。

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_property_images.py
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_property_images.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_property_images.py --clear-existing
"""

import asyncio, os, random, sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete, func
from app.db.session import async_session_maker
from app.models.property import Property
from app.models.property_image import PropertyImage

# ═══════════════════════════════════════════════
# Unsplash 精选照片库 — 按类型分类
# 每个URL格式: https://images.unsplash.com/photo-{ID}?w=800&fit=crop
# ═══════════════════════════════════════════════

UNSPLASH = {
    # 客厅 (Living Room) — 现代明亮风
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
    # 厨房 (Kitchen) — 现代装修
    "kitchen": [
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&fit=crop",
        "https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=800&fit=crop",
        "https://images.unsplash.com/photo-1565538810643-b5bdb714032a?w=800&fit=crop",
        "https://images.unsplash.com/photo-1588854337236-6889d631faa8?w=800&fit=crop",
        "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?w=800&fit=crop",
    ],
    # 卧室 (Bedroom) — 温馨舒适
    "bedroom": [
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&fit=crop",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=800&fit=crop",
        "https://images.unsplash.com/photo-1540518614846-7eded433c457?w=800&fit=crop",
        "https://images.unsplash.com/photo-1560185007-5f0bb1866cab?w=800&fit=crop",
        "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800&fit=crop",
        "https://images.unsplash.com/photo-1505693314120-0d443867891c?w=800&fit=crop",
    ],
    # 卫生间 (Bathroom) — 干净现代
    "bathroom": [
        "https://images.unsplash.com/photo-1584622650111-993a803aa2b7?w=800&fit=crop",
        "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&fit=crop",
        "https://images.unsplash.com/photo-1604709177225-055f99402ea3?w=800&fit=crop",
    ],
    # 外观/建筑 (Exterior) — 公寓楼/House外观
    "exterior": [
        "https://images.unsplash.com/photo-1460317442991-0ec209397118?w=800&fit=crop",
        "https://images.unsplash.com/photo-1475855581690-80accde3ae2b?w=800&fit=crop",
        "https://images.unsplash.com/photo-1448630360428-65456659c146?w=800&fit=crop",
        "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800&fit=crop",
        "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&fit=crop",
    ],
    # 书房/工作区 (Study)
    "study": [
        "https://images.unsplash.com/photo-1593476550610-87baa746101b?w=800&fit=crop",
        "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?w=800&fit=crop",
        "https://images.unsplash.com/photo-1593062096033-9a26b09da705?w=800&fit=crop",
    ],
    # 阳台/景观 (View)
    "view": [
        "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=800&fit=crop",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&fit=crop",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=800&fit=crop",
    ],
    # 公共区域/大堂 (Lobby)
    "lobby": [
        "https://images.unsplash.com/photo-1545324417-2c3cb20a15c9?w=800&fit=crop",
        "https://images.unsplash.com/photo-1574362848149-11496d93a7c7?w=800&fit=crop",
        "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=800&fit=crop",
    ],
}

# 每个房源类型的照片组合 (20张)
# apartment: 客厅×4 + 厨房×3 + 卧室×3 + 卫生间×2 + 外观×3 + 书房×2 + 景观×2 + 大堂×1
APARTMENT_PLAN = [
    ("living", 4), ("kitchen", 3), ("bedroom", 3), ("bathroom", 2),
    ("exterior", 3), ("study", 2), ("view", 2), ("lobby", 1),
]
# house: 外观×4 + 客厅×3 + 厨房×3 + 卧室×3 + 卫生间×2 + 书房×2 + 景观×3
HOUSE_PLAN = [
    ("exterior", 4), ("living", 3), ("kitchen", 3), ("bedroom", 3),
    ("bathroom", 2), ("study", 2), ("view", 3),
]
# studio: 客厅×5 + 厨房×3 + 卧室×3 + 卫生间×2 + 外观×3 + 景观×2 + 大堂×2
STUDIO_PLAN = [
    ("living", 5), ("kitchen", 3), ("bedroom", 3), ("bathroom", 2),
    ("exterior", 3), ("view", 2), ("lobby", 2),
]
# shared: 卧室×7 + 客厅×3 + 厨房×3 + 卫生间×3 + 外观×2 + 书房×2
SHARED_PLAN = [
    ("bedroom", 7), ("living", 3), ("kitchen", 3), ("bathroom", 3),
    ("exterior", 2), ("study", 2),
]

PLAN_MAP = {
    "apartment": APARTMENT_PLAN,
    "house": HOUSE_PLAN,
    "studio": STUDIO_PLAN,
    "shared": SHARED_PLAN,
}


def generate_image_urls(property_type: str, seed: int, count: int = 20) -> list[str]:
    """为某个房源生成20张照片URL，按类型分配"""
    plan = PLAN_MAP.get(property_type, APARTMENT_PLAN)
    urls = []
    rng = random.Random(seed)
    for category, n in plan:
        pool = UNSPLASH[category]
        picks = rng.sample(pool, min(n, len(pool)))
        urls.extend(picks)
    # 如果不够20张，用living补
    while len(urls) < count:
        urls.append(rng.choice(UNSPLASH["living"]))
    return urls[:count]


async def seed_images(dry_run=False, clear_existing=False):
    """为SG和UK各选10套房源，每套添加20张Unsplash照片"""

    async with async_session_maker() as session:
        # ── 选取房源：SG 10套 + UK 10套 ──
        sg_result = await session.execute(
            select(Property.id, Property.property_type)
            .where(Property.country == "SG")
            .order_by(func.random())
            .limit(10)
        )
        sg_props = [(r[0], r[1].value if hasattr(r[1], 'value') else r[1]) for r in sg_result.all()]

        uk_result = await session.execute(
            select(Property.id, Property.property_type)
            .where(Property.country == "GB")
            .order_by(func.random())
            .limit(10)
        )
        uk_props = [(r[0], r[1].value if hasattr(r[1], 'value') else r[1]) for r in uk_result.all()]

        selected = [("SG", p) for p in sg_props] + [("GB", p) for p in uk_props]

        if not selected:
            print("[ERROR] 没有找到房源!")
            return

        print(f"[选取] SG {len(sg_props)}套 + UK {len(uk_props)}套 = {len(selected)}套")
        print(f"[照片] 每套20张 = {len(selected)*20}张\n")

        # ── 清除旧的外部图片 ──
        if clear_existing and not dry_run:
            # 只清除unplash URL的图片（保留本地上传的）
            dr = await session.execute(
                delete(PropertyImage).where(PropertyImage.filename.like("https://images.unsplash.com/%"))
            )
            print(f"[CLEAR] 已删除 {dr.rowcount} 张Unsplash图片\n")
            await session.flush()

        if dry_run:
            print("=== DRY RUN ===\n")
            for country, (pid, ptype) in selected:
                urls = generate_image_urls(str(ptype), seed=pid)
                print(f"  [{country}] Property #{pid} ({ptype}): {len(urls)} URLs")
                for i, url in enumerate(urls[:3]):
                    print(f"    [{i+1}] {url[:80]}...")
                print(f"    ... +{len(urls)-3} more")
            print(f"\n[DRY RUN] {len(selected)}套 × 20 = {len(selected)*20} 张图片")
            return

        # ── 正式插入 ──
        total = 0
        for country, (pid, ptype) in selected:
            urls = generate_image_urls(str(ptype), seed=pid)
            for sort_order, url in enumerate(urls):
                is_primary = (sort_order == 0)
                # 加唯一后缀避免文件名冲突 (&seed= 参数 Unsplash 会忽略)
                unique_url = f"{url}&seed={pid}_{sort_order}"
                img = PropertyImage(
                    property_id=pid,
                    filename=unique_url,  # 前端会检测http前缀
                    original_name=f"unsplash_{country}_{pid}_{sort_order+1:02d}.jpg",
                    mime_type="image/jpeg",
                    file_size=0,  # 外部URL，未知大小
                    sort_order=sort_order,
                    is_primary=is_primary,
                )
                session.add(img)
                total += 1
            print(f"  [{country}] Property #{pid} ({ptype}): 20 photos added")

        await session.commit()
        print(f"\n{'='*60}")
        print(f"[DONE] {len(selected)}套 × 20 = {total} 张Unsplash照片导入完成!")
        print(f"{'='*60}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clear = "--clear-existing" in sys.argv
    asyncio.run(seed_images(dry_run=dry, clear_existing=clear))
