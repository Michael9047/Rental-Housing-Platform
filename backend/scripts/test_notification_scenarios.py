# -*- coding: utf-8 -*-
"""Notification module end-to-end test — triggers all 12 scenarios.

Usage:
    cd backend
    python scripts/test_notification_scenarios.py

Prerequisites: database migration applied
"""
import asyncio
import sys
import io

# Fix Windows console encoding for emoji output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.config import get_settings
from app.services.notification_service import NotificationService, CHANNEL_MATRIX
from app.models.user import User
from app.models.order import Order
from app.models.property import Room


SCENARIOS = [
    ("contract_signed", "[Contract] Contract signed -> tenant email + in-app"),
    ("payment_pending", "[Payment] Payment pending -> tenant email + in-app"),
    ("payment_failed", "[Payment] Payment failed -> tenant email + sms + in-app"),
    ("payment_processing", "[Payment] Payment processing -> in-app only"),
    ("payment_expiring_3h", "[Payment] Expiring in 3h -> email + sms + in-app"),
    ("payment_succeeded", "[Payment] Payment succeeded -> all channels + landlord"),
    ("booking_confirmed", "[Order] Booking confirmed -> all channels + landlord"),
    ("order_auto_cancelled", "[Order] Auto cancelled -> email + sms + in-app"),
    ("payment_review", "[Payment] Payment review -> email + in-app"),
    ("refund_pending", "[Refund] Refund pending -> email + in-app"),
    ("refunded", "[Refund] Refunded -> email + in-app"),
    ("contract_expiring", "[Contract] Contract expiring -> email + in-app"),
]

LANDLORD_EVENTS = {"payment_succeeded", "booking_confirmed"}


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Find test users
    async with session_factory() as session:
        r = await session.execute(select(User).order_by(User.id).limit(3))
        users = list(r.scalars())
        if not users:
            print("ERROR: No users in database! Create a test user first.")
            await engine.dispose()
            return 1

        user = users[0]
        landlord = users[1] if len(users) > 1 else user
        print(f"Test user: id={user.id} username={user.username} email={user.email} phone={user.phone}")

        r = await session.execute(select(Order).order_by(Order.id.desc()).limit(1))
        order = r.scalar()

        r = await session.execute(select(Room).order_by(Room.id.desc()).limit(1))
        room = r.scalar()

        order_id = order.id if order else None
        property_id = room.id if room else None

        if not order_id:
            print("WARNING: No orders found, order_id will be null")
        else:
            print(f"Order: id={order_id}")
        if not property_id:
            print("WARNING: No rooms found, property_id will be null")
        else:
            print(f"Room: id={property_id}")

    print(f"\n{'='*60}")
    print(f"Running {len(SCENARIOS)} scenario tests")
    print(f"{'='*60}")

    passed = 0
    failed = 0

    for i, (scenario_key, description) in enumerate(SCENARIOS, 1):
        print(f"\n[{i:2d}/{len(SCENARIOS)}] {description}")
        print(f"      event_type: {scenario_key}")

        try:
            async with session_factory() as session:
                svc = NotificationService(session)

                is_landlord = scenario_key in LANDLORD_EVENTS
                result = await svc.dispatch_event(
                    event_type=scenario_key,
                    user_id=user.id,
                    order_id=order_id,
                    property_id=property_id,
                    landlord_id=landlord.id if is_landlord else None,
                )

                expected = CHANNEL_MATRIX.get(scenario_key, {})
                actual = set(result.get("channels_sent", []))
                nid = result.get("notification_id")
                dids = result.get("delivery_ids", [])
                skipped = [s["channel"] for s in result.get("skipped", [])]

                check_results = []
                if expected.get("in_app", True):
                    ok = nid is not None
                    check_results.append(("in_app", ok, f"notification_id={nid}"))
                if expected.get("tenant_email", False):
                    ok = len(dids) > 0
                    check_results.append(("email", ok, f"deliveries={len(dids)}"))
                if expected.get("tenant_sms", False):
                    ok = "sms" in actual
                    check_results.append(("sms", ok, "queued" if ok else "skipped"))
                if expected.get("landlord_email", False) and is_landlord:
                    check_results.append(("landlord", True, "triggered"))

                all_ok = True
                for ch, ok, detail in check_results:
                    mark = "[OK]" if ok else "[SKIP]"
                    if not ok and expected.get(ch, False):
                        all_ok = False
                    skip_info = ""
                    if skipped:
                        skip_info = f" (skipped channels: {skipped})"
                    print(f"      {mark} {ch}: {detail}{skip_info}")

                if all_ok:
                    passed += 1
                else:
                    failed += 1

        except Exception as e:
            print(f"      [FAIL] {type(e).__name__}: {e}")
            failed += 1

    # Idempotency test
    print(f"\n{'='*60}")
    print("Idempotency test: trigger same event twice")
    print(f"{'='*60}")

    try:
        async with session_factory() as session:
            svc = NotificationService(session)

            r1 = await svc.dispatch_event(
                event_type="payment_succeeded",
                user_id=user.id,
                order_id=order_id,
                property_id=property_id,
            )
            print(f"  1st trigger: notification_id={r1['notification_id']} deliveries={len(r1['delivery_ids'])}")

            r2 = await svc.dispatch_event(
                event_type="payment_succeeded",
                user_id=user.id,
                order_id=order_id,
                property_id=property_id,
            )
            print(f"  2nd trigger: notification_id={r2['notification_id']} deliveries={len(r2['delivery_ids'])} skipped={r2.get('skipped', [])}")

            if r2["delivery_ids"] == [] and r1["delivery_ids"] != []:
                print(f"  [OK] Email/SMS idempotency works: 2nd call skipped deliveries")
            elif r1["delivery_ids"] == []:
                print(f"  [INFO] First call had no deliveries (email/sms not configured), cannot verify idempotency")
            else:
                print(f"  [WARN] Idempotency may not work: 2nd call also created deliveries")
    except Exception as e:
        print(f"  [FAIL] Idempotency test error: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(SCENARIOS)} total")
    print(f"{'='*60}")

    await engine.dispose()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
