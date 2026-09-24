"""批量导入维护开关的发布回归测试。"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/import/upload"),
        ("post", "/api/v1/import/preview"),
        ("post", "/api/v1/import/confirm/1"),
        ("get", "/api/v1/import/tasks"),
        ("get", "/api/v1/import/tasks/1"),
        ("post", "/api/v1/import/tasks/1/retry"),
        ("get", "/api/v1/import/template"),
        ("get", "/api/v1/import/tasks/1/errors/download"),
    ],
)
async def test_all_bulk_import_endpoints_are_disabled(
    client: AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await client.request(method, path)

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "批量导入功能正在维护，暂不可用"
