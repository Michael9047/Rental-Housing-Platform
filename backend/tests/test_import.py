import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_upload_requires_admin(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    resp = await client.post("/api/v1/import/upload")
    assert resp.status_code == 401

    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login.json()["access_token"]

    csv_content = b"title,address,district,price_monthly\nTest,Addr,SIP,3000"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_tasks_requires_admin(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/v1/import/tasks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_csv_as_admin(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "import_admin",
        "email": "import_admin@example.com",
        "password": "import-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "import_admin", "password": "import-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly,bedrooms,property_type\n"
        "Test Apartment 1,123 Test Rd,SIP,3500,2,apartment\n"
        "Test Apartment 2,456 Demo St,Wuzhong,4200,3,apartment\n"
    ).encode("utf-8")

    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["total_records"] == 2
    assert data["success_records"] == 2
    assert data["failed_records"] == 0


@pytest.mark.asyncio
async def test_import_csv_missing_required_fields(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "field_admin",
        "email": "field_admin@example.com",
        "password": "field-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "field_admin", "password": "field-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,price_monthly\n"
        "Missing District,No District Here,2500\n"
    ).encode("utf-8")

    files = {"file": ("missing.csv", io.BytesIO(csv_content), "text/csv")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["failed_records"] > 0


@pytest.mark.asyncio
async def test_import_csv_invalid_price(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "price_admin",
        "email": "price_admin@example.com",
        "password": "price-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "price_admin", "password": "price-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly\n"
        "Bad Price,Addr,District,not_a_number\n"
    ).encode("utf-8")

    files = {"file": ("bad_price.csv", io.BytesIO(csv_content), "text/csv")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["failed_records"] == 1


@pytest.mark.asyncio
async def test_import_invalid_file_type(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "type_admin",
        "email": "type_admin@example.com",
        "password": "type-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "type_admin", "password": "type-pass"},
    )
    token = login.json()["access_token"]

    files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_tasks_list(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "list_admin",
        "email": "list_admin@example.com",
        "password": "list-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "list_admin", "password": "list-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly\n"
        "List Test,Addr,SIP,3000\n"
    ).encode("utf-8")

    files = {"file": ("list.csv", io.BytesIO(csv_content), "text/csv")}
    await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/api/v1/import/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    tasks = resp.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    assert "source_name" in tasks[0]
    assert "status" in tasks[0]


@pytest.mark.asyncio
async def test_import_task_detail(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "detail_admin",
        "email": "detail_admin@example.com",
        "password": "detail-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "detail_admin", "password": "detail-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly\n"
        "Detail Test,Addr,SIP,3000\n"
    ).encode("utf-8")

    files = {"file": ("detail.csv", io.BytesIO(csv_content), "text/csv")}
    upload_resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = upload_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/import/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == task_id
    assert "error_log" in detail


@pytest.mark.asyncio
async def test_import_task_not_found(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "notfound_admin",
        "email": "notfound_admin@example.com",
        "password": "notfound-pass",
        "role": "admin",
    }
    reg = await client.post("/api/v1/auth/register", json=admin_payload)
    assert reg.status_code in (200, 201), f"Register failed: {reg.status_code} {reg.text}"
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "notfound_admin", "password": "notfound-pass"},
    )
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.text}"
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/import/tasks/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_duplicate_detection(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "dup_admin",
        "email": "dup_admin@example.com",
        "password": "dup-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "dup_admin", "password": "dup-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly\n"
        "Same Title,Same Addr,SIP,3000\n"
        "Same Title,Same Addr,SIP,3500\n"
    ).encode("utf-8")

    files = {"file": ("dup.csv", io.BytesIO(csv_content), "text/csv")}
    resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success_records"] == 1
    assert data["failed_records"] == 1


@pytest.mark.asyncio
async def test_import_tasks_filter_by_status(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "filt_admin",
        "email": "filt_admin@example.com",
        "password": "filt-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "filt_admin", "password": "filt-pass"},
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/import/tasks",
        params={"status": "completed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    tasks = resp.json()
    assert all(t["status"] == "completed" for t in tasks)


@pytest.mark.asyncio
async def test_import_retry(
    client: AsyncClient,
) -> None:
    admin_payload = {
        "username": "retry_admin",
        "email": "retry_admin@example.com",
        "password": "retry-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "retry_admin", "password": "retry-pass"},
    )
    token = login.json()["access_token"]

    csv_content = (
        "title,address,district,price_monthly\n"
        "Retry Title,Retry Addr,District,not_a_price\n"
    ).encode("utf-8")

    files = {"file": ("retry.csv", io.BytesIO(csv_content), "text/csv")}
    upload_resp = await client.post(
        "/api/v1/import/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = upload_resp.json()["id"]

    retry_resp = await client.post(
        f"/api/v1/import/tasks/{task_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry_resp.status_code == 200
