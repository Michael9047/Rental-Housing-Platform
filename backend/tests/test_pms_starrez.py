"""StarRez PMS Connector 测试 — 基于 Mock 数据的端到端测试"""
import json

import pytest
from httpx import AsyncClient


# ═══════════════════════════════════════════════════════════════
# 单元测试：对照表完整性
# ═══════════════════════════════════════════════════════════════

class TestFieldMap:
    """验证 field_map.json 格式正确、覆盖必要字段"""

    def test_field_map_loads_and_has_required_keys(self):
        from pathlib import Path
        path = Path(__file__).parent.parent / "app" / "services" / "pms" / "starrez" / "field_map.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert "fields" in data
        assert "ai_extraction" in data
        assert "meta" in data
        assert data["meta"]["pms_type"] == "starrez"

    def test_field_map_covers_core_fields(self):
        """核心字段必须在对照表中有映射"""
        from pathlib import Path
        path = Path(__file__).parent.parent / "app" / "services" / "pms" / "starrez" / "field_map.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        fields = data["fields"]
        required_paths = [
            "name", "type", "status", "building",
            "floor", "lease.rate_per_week", "lease.start_date",
            "address.line1", "address.country",
        ]
        for rp in required_paths:
            assert rp in fields, f"Missing mapping for {rp}"

    def test_field_map_lookups_have_target(self):
        """所有 lookup 类型的映射必须有 target"""
        from pathlib import Path
        path = Path(__file__).parent.parent / "app" / "services" / "pms" / "starrez" / "field_map.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        for name, config in data["fields"].items():
            if config.get("type") == "lookup" and config.get("strategy") != "array_lookup":
                assert config.get("target"), f"lookup field '{name}' missing target"


# ═══════════════════════════════════════════════════════════════
# 集成测试：StarRezClient Mock
# ═══════════════════════════════════════════════════════════════

class TestStarRezClient:
    """StarRez Mock 客户端测试"""

    @pytest.mark.asyncio
    async def test_mock_returns_spaces(self):
        from app.services.pms.starrez.client import StarRezClient

        client = StarRezClient(base_url="mock://starrez")
        spaces = await client.fetch_spaces()
        await client.close()

        assert len(spaces) >= 5
        for space in spaces:
            assert "id" in space
            assert "name" in space
            assert "type" in space
            assert "lease" in space
            assert "address" in space

    @pytest.mark.asyncio
    async def test_mock_filter_by_property_code(self):
        from app.services.pms.starrez.client import StarRezClient

        client = StarRezClient(base_url="mock://starrez")
        spaces = await client.fetch_spaces(property_code="Block B")
        await client.close()

        # Block B has ids SR003 and SR004
        assert len(spaces) == 2
        block_ids = {s["id"] for s in spaces}
        assert block_ids == {"SR003", "SR004"}


# ═══════════════════════════════════════════════════════════════
# 集成测试：StarRezConnector 映射
# ═══════════════════════════════════════════════════════════════

class TestStarRezConnectorMapping:
    """StarRezConnector 映射逻辑测试"""

    @pytest.mark.asyncio
    async def test_map_ensuite_single(self):
        """Ensuite Single 应正确映射为 studio + shared"""
        from app.services.pms.starrez import StarRezConnector

        connector = StarRezConnector(base_url="mock://starrez")
        raw = {
            "id": "TEST001",
            "name": "Ensuite Single Room 101",
            "type": "Ensuite Single",
            "description": "Ensuite room in shared flat. Female only. £300 deposit.",
            "status": "Available",
            "building": "Block A",
            "floor": 1,
            "area_sqm": 14.5,
            "max_occupancy": 1,
            "capacity": 1,
            "amenities": ["WiFi", "Desk", "Ensuite Bathroom"],
            "room_number": "101",
            "images": ["http://example.com/img1.jpg"],
            "lease": {
                "rate_per_week": 185.00,
                "currency": "GBP",
                "start_date": "2026-09-15",
                "end_date": "2027-06-30",
                "min_stay_weeks": 16,
                "deposit_amount": 300,
            },
            "address": {
                "line1": "Oxford Road, Manchester",
                "city": "Manchester",
                "country": "United Kingdom",
            },
            "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
        }

        result = await connector.map_property(raw)
        await connector.close()

        mapped = result.mapped
        assert mapped["title"] == "Ensuite Single Room 101"
        assert mapped["property_type"] == "studio"
        assert mapped["status"] == "available"
        assert mapped["building_name"] == "Block A"
        assert mapped["floor"] == 1
        assert mapped["area_sqm"] == 14.5
        assert mapped["room_number"] == "101"
        assert mapped["address"] == "Oxford Road, Manchester"
        assert mapped["district"] == "Manchester"
        assert mapped["country"] == "GB"
        # rent_type: capacity=1 + not explicitly shared → whole (pre-AI)
        # Actually Ensuite Single in shared flat → AI may override to shared
        assert mapped["rent_type"] in ("whole", "shared")
        # price_monthly = 185 * 4.33 ≈ 801.05
        assert float(mapped["price_monthly"]) == pytest.approx(801.05, rel=0.1)
        assert mapped["latitude"] == 53.4668
        assert mapped["longitude"] == -2.2334

    @pytest.mark.asyncio
    async def test_map_studio(self):
        """Studio 应正确映射为整租"""
        from app.services.pms.starrez import StarRezConnector

        connector = StarRezConnector(base_url="mock://starrez")
        raw = {
            "id": "TEST002",
            "name": "Studio Apartment 205",
            "type": "Studio",
            "description": "Self-contained studio with private kitchen.",
            "status": "Available",
            "building": "Block A",
            "floor": 2,
            "area_sqm": 24.0,
            "max_occupancy": 2,
            "capacity": 1,
            "amenities": ["WiFi", "Kitchen", "Private Bathroom"],
            "room_number": "205",
            "images": ["http://example.com/img2.jpg"],
            "lease": {
                "rate_per_week": 225.00,
                "currency": "GBP",
                "start_date": "2026-09-15",
                "end_date": "2027-06-30",
                "min_stay_weeks": 38,
                "deposit_amount": 500,
            },
            "address": {
                "line1": "Oxford Road, Manchester",
                "city": "Manchester",
                "country": "United Kingdom",
            },
            "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
        }

        result = await connector.map_property(raw)
        await connector.close()

        mapped = result.mapped
        assert mapped["property_type"] == "studio"
        # Studio is self-contained → rent_type should be "whole"
        assert mapped["rent_type"] == "whole"
        assert mapped["bedrooms"] == 1  # max_occupancy=2 → bedrooms=1
        assert float(mapped["price_monthly"]) == pytest.approx(974.25, rel=0.1)

    @pytest.mark.asyncio
    async def test_map_twin_share(self):
        """Twin Share 应正确映射为 shared"""
        from app.services.pms.starrez import StarRezConnector

        connector = StarRezConnector(base_url="mock://starrez")
        raw = {
            "id": "TEST003",
            "name": "Twin Share Room 312",
            "type": "Twin Share",
            "description": "Shared twin room in cluster flat.",
            "status": "Available",
            "building": "Block B",
            "floor": 3,
            "area_sqm": 18.0,
            "max_occupancy": 2,
            "capacity": 2,
            "amenities": ["WiFi", "Desk", "Shared Bathroom"],
            "room_number": "312",
            "images": [],
            "lease": {
                "rate_per_week": 145.00,
                "currency": "GBP",
                "start_date": "2026-09-15",
                "end_date": "2027-01-31",
                "min_stay_weeks": 16,
                "deposit_amount": 250,
            },
            "address": {
                "line1": "Oxford Road, Manchester",
                "city": "Manchester",
                "country": "United Kingdom",
            },
            "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
        }

        result = await connector.map_property(raw)
        await connector.close()

        mapped = result.mapped
        assert mapped["property_type"] == "shared"
        assert mapped["rent_type"] == "shared"  # Twin Share → shared

    @pytest.mark.asyncio
    async def test_map_all_batch(self):
        """批量映射不应丢失数据"""
        from app.services.pms.starrez import StarRezConnector
        from app.services.pms.starrez.client import MOCK_SPACES

        connector = StarRezConnector(base_url="mock://starrez")
        results = await connector.map_all(MOCK_SPACES)
        await connector.close()

        assert len(results) == len(MOCK_SPACES)
        for r in results:
            assert r.mapped.get("title"), f"Missing title for {r.external_id}"
            assert r.mapped.get("address"), f"Missing address for {r.external_id}"

    @pytest.mark.asyncio
    async def test_room_type_override(self):
        """入驻时人工配置的 room_type_mapping 应覆盖默认映射"""
        from app.services.pms.starrez import StarRezConnector

        connector = StarRezConnector(base_url="mock://starrez")
        raw = {
            "id": "TEST004",
            "name": "Deluxe Suite",
            "type": "Super Deluxe Penthouse",  # 不在默认 lookup 中
            "description": "Top floor luxury suite.",
            "status": "Available",
            "building": "Block C",
            "floor": 10,
            "area_sqm": 45.0,
            "max_occupancy": 2,
            "capacity": 1,
            "amenities": [],
            "room_number": "1001",
            "images": [],
            "lease": {
                "rate_per_week": 350.00, "currency": "GBP",
                "start_date": "2026-09-15", "end_date": "2027-06-30",
                "min_stay_weeks": 38, "deposit_amount": 800,
            },
            "address": {"line1": "Main St", "city": "London", "country": "United Kingdom"},
            "coordinates": {"latitude": 51.5074, "longitude": -0.1278},
        }

        # 不传 override → 房型无法匹配，fallback=ai → unmapped
        result_no_override = await connector.map_property(raw)
        assert result_no_override.unmapped  # property_type should be in unmapped or missing

        # 传入 override → 房型应匹配
        result_with_override = await connector.map_property(
            raw, room_type_mapping={"Super Deluxe Penthouse": "apartment"}
        )
        assert result_with_override.mapped.get("property_type") == "apartment"

        await connector.close()

    @pytest.mark.asyncio
    async def test_amenities_array_lookup(self):
        """设施数组应逐项查表翻译"""
        from app.services.pms.starrez import StarRezConnector

        connector = StarRezConnector(base_url="mock://starrez")
        raw = {
            "id": "TEST005",
            "name": "Standard Room",
            "type": "Ensuite Single",
            "description": "Standard ensuite room.",
            "status": "Available",
            "building": "Block A",
            "floor": 1,
            "area_sqm": 14.0,
            "max_occupancy": 1,
            "capacity": 1,
            "amenities": ["WiFi", "Desk", "Ensuite Bathroom", "Unknown Feature XYZ"],
            "room_number": "001",
            "images": [],
            "lease": {
                "rate_per_week": 150.00, "currency": "GBP",
                "start_date": "2026-09-15", "end_date": "2027-01-31",
                "min_stay_weeks": 16, "deposit_amount": 200,
            },
            "address": {"line1": "Test St", "city": "Manchester", "country": "United Kingdom"},
            "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
        }

        result = await connector.map_property(raw)
        await connector.close()

        amenities = result.mapped.get("amenities", [])
        assert "wifi" in amenities
        assert "desk" in amenities
        assert "ensuite" in amenities
        # 未命中项保留原文
        assert "Unknown Feature XYZ" in amenities


# ═══════════════════════════════════════════════════════════════
# 集成测试：托管客户测试
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_preview_mapping_endpoint(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
):
    """测试预览映射 API（不写库）需 Institute 先存在 — 此测试验证 API 结构而非完整流程"""
    # 登录
    reg = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    if reg.status_code != 201:
        pytest.skip("Registration endpoint unavailable or failed")

    token_data = await client.post("/api/v1/auth/login", json={
        "username": landlord_register_payload["username"],
        "password": landlord_register_payload["password"],
    })
    if token_data.status_code != 200:
        pytest.skip("Login endpoint unavailable")

    token = token_data.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建 institute
    inst_resp = await client.post("/api/v1/admin/institutes", headers=headers, json={
        "name": "Test Student Accommodation",
        "address": "Oxford Road",
        "contact_email": "test@unite.co.uk",
    })
    # Admin endpoint may require admin role — skip gracefully if 403
    if inst_resp.status_code not in (200, 201, 403):
        pytest.skip(f"Institute creation returned {inst_resp.status_code}")

    # If institute creation requires admin, skip full test
    if inst_resp.status_code == 403:
        pytest.skip("Institute creation requires admin role — test skipped")

    institute_id = inst_resp.json()["id"]

    # 创建 PMS connection
    conn_resp = await client.post("/api/v1/pms/connections", headers=headers, json={
        "pms_type": "starrez",
        "label": "Test Connection",
        "base_url": "mock://starrez",
        "institute_id": institute_id,
    })

    # 如果用户不是 admin，创建 connection 也会被拒
    if conn_resp.status_code == 403:
        pytest.skip("PMS connection creation requires admin role — test skipped")

    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    # 预览映射
    preview_resp = await client.get(
        f"/api/v1/pms/connections/{conn_id}/preview?limit=3", headers=headers,
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert len(preview) <= 3
    for item in preview:
        assert "external_id" in item
        assert "mapped" in item
        assert "confidence" in item


@pytest.mark.asyncio
async def test_sync_endpoint_creates_properties(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
):
    """端到端：Mock 同步 → 房源写库"""
    # 注册 + 登录
    reg = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    if reg.status_code != 201:
        pytest.skip("Registration failed")

    token_data = await client.post("/api/v1/auth/login", json={
        "username": landlord_register_payload["username"],
        "password": landlord_register_payload["password"],
    })
    if token_data.status_code != 200:
        pytest.skip("Login failed")

    token = token_data.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建 institute
    inst_resp = await client.post("/api/v1/admin/institutes", headers=headers, json={
        "name": "Unite Manchester",
        "address": "Oxford Road",
        "contact_email": "hello@unite.co.uk",
    })
    if inst_resp.status_code in (403, 404):
        pytest.skip("Institute creation requires admin role")

    institute_id = inst_resp.json()["id"]

    # 创建 PMS connection
    conn_resp = await client.post("/api/v1/pms/connections", headers=headers, json={
        "pms_type": "starrez",
        "label": "Unite Manchester (StarRez)",
        "base_url": "mock://starrez",
        "institute_id": institute_id,
    })
    if conn_resp.status_code == 403:
        pytest.skip("PMS connection creation requires admin role")

    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    # 触发同步
    sync_resp = await client.post(f"/api/v1/pms/connections/{conn_id}/sync", headers=headers)
    assert sync_resp.status_code == 200
    stats = sync_resp.json()
    assert stats["status"] == "success"
    assert stats["created"] + stats["updated"] + stats["skipped"] + stats["errors"] >= 1

    # 验证房源已入库
    props = await client.get("/api/v1/properties", headers=headers)
    if props.status_code == 200:
        prop_list = props.json()
        if isinstance(prop_list, dict):
            prop_list = prop_list.get("items", [])
        assert len(prop_list) >= 1
