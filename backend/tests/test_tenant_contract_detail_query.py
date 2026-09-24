"""租客合同详情查询的异步关联加载测试。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.tenant_contract_service import TenantContractService


@pytest.mark.asyncio
async def test_contract_detail_eager_loads_institute() -> None:
    """详情查询必须预加载公寓，避免异步访问关联时触发 MissingGreenlet。"""
    session = AsyncMock()
    session.scalar.side_effect = [SimpleNamespace(booking_id=5), None]
    session.get.return_value = SimpleNamespace(unit_type_id=8)

    with pytest.raises(LookupError):
        await TenantContractService(session).detail_for_tenant("contract-1", 7)

    room_statement = session.scalar.await_args_list[1].args[0]
    assert room_statement._with_options
