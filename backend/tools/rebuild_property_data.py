"""数据重建工具：从房间标题提取楼栋名，重建 institute/unit_type/room 三层"""
import asyncio, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.session import async_session_maker
from sqlalchemy import text

def extract_building(title):
    if not title: return None
    m = re.match(r'^(.+?)(?:公寓|的?\s*(精装|Ensuite|Studio|一室|一厅|HDB|高层|学生|单间|双人|独立|安静|温馨|舒适))', title)
    if m: return m.group(1).strip().rstrip('的')
    m = re.match(r'^([A-Z][a-zA-Z\s]+(?:Tower|Garden|Heights|Woods|Grove|Peak|Vista|Point|Plaza|Court|Park|Place|Hill|Green|Mansion|Manor|Lodge|House|Residence|Terrace|Canopy|Cascadia|Centris|Horizon))', title)
    if m: return m.group(1).strip()
    m = re.match(r'^(NTU|NUS)\s*(.+?)(?:的|精装|公寓|Studio|一室|Ensuite|HDB|附近|周边)', title)
    if m: return m.group(2).strip().rstrip('的') if len(m.group(2)) > 4 else title[:25]
    return title[:30] if len(title) > 30 else title

async def rebuild():
    async with async_session_maker() as s:
        print("Step 1: Load rooms")
        r = await s.execute(text("""
            SELECT r.id, r.title, r.country, r.district, r.city,
                   r.institute_id, r.unit_type_id, r.latitude, r.longitude
            FROM rooms r WHERE r.deleted_at IS NULL ORDER BY r.country, r.title
        """))
        rows = r.fetchall()
        rooms = []
        for row in rows:
            rooms.append(dict(id=row[0], title=row[1], country=row[2], district=row[3],
                city=row[4], inst_id=row[5], ut_id=row[6], lat=row[7], lng=row[8]))
        print(f"  {len(rooms)} rooms total")

        for country in ['SG', 'GB']:
            cr = [rm for rm in rooms if rm['country'] == country]
            if not cr: continue

            groups = {}
            for rm in cr:
                bldg = extract_building(rm['title'])
                if not bldg: bldg = rm['title'][:30]
                groups.setdefault(bldg, []).append(rm)

            print(f"\n{country}: {len(groups)} buildings from {len(cr)} rooms")
            for bldg, rms in sorted(groups.items(), key=lambda x: -len(x[1])):
                print(f"  [{len(rms):2d}] {bldg[:40]}")

            # Step A: Create new institutes + clone unit_types + update rooms
            old_ids = {rm['inst_id'] for rm in cr if rm['inst_id']}
            building_to_inst = {}
            ut_created = 0

            for bldg, rms in groups.items():
                first = rms[0]
                # Create new institute
                result = await s.execute(text("""
                    INSERT INTO institutes (name, country, district, city, latitude, longitude, status, created_by)
                    VALUES (:n, :c, :d, :ct, :lat, :lng, 'active', 1) RETURNING id
                """), {
                    'n': bldg[:200], 'c': country,
                    'd': first['district'], 'ct': first['city'],
                    'lat': str(first['lat']) if first['lat'] else None,
                    'lng': str(first['lng']) if first['lng'] else None,
                })
                new_inst_id = result.scalar()
                building_to_inst[bldg] = new_inst_id

                # Clone unit_types used by rooms in this building
                ut_map = {}  # old_ut_id -> new_ut_id
                for rm in rms:
                    if not rm['ut_id'] or rm['ut_id'] in ut_map: continue
                    old_ut_id = rm['ut_id']

                    r2 = await s.execute(text(
                        "SELECT name, bedrooms, bathrooms, area_sqm, base_rent, min_stay_months FROM unit_types WHERE id = :id"
                    ), {'id': old_ut_id})
                    ut_row = r2.fetchone()
                    if not ut_row: continue

                    r4 = await s.execute(text("""
                        INSERT INTO unit_types (institute_id, name, bedrooms, bathrooms, area_sqm, base_rent, min_stay_months, status)
                        VALUES (:iid, :n, :br, :ba, :area, :rent, :min_stay, 'available') RETURNING id
                    """), {'iid': new_inst_id, 'n': ut_row[0], 'br': ut_row[1], 'ba': ut_row[2],
                           'area': str(ut_row[3]) if ut_row[3] else None,
                           'rent': str(ut_row[4]) if ut_row[4] else '0',
                           'min_stay': ut_row[5] or 3})
                    ut_map[old_ut_id] = r4.scalar()
                    ut_created += 1

                # Update rooms: new institute + new unit_type
                for rm in rms:
                    new_ut = ut_map.get(rm['ut_id']) if rm['ut_id'] else None
                    await s.execute(text(
                        "UPDATE rooms SET institute_id = :iid, unit_type_id = :ut WHERE id = :rid"
                    ), {'iid': new_inst_id, 'ut': new_ut, 'rid': rm['id']})

            print(f"  created {len(building_to_inst)} institutes, {ut_created} unit_types")

            # Step B: Delete old institutes (CASCADE handles old unit_types)
            for oid in old_ids:
                await s.execute(text("DELETE FROM institutes WHERE id = :id"), {'id': oid})
            print(f"  deleted {len(old_ids)} old institutes")

        # Clean orphan unit_types (no rooms, no institute)
        await s.execute(text("""
            DELETE FROM unit_types WHERE id IN (
                SELECT ut.id FROM unit_types ut
                LEFT JOIN rooms r ON r.unit_type_id = ut.id AND r.deleted_at IS NULL
                WHERE r.id IS NULL
            )
        """))
        await s.commit()
        print("\n=== DONE ===")

asyncio.run(rebuild())
