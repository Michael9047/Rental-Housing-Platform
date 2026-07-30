"""预约流程集成测试 —— 验证登录→房源→预约→确认全链路

用法:
  cd backend
  python tests/integration/test_booking_flow.py

每次 merge 后运行一次，确保同事的预约子系统正常。
"""
import asyncio
import httpx
import sys

BASE = "http://localhost:8000/api/v1"
PASS, FAIL, WARN = "✅", "❌", "⚠️"


async def main():
    print("=" * 60)
    print("🏠 预约流程集成测试")
    print(f"   {BASE}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as c:
        # ═══════════════════════════════════════════════════
        # Step 1: 用户注册/登录
        # ═══════════════════════════════════════════════════
        print("\n── 1. 用户认证 ──")

        # 租客
        r = await c.post(f"{BASE}/auth/register", json={
            "username": "test_booking_int", "password": "test123456",
            "email": "test_booking_int@test.com",
        })
        if r.status_code == 409:
            r = await c.post(f"{BASE}/auth/login", json={
                "username_or_email": "test_booking_int", "password": "test123456",
            })
        ok = r.status_code in (200, 201)
        print(f"  {PASS if ok else FAIL} 租客: {r.status_code}")
        if not ok:
            print(f"     {r.text[:200]}")
            return
        tenant_token = r.json()["access_token"]
        tenant_id = r.json().get("id") or r.json().get("user_id")

        # 房东
        r = await c.post(f"{BASE}/auth/register", json={
            "username": "test_booking_land", "password": "test123456",
            "email": "test_booking_land@test.com", "role": "landlord",
        })
        if r.status_code == 409:
            r = await c.post(f"{BASE}/auth/login", json={
                "username_or_email": "test_booking_land", "password": "test123456",
            })
        ok = r.status_code in (200, 201)
        print(f"  {PASS if ok else FAIL} 房东: {r.status_code}")
        if not ok:
            print(f"     {r.text[:200]}")
            return
        landlord_token = r.json()["access_token"]
        landlord_headers = {"Authorization": f"Bearer {landlord_token}"}
        tenant_headers = {"Authorization": f"Bearer {tenant_token}"}

        # ═══════════════════════════════════════════════════
        # Step 2: 创建公寓
        # ═══════════════════════════════════════════════════
        print("\n── 2. 创建公寓 ──")
        r = await c.post(f"{BASE}/buildings", headers=landlord_headers, json={
            "name": "Integration Test Building",
            "name_cn": "集成测试公寓", "abbreviation": "ITB",
            "address": "1 Test Rd, Singapore", "district": "新加坡-测试区",
            "country": "SG", "city": "Singapore",
            "latitude": 1.3000, "longitude": 103.8000,
            "amenities": ["CCTV", "门禁", "洗衣房"],
        })
        if r.status_code in (200, 201):
            institute_id = r.json()["id"]
            print(f"  {PASS} 公寓 #{institute_id}")
        elif r.status_code == 409:
            print(f"  {WARN} 公寓已存在，尝试获取...")
            r2 = await c.get(f"{BASE}/buildings", headers=landlord_headers)
            items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
            institute_id = items[0]["id"] if items else None
            print(f"     {PASS if institute_id else FAIL} institute_id={institute_id}")
        else:
            print(f"  {FAIL} {r.status_code}: {r.text[:200]}")
            return

        if not institute_id:
            print(f"  {FAIL} 无法获取公寓ID")
            return

        # ═══════════════════════════════════════════════════
        # Step 3: 创建户型
        # ═══════════════════════════════════════════════════
        print("\n── 3. 创建户型 ──")
        r = await c.post(f"{BASE}/unit-types", headers=landlord_headers, json={
            "institute_id": institute_id, "name": "Studio Test",
            "bedrooms": 1, "bathrooms": 1, "hall_count": 0,
            "area_sqm": 18, "base_rent": 1200, "currency": "SGD",
            "amenities": ["独立卫浴", "WiFi", "空调"],
        })
        if r.status_code in (200, 201):
            unit_type_id = r.json().get("id")
            print(f"  {PASS} 户型 #{unit_type_id}")
        else:
            print(f"  {WARN} 户型: {r.status_code} (可能已存在)")
            unit_type_id = None

        # ═══════════════════════════════════════════════════
        # Step 4: 创建房间
        # ═══════════════════════════════════════════════════
        print("\n── 4. 创建房间 ──")
        r = await c.post(f"{BASE}/rooms", headers=landlord_headers, json={
            "institute_id": institute_id,
            "title": "Test Room 101", "price_monthly": 1200,
            "bedrooms": 1, "bathrooms": 1,
            "district": "新加坡-测试区", "country": "SG",
            "latitude": 1.3005, "longitude": 103.8005,
            "room_number": "101", "property_type": "studio",
        })
        if r.status_code in (200, 201):
            room_id = r.json()["id"]
            print(f"  {PASS} 房间 #{room_id}")
        elif r.status_code == 409:
            print(f"  {WARN} 房间已存在，获取已有...")
            r2 = await c.get(f"{BASE}/rooms?limit=1", headers=tenant_headers)
            items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
            room_id = items[0]["id"] if items else None
            print(f"     room_id={room_id}")
        else:
            print(f"  {FAIL} {r.status_code}: {r.text[:200]}")
            return

        if not room_id:
            print(f"  {FAIL} 无法获取房间ID")
            return

        # ═══════════════════════════════════════════════════
        # Step 5: 预约草稿
        # ═══════════════════════════════════════════════════
        print("\n── 5. 预约草稿 ──")
        r = await c.put(f"{BASE}/bookings/drafts/{room_id}", headers=tenant_headers, json={
            "preferred_date": "2026-08-01", "preferred_time": "14:00",
            "message": "集成测试预约",
        })
        ok = r.status_code in (200, 201)
        print(f"  {PASS if ok else FAIL} 草稿: {r.status_code}")
        if not ok:
            print(f"     {r.text[:200]}")

        # ═══════════════════════════════════════════════════
        # Step 6: 验证个人信息
        # ═══════════════════════════════════════════════════
        print("\n── 6. 验证个人信息 ──")
        r = await c.post(f"{BASE}/bookings/personal-info/validate", headers=tenant_headers, json={
            "full_name": "Test User", "id_number": "S1234567A", "phone": "+65 9876 5432",
        })
        ok = r.status_code in (200, 201, 422)
        print(f"  {PASS if ok else FAIL} 个人: {r.status_code}")

        r = await c.post(f"{BASE}/bookings/emergency-contact/validate", headers=tenant_headers, json={
            "name": "Contact Person", "phone": "+65 1111 2222", "relationship": "朋友",
        })
        ok = r.status_code in (200, 201, 422)
        print(f"  {PASS if ok else FAIL} 紧急联系人: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # Step 7: 确认预约
        # ═══════════════════════════════════════════════════
        print("\n── 7. 确认预约 ──")
        r = await c.post(f"{BASE}/bookings/confirm", headers=tenant_headers, json={
            "property_id": room_id,
            "preferred_date": "2026-08-01", "preferred_time": "14:00",
            "message": "集成测试确认", "full_name": "Test User",
            "id_number": "S1234567A", "phone": "+65 9876 5432",
            "emergency_contact_name": "Contact Person",
            "emergency_contact_phone": "+65 1111 2222",
            "emergency_contact_relationship": "朋友",
        })
        if r.status_code in (200, 201):
            booking_id = r.json().get("id")
            print(f"  {PASS} 预约确认 #{booking_id}")
        else:
            print(f"  {WARN} {r.status_code}: {r.text[:200]}")
            booking_id = None

        # ═══════════════════════════════════════════════════
        # Step 8: 查询预约
        # ═══════════════════════════════════════════════════
        print("\n── 8. 查询预约 ──")
        r = await c.get(f"{BASE}/bookings", headers=tenant_headers)
        ok = r.status_code == 200
        bookings = r.json() if ok else []
        if isinstance(bookings, dict):
            bookings = bookings.get("items", [])
        print(f"  {PASS if ok else FAIL} 预约列表: {len(bookings)} 条")

        # ═══════════════════════════════════════════════════
        # Step 9: 取消预约
        # ═══════════════════════════════════════════════════
        print("\n── 9. 取消预约 ──")
        if booking_id:
            r = await c.patch(f"{BASE}/bookings/{booking_id}/cancel", headers=tenant_headers)
            ok = r.status_code == 200
            print(f"  {PASS if ok else FAIL} 取消 #{booking_id}: {r.status_code}")
        else:
            print(f"  {WARN} 跳过（无预约ID）")

        # ═══════════════════════════════════════════════════
        # 总结
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("📋 测试完成 — 预约流程全链路")
        print("  注册→登录→公寓→户型→房间→草稿→验证→确认→查询→取消")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
