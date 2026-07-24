"""V1 → V2 数据迁移（健壮版）
先删干净 V2 表，再从 V1 重新建。
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from app.db.session import async_session_maker

async def migrate():
    async with async_session_maker() as s:
        print("=" * 50)

        # ── 0. 清 V2 表 ──
        print("[0] Drop V2 tables...")
        for tbl in ['room_images', 'rooms', 'unit_types']:
            await s.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        # 保留旧 institutes，重置序列
        await s.execute(text("DELETE FROM building_images"))
        await s.execute(text("DELETE FROM building_staff"))
        # 重置 institutes 序列
        await s.execute(text("SELECT setval('institutes_id_seq', 1, false)"))
        await s.execute(text("DELETE FROM institutes"))
        await s.flush()
        print("  Done")

        # ── 1. 建表 ──
        print("[1] Create V2 tables...")
        await s.execute(text("""
            CREATE TABLE unit_types (
                id SERIAL PRIMARY KEY,
                institute_id INTEGER NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                bedrooms INTEGER DEFAULT 0 NOT NULL,
                bathrooms INTEGER DEFAULT 1 NOT NULL,
                hall_count INTEGER DEFAULT 0 NOT NULL,
                area_sqm NUMERIC(8,2),
                base_rent NUMERIC(12,2) NOT NULL DEFAULT 0,
                deposit_amount INTEGER,
                deposit_type VARCHAR(30),
                lease_start VARCHAR(50), lease_end VARCHAR(50),
                currency VARCHAR(10) DEFAULT 'CNY',
                special_offer TEXT,
                floor_pricing JSONB DEFAULT '[]',
                amenities VARCHAR(50)[],
                image_urls VARCHAR(500)[],
                description TEXT,
                available_from DATE,
                min_stay_months INTEGER DEFAULT 3 NOT NULL,
                status VARCHAR(30) DEFAULT 'available' NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await s.execute(text("""
            CREATE TABLE rooms (
                id SERIAL PRIMARY KEY,
                landlord_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                unit_type_id INTEGER REFERENCES unit_types(id) ON DELETE SET NULL,
                institute_id INTEGER,
                room_number VARCHAR(20), title VARCHAR(200),
                description TEXT, address VARCHAR(500), district VARCHAR(100),
                price_monthly NUMERIC(12,2), area_sqm NUMERIC(8,2),
                bedrooms INTEGER, bathrooms INTEGER,
                property_type VARCHAR(50), deposit_amount INTEGER,
                deposit_type VARCHAR(50), service_fee_rate FLOAT,
                country VARCHAR(100), latitude NUMERIC(9,6), longitude NUMERIC(9,6),
                rent_type VARCHAR(50), rental_rules JSONB, embedding TEXT,
                floor INTEGER, building_block VARCHAR(20),
                special_discount VARCHAR(200), city VARCHAR(100),
                available_from DATE,
                status VARCHAR(30) DEFAULT 'available' NOT NULL,
                min_stay_months INTEGER DEFAULT 3,
                min_lease_months INTEGER, max_lease_months INTEGER,
                version INTEGER DEFAULT 1 NOT NULL,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await s.execute(text("""
            CREATE TABLE room_images (
                id SERIAL PRIMARY KEY,
                room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL UNIQUE,
                original_name VARCHAR(255) NOT NULL,
                mime_type VARCHAR(50) NOT NULL,
                file_size INTEGER NOT NULL,
                sort_order INTEGER DEFAULT 0 NOT NULL,
                is_primary BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await s.execute(text("CREATE INDEX IF NOT EXISTS ix_unit_types_iid ON unit_types(institute_id)"))
        await s.execute(text("CREATE INDEX IF NOT EXISTS ix_rooms_utid ON rooms(unit_type_id)"))
        await s.execute(text("CREATE INDEX IF NOT EXISTS ix_rooms_iid ON rooms(institute_id)"))
        await s.execute(text("CREATE INDEX IF NOT EXISTS ix_room_images_rid ON room_images(room_id)"))
        await s.flush()
        print("  Tables created")

        # ── 2. 从 properties 聚合 institutes ──
        print("[2] Create institutes...")
        # 先确保 country 列存在
        try:
            await s.execute(text("ALTER TABLE institutes ADD COLUMN IF NOT EXISTS country VARCHAR(100)"))
        except: pass
        await s.flush()

        r = await s.execute(text(
            "SELECT DISTINCT district, country, MIN(latitude) as lat, MIN(longitude) as lng, "
            "MIN(address) as addr FROM properties WHERE district IS NOT NULL "
            "GROUP BY district, country ORDER BY country, district"
        ))
        inst_map = {}
        for row in r:
            dist, country, lat, lng, addr = row
            name = (dist.split("-")[-1] if "-" in dist else dist) + " 公寓"
            ins = await s.execute(text(
                "INSERT INTO institutes (name, address, latitude, longitude, status, created_by, country) "
                "VALUES (:n, :a, :lat, :lng, 'active', 1, :c) RETURNING id"
            ), {"n": name, "a": addr or dist,
                "lat": float(lat) if lat else None,
                "lng": float(lng) if lng else None, "c": country})
            inst_map[(dist, country)] = ins.scalar()
        print(f"  {len(inst_map)} institutes created")

        # ── 3. room_types → unit_types ──
        print("[3] room_types → unit_types...")
        # 为每个 property 找到 institute
        r = await s.execute(text("SELECT id, district, country FROM properties"))
        prop_inst = {}
        for row in r:
            key = (row[1], row[2])
            if key in inst_map:
                prop_inst[row[0]] = inst_map[key]

        # 合并去重
        r = await s.execute(text(
            "SELECT property_id, room_type, name, bedrooms, bathrooms, "
            "price_monthly, area_sqm, deposit_amount, deposit_type, "
            "min_stay_months, amenities, description, status, available_from "
            "FROM room_types WHERE property_id IS NOT NULL ORDER BY id"
        ))
        ut_map = {}  # merge_key → ut_id
        for row in r:
            pid, rtype, rt_name, beds, baths = row[0:5]
            price, area, dep_amt, dep_type = row[5:9]
            min_stay, amenities, desc, status, avail_from = row[9:14]
            iid = prop_inst.get(pid)
            if not iid: continue

            mk = (iid, str(rtype), str(beds or 0), str(baths or 0))
            if mk not in ut_map:
                ut = await s.execute(text(
                    "INSERT INTO unit_types (institute_id, name, bedrooms, bathrooms, "
                    "area_sqm, base_rent, deposit_amount, deposit_type, "
                    "min_stay_months, amenities, description, status, available_from) "
                    "VALUES (:iid,:n,:beds,:baths,:area,:rent,:dep,:dt,:stay,:amen,:desc,:st,:af) "
                    "RETURNING id"
                ), {"iid":iid, "n":(rt_name or str(rtype))[:100],
                    "beds":beds or 1, "baths":baths or 1,
                    "area":float(area) if area else 30,
                    "rent":float(price) if price else 0,
                    "dep":dep_amt, "dt":dep_type,
                    "stay":min_stay or 3, "amen":amenities,
                    "desc":desc or "", "st":status or "available",
                    "af":avail_from})
                ut_map[mk] = ut.scalar()
        print(f"  {len(ut_map)} unit_types created")

        # ── 4. properties → rooms ──
        print("[4] properties → rooms...")
        r = await s.execute(text("SELECT * FROM properties ORDER BY id"))
        cols = list(r.keys())
        room_count = 0
        for row in r:
            d = dict(zip(cols, row))
            pid = d['id']
            iid = prop_inst.get(pid)
            if not iid: continue
            # find unit_type
            mk = (iid, str(d.get('property_type','apartment')), str(d.get('bedrooms',0)), "1")
            ut_id = ut_map.get(mk)
            if not ut_id:
                for k, v in ut_map.items():
                    if k[0] == iid: ut_id = v; break
            if not ut_id: continue

            await s.execute(text(
                "INSERT INTO rooms (id, landlord_id, unit_type_id, institute_id, room_number, "
                "title, description, address, district, price_monthly, area_sqm, "
                "bedrooms, bathrooms, property_type, deposit_amount, deposit_type, "
                "service_fee_rate, country, latitude, longitude, rent_type, rental_rules, "
                "embedding, floor, building_block, special_discount, city, "
                "available_from, status, min_stay_months, min_lease_months, max_lease_months, "
                "version, deleted_at) "
                "VALUES (:id,:lid,:ut,:iid,:rn,:t,:desc,:addr,:dist,:pr,:area,"
                ":beds,:baths,:pt,:dep,:dt,:sfr,:c,:lat,:lng,:rt,:rr,"
                ":emb,:fl,:bb,:sd,:city,:af,:st,:ms,:ml,:xl,:ver,:del)"
            ), {
                "id": pid, "lid": d.get('landlord_id'), "ut": ut_id, "iid": iid,
                "rn": d.get('room_number'), "t": d.get('title'), "desc": d.get('description'),
                "addr": d.get('address'), "dist": d.get('district'),
                "pr": d.get('price_monthly'), "area": d.get('area_sqm'),
                "beds": d.get('bedrooms'), "baths": d.get('bathrooms'),
                "pt": d.get('property_type'), "dep": d.get('deposit_amount'),
                "dt": d.get('deposit_type'), "sfr": d.get('service_fee_rate'),
                "c": d.get('country'), "lat": d.get('latitude'), "lng": d.get('longitude'),
                "rt": d.get('rent_type'), "rr": d.get('rental_rules'),
                "emb": d.get('embedding'), "fl": d.get('floor'),
                "bb": d.get('building_block'), "sd": d.get('special_discount'),
                "city": d.get('city'), "af": d.get('available_from'),
                "st": d.get('status', 'available'),
                "ms": d.get('min_stay_months'), "ml": d.get('min_lease_months'),
                "xl": d.get('max_lease_months'), "ver": d.get('version', 1),
                "del": d.get('deleted_at'),
            })
            room_count += 1
        print(f"  {room_count} rooms migrated")

        # ── 5. property_images → room_images ──
        print("[5] property_images → room_images...")
        r = await s.execute(text(
            "INSERT INTO room_images (id, room_id, filename, original_name, mime_type, "
            "file_size, sort_order, is_primary, created_at, updated_at) "
            "SELECT id, property_id, filename, original_name, mime_type, "
            "file_size, sort_order, is_primary, created_at, updated_at "
            "FROM property_images WHERE property_id IN (SELECT id FROM rooms)"
        ))
        img_cnt = r.rowcount
        print(f"  {img_cnt} images migrated")

        # ── 6. building_images 种子 ──
        print("[6] Seed building_images...")
        await s.execute(text(
            "INSERT INTO building_images (institute_id, filename, original_name, "
            "mime_type, file_size, sort_order, is_primary) "
            "SELECT DISTINCT ON (r.institute_id) r.institute_id, "
            "ri.filename, ri.original_name, ri.mime_type, ri.file_size, 0, TRUE "
            "FROM rooms r JOIN room_images ri ON ri.room_id = r.id AND ri.is_primary = TRUE "
            "WHERE r.institute_id IS NOT NULL"
        ))

        # ── 7. 更新序列 ──
        await s.execute(text("SELECT setval('rooms_id_seq', COALESCE((SELECT MAX(id) FROM rooms), 1))"))
        await s.execute(text("SELECT setval('room_images_id_seq', COALESCE((SELECT MAX(id) FROM room_images), 1))"))
        await s.execute(text("SELECT setval('unit_types_id_seq', COALESCE((SELECT MAX(id) FROM unit_types), 1))"))

        await s.commit()
        print("\n" + "=" * 50)
        r = await s.execute(text("SELECT count(*) FROM institutes")); ic = r.scalar()
        r = await s.execute(text("SELECT count(*) FROM unit_types")); uc = r.scalar()
        r = await s.execute(text("SELECT count(*) FROM rooms")); rc = r.scalar()
        r = await s.execute(text("SELECT count(*) FROM room_images")); ric = r.scalar()
        print(f"  institutes: {ic}")
        print(f"  unit_types: {uc}")
        print(f"  rooms: {rc}")
        print(f"  room_images: {ric}")
        print("=" * 50)
        print("DONE - V1 data migrated to V2 three-tier!")

asyncio.run(migrate())
