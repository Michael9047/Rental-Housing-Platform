import psycopg

conn = psycopg.connect("postgresql://rental:rental@localhost:5432/rental_housing")
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'properties'
    AND column_name LIKE '%lease%'
""")
rows = cur.fetchall()
print("Properties 表中的租期相关字段:", rows)

# 检查 min_lease_months 是否存在
has_min = any(r[0] == "min_lease_months" for r in rows)
has_max = any(r[0] == "max_lease_months" for r in rows)

if not has_min:
    print("添加 min_lease_months 字段...")
    cur.execute("""
        ALTER TABLE properties
        ADD COLUMN IF NOT EXISTS min_lease_months INTEGER NOT NULL DEFAULT 12
    """)
    print("已添加 min_lease_months")

if not has_max:
    print("添加 max_lease_months 字段...")
    cur.execute("""
        ALTER TABLE properties
        ADD COLUMN IF NOT EXISTS max_lease_months INTEGER DEFAULT 60
    """)
    print("已添加 max_lease_months")

conn.commit()

# 再查一遍确认
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'properties'
    AND column_name LIKE '%lease%'
""")
rows = cur.fetchall()
print("\n最终字段状态:", rows)

cur.close()
conn.close()
