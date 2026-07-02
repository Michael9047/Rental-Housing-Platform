import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_booking(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert create_resp.status_code == 201
    property_id = create_resp.json()["id"]

    tenant_payload = {
        "username": "booking_tenant",
        "email": "tenant@example.com",
        "password": "tenant-pass",
        "role": "tenant",
    }
    tenant_register_resp = await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_id = tenant_register_resp.json()["id"]
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "booking_tenant", "password": "tenant-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    booking_resp = await client.post(
        "/api/v1/bookings",
        json={
            "property_id": property_id,
            "message": "I would like to view this property",
            "scheduled_date": "2026-07-01",
        },
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert booking_resp.status_code == 201
    created = booking_resp.json()
    assert created["tenant_id"] == tenant_id
    assert created["property_id"] == property_id
    assert created["status"] == "pending"

    list_resp = await client.get(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_duplicate_pending_booking_rejected(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    property_id = create_resp.json()["id"]

    tenant_payload = {
        "username": "dup_tenant",
        "email": "dup_tenant@example.com",
        "password": "dup-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "dup_tenant", "password": "dup-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    booking_data = {"property_id": property_id, "scheduled_date": "2026-07-01"}
    first = await client.post(
        "/api/v1/bookings", json=booking_data,
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bookings", json=booking_data,
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_landlord_approve_and_reject_booking(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    property_id = create_resp.json()["id"]

    tenant_payload = {
        "username": "approve_tenant",
        "email": "approve_tenant@example.com",
        "password": "approve-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "approve_tenant", "password": "approve-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    booking_resp = await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "scheduled_date": "2026-07-01"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    booking_id = booking_resp.json()["id"]

    approve_resp = await client.patch(
        f"/api/v1/bookings/{booking_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    second_tenant = {
        "username": "reject_tenant",
        "email": "reject_tenant@example.com",
        "password": "reject-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=second_tenant)
    reject_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "reject_tenant", "password": "reject-pass"},
    )
    reject_token = reject_login.json()["access_token"]

    booking2 = await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "scheduled_date": "2026-07-02"},
        headers={"Authorization": f"Bearer {reject_token}"},
    )
    booking2_id = booking2.json()["id"]

    reject_resp = await client.patch(
        f"/api/v1/bookings/{booking2_id}/status",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_tenant_cancel_booking(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    property_id = create_resp.json()["id"]

    tenant_payload = {
        "username": "cancel_tenant",
        "email": "cancel_tenant@example.com",
        "password": "cancel-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "cancel_tenant", "password": "cancel-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    booking_resp = await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "scheduled_date": "2026-07-01"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    booking_id = booking_resp.json()["id"]

    cancel_resp = await client.patch(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_unauthenticated_cannot_book(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/bookings",
        json={"property_id": 1, "scheduled_date": "2026-07-01"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_contract_info_must_be_confirmed_before_contract_generation(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:
    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    property_id = create_resp.json()["id"]

    tenant_payload = {
        "username": "contract_info_tenant",
        "email": "contract_info_tenant@example.com",
        "password": "tenant-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "contract_info_tenant", "password": "tenant-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    booking_resp = await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "scheduled_date": "2026-07-01"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    booking_id = booking_resp.json()["id"]

    early_contract = await client.post(
        f"/api/v1/contracts/{booking_id}/generate",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert early_contract.status_code == 409

    info_resp = await client.patch(
        f"/api/v1/bookings/{booking_id}/contract-info",
        json={
            "contract_real_name": "张三",
            "contract_id_card_no": "320102199901011234",
            "contract_phone": "13800138000",
            "lease_start_date": "2026-09-01",
            "lease_end_date": "2027-08-31",
            "contract_extra_terms": "不得转租。",
        },
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert info_resp.status_code == 200
    assert info_resp.json()["contract_info_status"] == "pending_landlord"

    unconfirmed_contract = await client.post(
        f"/api/v1/contracts/{booking_id}/generate",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert unconfirmed_contract.status_code == 409

    confirm_resp = await client.patch(
        f"/api/v1/bookings/{booking_id}/contract-info/confirm",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["contract_info_status"] == "confirmed"

    contract_resp = await client.post(
        f"/api/v1/contracts/{booking_id}/generate",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert contract_resp.status_code == 201
    content = contract_resp.json()["content"]
    assert "乙方（承租方）：张三" in content
    assert "身份证号：320102199901011234" in content
    assert "租赁期限自2026年09月01日起至2027年08月31日止" in content
    assert "不得转租。" in content
