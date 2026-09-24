"""Agent 流式轮次协作停止状态测试。"""
from app.services.agent_turn_control import (
    register_agent_turn,
    request_agent_turn_stop,
    unregister_agent_turn,
)


def test_stop_before_structured_work_rolls_back() -> None:
    control = register_agent_turn(1, 2, "turn-before-work")
    try:
        assert request_agent_turn_stop(1, 2, "turn-before-work") == "rolled_back"
        assert control.stop_requested is True
    finally:
        unregister_agent_turn(1, 2, "turn-before-work")


def test_stop_after_structured_work_waits_for_safe_point() -> None:
    control = register_agent_turn(1, 2, "turn-after-work")
    try:
        control.start_structured_work()
        assert request_agent_turn_stop(1, 2, "turn-after-work") == "pending"
        assert control.stop_requested is True
    finally:
        unregister_agent_turn(1, 2, "turn-after-work")
