"""预约看房申请接口测试。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.routes.visit_messages import SubmitVisitApply, submit_visit_apply
from app.models.notification import Notification
from app.models.visit_message import VisitMessage


@pytest.mark.asyncio
async def test_submit_visit_apply_creates_message_and_notification():
    session = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(id=254, bm_id=40, created_by=12)),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
    )
    data = SubmitVisitApply(apartmentId=254, guestPhone="13671721835", guestMessage="周六下午看房")

    result = await submit_visit_apply(data, session)

    assert result["ok"] is True
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(item, VisitMessage) for item in added)
    notification = next(item for item in added if isinstance(item, Notification))
    assert notification.user_id == 40
    assert notification.entity_type == "visit_message"
    assert notification.entity_id is not None
    assert notification.unit_type_id is None
    session.commit.assert_awaited_once()
