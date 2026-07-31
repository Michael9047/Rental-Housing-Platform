"""Unit tests for search-cache versioning and sync-first embedding fallback."""
import pytest

from app.services.property_service import PropertyService, _cache_key


def test_cache_key_is_version_scoped() -> None:
    """Cache keys embed the namespace version so a version bump invalidates all."""
    params = {"district": "SIP", "limit": 20}
    k_v0 = _cache_key("filter", "0", **params)
    k_v1 = _cache_key("filter", "1", **params)

    assert k_v0 == "search:filter:v0:" + '{"district": "SIP", "limit": 20}'
    assert k_v0 != k_v1  # bumping the version yields a fresh, unreachable namespace


@pytest.mark.asyncio
async def test_rewrite_imports_cleanly() -> None:
    """PropertyService 重写后导入正常，所有必要方法存在。"""
    svc = PropertyService(session=None)  # type: ignore[arg-type]

    # 核心方法必须存在
    assert hasattr(svc, "search")
    assert hasattr(svc, "search_unit_types")
    assert hasattr(svc, "list")
    assert hasattr(svc, "get")
    assert hasattr(svc, "create")
    assert hasattr(svc, "update")
    assert hasattr(svc, "delete")
    assert hasattr(svc, "restore")
    assert hasattr(svc, "hard_delete")

    # 批量操作
    assert hasattr(svc, "batch_delete")
    assert hasattr(svc, "batch_restore")
    assert hasattr(svc, "batch_hard_delete")
    assert hasattr(svc, "batch_update_status")

    # 已移除的方法不得存在
    assert not hasattr(svc, "_build_filters")
    assert not hasattr(svc, "_ensure_embedding")
    assert not hasattr(svc, "revert_audit")
    assert not hasattr(svc, "_ROOM_TYPE_MAP")
