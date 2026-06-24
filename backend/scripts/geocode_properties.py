import asyncio
import os
import sys
from pathlib import Path

# Ensure backend root is the working directory so .env is found
backend_root = Path(__file__).resolve().parent.parent
os.chdir(backend_root)
sys.path.insert(0, str(backend_root))

from sqlalchemy import select, update

from app.db.session import async_session_maker
from app.models.property import Property
from app.services.geocoding_service import AmapGeocodingService


async def geocode_properties(dry_run: bool = False):
    geocoder = AmapGeocodingService()

    async with async_session_maker() as session:
        result = await session.execute(
            select(Property).where(
                (Property.latitude == None) | (Property.longitude == None)
            )
        )
        properties = result.scalars().all()

        if not properties:
            print("[OK] All properties already have coordinates!")
            return

        print(f"Found {len(properties)} properties without coordinates:\n")

        success = 0
        failed = 0

        for prop in properties:
            address = f"{prop.district} {prop.address}" if prop.district else prop.address
            print(f"  [{prop.id}] {prop.title}")
            print(f"       Address: {address}")

            try:
                geo = await geocoder.geocode(address)
                lat = float(geo.latitude)
                lng = float(geo.longitude)

                if not dry_run:
                    await session.execute(
                        update(Property)
                        .where(Property.id == prop.id)
                        .values(latitude=geo.latitude, longitude=geo.longitude)
                    )
                    await session.commit()

                print(f"       [OK] lat={lat:.6f}, lng={lng:.6f}  ({geo.formatted_address})")
                success += 1

            except Exception as e:
                print(f"       [FAIL] {e}")
                failed += 1

            await asyncio.sleep(0.3)

        if not dry_run:
            print(f"\nDone: {success} updated, {failed} failed")
        else:
            print(f"\n[Dry run] Would update {success} properties, {failed} would fail")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(geocode_properties(dry_run=dry))
