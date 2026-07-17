import psycopg

conn = psycopg.connect("postgresql://rental:rental@localhost:5432/rental_housing")
cur = conn.cursor()

cur.execute("SELECT id, title, status, min_lease_months, price_monthly FROM properties ORDER BY id")
rows = cur.fetchall()
print(f"共有 {len(rows)} 套房源:")
for r in rows:
    print(f"  ID={r[0]}, title={r[1]}, status={r[2]}, min_lease={r[3]}, price={r[4]}")

cur.close()
conn.close()
