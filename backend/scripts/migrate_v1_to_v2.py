"""V1 数据 → V2 三层架构迁移

映射规则：
  - properties 按 district 分组 → institutes（公寓楼）
  - room_types（改 property_id → institute_id）→ unit_types（户型）
  - 每个 property → 一个 room（房间），绑定到对应 unit_type
  - property_images 不动（已绑定 property_id = room_id）
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from app.db.session import async_session_maker

async def migrate():
    async with async_session_maker() as s:
        print("=" * 60)
        print("V1 → V2 三层架构数据迁移")
        print("=" * 60)

        # ── Step 1: 按 district 创建 institutes ──
        print("\n[1/5] 按 district 创建 institutes...")
        r = await s.execute(text(
            "SELECT DISTINCT ON (district) district, country, "
            "  MIN(latitude) as lat, MIN(longitude) as lng, "
            "  MIN(address) as addr "
            "FROM properties WHERE district IS NOT NULL "
            "GROUP BY district, country"
        ))
        districts = [(row[0], row[1], row[2], row[3], row[4]) for row in r]
        inst_map = {}  # district → new institute_id
        inst_count = 0

        for dist, country, lat, lng, addr in districts:
            name = dist.replace("新加坡-", "").replace("美国-", "").replace("伦敦-", "").replace("香港-", "")
            ins = await s.execute(text(
                "INSERT INTO institutes (name, address, latitude, longitude, status, created_by) "
                "VALUES (:name, :addr, :lat, :lng, 'active', 1) RETURNING id"
            ), {"name": f"{name} 公寓", "addr": addr or dist, "lat": lat, "lng": lng})
            new_id = ins.scalar()
            inst_map[dist] = new_id
            inst_count += 1
        await s.flush()
        print(f"  ✓ 创建了 {inst_count} 个 institutes")

        # ── Step 2: 将 room_types → unit_types（改 property_id → institute_id）──
        print("\n[2/5] 迁移 room_types → unit_types ...")
        # 为每个 property 找它的 district → institute
        r = await s.execute(text(
            "SELECT p.id, p.district FROM properties p WHERE p.district IS NOT NULL"
        ))
        prop_inst = {row[0]: inst_map.get(row[1]) for row in r}

        # 更新 room_types: property_id → institute_id
        # 先添加 institute_id 列（如果还没有）
        try:
            await s.execute(text("ALTER TABLE room_types ADD COLUMN IF NOT EXISTS institute_id INTEGER"))
            await s.flush()
        except:
            pass  # 列已存在

        rt_count = 0
        r = await s.execute(text("SELECT id, property_id FROM room_types WHERE property_id IS NOT NULL"))
        for row in r:
            rt_id, prop_id = row[0], row[1]
            inst_id = prop_inst.get(prop_id)
            if inst_id:
                await s.execute(text(
                    "UPDATE room_types SET institute_id = :iid WHERE id = :rid"
                ), {"iid": inst_id, "rid": rt_id})
                rt_count += 1
        await s.flush()
        print(f"  ✓ {rt_count} 个 room_types 已关联到 institutes")

        # ── Step 3: 根据 room_types 创建 unit_types 记录（去重合并）──
        print("\n[3/5] 合并 room_types → unit_types（按 institute + room_type + bedrooms 去重）...")
        # 查询所有 room_types，按 institute_id + room_type + bedrooms 分组
        r = await s.execute(text(
            "SELECT institute_id, room_type, bedrooms, bathrooms, "
            "  MIN(price_monthly) as min_price, MAX(price_monthly) as max_price, "
            "  AVG(area_sqm::numeric) as avg_area, "
            "  MIN(deposit_amount) as deposit, MIN(deposit_type) as dep_type, "
            "  MIN(min_stay_months) as min_stay, "
            "  array_agg(DISTINCT name) as names, "
            "  array_agg(DISTINCT description) as descs, "
            "  count(*) as cnt "
            "FROM room_types "
            "WHERE institute_id IS NOT NULL AND room_type IS NOT NULL "
            "GROUP BY institute_id, room_type, bedrooms, bathrooms "
            "ORDER BY institute_id, room_type"
        ))
        ut_map = {}  # (institute_id, room_type_key) → ut_id
        ut_count = 0

        for row in r:
            iid, rtype, beds, baths = row[0], row[1], row[2], row[3]
            min_p, max_p = row[4], row[5]
            avg_area = row[6]
            deposit, dep_type = row[7], row[8]
            min_stay = row[9]
            names, descs = row[10], row[11]

            # 取 base_rent = 最低价
            base_rent = float(min_p) if min_p else 0
            name = (names[0] if names else str(rtype))[:100]
            desc = (descs[0] if descs else name)[:500]
            area = float(avg_area) if avg_area else 30

            ut = await s.execute(text(
                "INSERT INTO unit_types (institute_id, name, bedrooms, bathrooms, "
                "  hall_count, area_sqm, base_rent, deposit_amount, deposit_type, "
                "  min_stay_months, description, status, available_from) "
                "VALUES (:iid, :name, :beds, :baths, 0, :area, :rent, :dep, :dt, "
                "  :stay, :desc, 'available', CURRENT_DATE) RETURNING id"
            ), {
                "iid": iid, "name": name, "beds": beds or 1, "baths": baths or 1,
                "area": area, "rent": base_rent, "dep": deposit, "dt": dep_type,
                "stay": min_stay or 3, "desc": desc,
            })
            ut_id = ut.scalar()
            ut_map[(iid, str(rtype), str(beds))] = ut_id
            ut_count += 1
        await s.flush()
        print(f"  ✓ 创建了 {ut_count} 个 unit_types")

        # ── Step 4: 将 properties → rooms，绑定 unit_type ──
        print("\n[4/5] 迁移 properties → rooms ...")
        # 先添加缺失列
        for col_sql in [
            "ALTER TABLE properties ADD COLUMN IF NOT EXISTS unit_type_id INTEGER",
            "ALTER TABLE properties ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
        ]:
            try:
                await s.execute(text(col_sql))
            except:
                pass
        await s.flush()

        # 为每个 property 找到匹配的 unit_type
        r = await s.execute(text(
            "SELECT p.id, p.district, p.property_type, p.bedrooms, p.institute_id "
            "FROM properties p"
        ))
        room_count = 0
        for row in r:
            pid, dist, ptype, beds, iid = row[0], row[1], row[2], row[3], row[4]
            inst_id = inst_map.get(dist) if dist else iid

            # 匹配 unit_type：按 institute + property_type/room_type + bedrooms
            ut_key1 = (inst_id, str(ptype), str(beds))
            ut_key2 = (inst_id, "studio", "1")  # fallback
            ut_id = ut_map.get(ut_key1)
            if not ut_id:
                # 尝试宽松匹配
                for k, v in ut_map.items():
                    if k[0] == inst_id:
                        ut_id = v
                        break

            if ut_id and inst_id:
                await s.execute(text(
                    "UPDATE properties SET unit_type_id = :ut, institute_id = :iid "
                    "WHERE id = :pid"
                ), {"ut": ut_id, "iid": inst_id, "pid": pid})
                room_count += 1
        await s.flush()
        print(f"  ✓ {room_count} 个 properties 已关联 unit_type + institute")

        # ── Step 5: 为 unit_types 填充 floor_pricing ──
        print("\n[5/5] 填充 unit_types 辅助字段...")
        await s.execute(text(
            "UPDATE unit_types SET floor_pricing = '[]'::jsonb WHERE floor_pricing IS NULL"
        ))
        # 更新 building_images：链接到 institutes
        try:
            await s.execute(text("ALTER TABLE building_images ADD COLUMN IF NOT EXISTS institute_id INTEGER"))
        except:
            pass
        await s.flush()

        await s.commit()
        print("\n" + "=" * 60)
        print("✅ 迁移完成！")
        print(f"   institutes: {inst_count}")
        print(f"   unit_types: {ut_count}")
        print(f"   rooms (linked): {room_count}")
        print("=" * 60)

asyncio.run(migrate())
