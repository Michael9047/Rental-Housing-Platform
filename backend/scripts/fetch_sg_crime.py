"""Fetch data.gov.sg crime data and write to sg_crime_data.py"""
import asyncio, httpx, json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DATAGOV_BASE = "https://data.gov.sg/api/action/datastore_search"
CRIME_RID = "d_5767147db6e5b4c4cfa874db132fef39"
UML_RID = "d_b6dc6308d208f668232b4f9e171af3a4"

async def fetch_all(rid, label):
    records = []
    offset = 0
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            r = await client.get(DATAGOV_BASE, params={
                "resource_id": rid, "limit": 100, "offset": offset,
            })
            if r.status_code == 429:
                print(f"{label}: rate limited, waiting 10s...")
                await asyncio.sleep(10)
                continue
            if r.status_code != 200:
                print(f"{label}: HTTP {r.status_code}")
                break
            data = r.json()
            if not data.get("success"):
                break
            recs = data.get("result", {}).get("records", [])
            if not recs:
                break
            records.extend(recs)
            offset += len(recs)
            print(f"{label}: {offset}")
            if offset >= data.get("result", {}).get("total", 0):
                break
            await asyncio.sleep(0.3)
    return records

def structure(records):
    data = {}
    current_key = None
    for rec in records:
        ds = rec.get("DataSeries", "")
        if not ds.startswith("    "):
            current_key = ds
        elif current_key:
            ctype = ds.strip()
            val = int(rec.get("2024", "0")) if rec.get("2024", "0").isdigit() else 0
            if val > 0:
                data.setdefault(current_key, {})[ctype] = val
    return {k: v for k, v in data.items() if " - " in k and "Unknown" not in k}

async def main():
    crime = await fetch_all(CRIME_RID, "Crime")
    uml = await fetch_all(UML_RID, "UML")

    npc_crime = structure(crime)
    npc_uml = structure(uml)

    print(f"\nCrime NPCs: {len(npc_crime)}, UML NPCs: {len(npc_uml)}")

    # Write sg_crime_data.py
    target = os.path.join(os.path.dirname(__file__), "..", "app", "services", "sg_crime_data.py")

    # Read existing NPC centers
    old_centers = {}
    if os.path.exists(target):
        ns = {}
        exec(open(target, encoding="utf-8").read(), ns)
        old_centers = ns.get("SG_NPC_CENTERS", {})

    with open(target, "w", encoding="utf-8") as f:
        f.write("# 新加坡 NPC 犯罪数据（2024 年度，来源 data.gov.sg）\n")
        f.write("# 数据刷新: python scripts/fetch_sg_crime.py\n\n")
        f.write(f"SG_CRIME_RECORDS: dict[str, dict[str, int]] = {json.dumps(npc_crime, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"SG_UML_RECORDS: dict[str, dict[str, int]] = {json.dumps(npc_uml, indent=2, ensure_ascii=False)}\n\n")
        f.write("# NPC 中心坐标（用于最近邻匹配）\n")
        f.write("SG_NPC_CENTERS: dict[str, tuple[float, float]] = {\n")
        all_npcs = sorted(set(list(npc_crime.keys()) + list(npc_uml.keys())))
        for npc in all_npcs:
            existing = old_centers.get("SG_NPC_CENTERS", {}).get(npc)
            if existing:
                f.write(f'    "{npc}": ({existing[0]}, {existing[1]}),\n')
            else:
                short = npc.split(" - ")[-1].replace(" NPC", "")
                f.write(f'    "{npc}": (1.35, 103.85),  # TODO: set real coords for {short}\n')
        f.write("}\n")

    print(f"Wrote {target}")
    print(f"Crime types: {set().union(*[set(v.keys()) for v in npc_crime.values()])}")
    print(f"UML types: {set().union(*[set(v.keys()) for v in npc_uml.values()])}")

asyncio.run(main())
