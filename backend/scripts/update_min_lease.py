import asyncio
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import asyncpg

load_dotenv()

# 使用同步驱动的 DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 转换为 asyncpg 格式
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

print(f"Connecting with: {DATABASE_URL}")

async def main():
    parsed = urlparse(DATABASE_URL)
    conn = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        database=parsed.path[1:],
        host=parsed.hostname,
        port=parsed.port
    )
    
    try:
        await conn.execute("UPDATE properties SET min_lease_months = 1 WHERE min_lease_months = 12")
        print("Updated min_lease_months to 1")
    except Exception as e:
        print(f"Update failed: {e}")
    
    rows = await conn.fetch("SELECT id, title, min_lease_months, max_lease_months FROM properties")
    for row in rows:
        print(dict(row))
    
    await conn.close()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
