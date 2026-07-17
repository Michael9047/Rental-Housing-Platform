import psycopg

conn = psycopg.connect("postgresql://rental:rental@localhost:5432/rental_housing")
cur = conn.cursor()

cur.execute("""
    UPDATE properties
    SET min_lease_months = 12,
        max_lease_months = 60
    WHERE min_lease_months IS NULL
""")
print(f"更新了 {cur.rowcount} 条房源记录")

cur.execute("SELECT id, title, min_lease_months, max_lease_months FROM properties WHERE id = 1")
row = cur.fetchone()
print(f"房源 1: min={row[2]}, max={row[3]}")

conn.commit()
cur.close()
conn.close()
