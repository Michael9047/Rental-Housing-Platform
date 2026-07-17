import psycopg

conn = psycopg.connect("postgresql://rental:rental@localhost:5432/rental_housing")
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'bookings'
    ORDER BY ordinal_position
""")
rows = cur.fetchall()
print("Bookings 表字段:")
for r in rows:
    print(f"  {r[0]}: {r[1]}")

# 检查是否有 application_data 和 lease_months, total_rent
cols = [r[0] for r in rows]
print("\n检查需要的字段:")
for c in ['application_data', 'lease_months', 'total_rent']:
    print(f"  {c}: {'存在' if c in cols else '不存在'}")

cur.close()
conn.close()
