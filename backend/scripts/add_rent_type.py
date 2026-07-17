import asyncio
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import asyncpg

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

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
        await conn.execute("CREATE TYPE rent_type AS ENUM ('monthly', 'quarterly', 'yearly')")
        print("Type created")
    except Exception as e:
        print(f"Type may already exist: {e}")
    
    try:
        await conn.execute("ALTER TABLE properties ADD COLUMN rent_type rent_type DEFAULT 'monthly'")
        print("Column added")
    except Exception as e:
        print(f"Column may already exist: {e}")
    
    try:
        await conn.execute("UPDATE properties SET rent_type = 'monthly' WHERE rent_type IS NULL")
        print("Updated existing rows")
    except Exception as e:
        print(f"Update failed: {e}")
    
    await conn.close()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
