"""管理流式 Agent 单轮任务的协作式停止状态。"""
from dataclasses import dataclass


@dataclass
class AgentTurnControl:
    """记录停止请求以及结构化工作是否已经开始。"""

    stop_requested: bool = False
    structured_work_started: bool = False

    def request_stop(self) -> str:
        self.stop_requested = True
        return "pending" if self.structured_work_started else "rolled_back"

    def start_structured_work(self) -> None:
        self.structured_work_started = True


_ACTIVE_TURNS: dict[tuple[int, int, str], AgentTurnControl] = {}


def register_agent_turn(user_id: int, session_id: int, request_id: str) -> AgentTurnControl:
    """注册当前进程内正在执行的流式轮次。"""
    control = AgentTurnControl()
    _ACTIVE_TURNS[(user_id, session_id, request_id)] = control
    return control


def request_agent_turn_stop(user_id: int, session_id: int, request_id: str) -> str:
    """请求停止轮次；不存在通常表示轮次已经完成。"""
    control = _ACTIVE_TURNS.get((user_id, session_id, request_id))
    return control.request_stop() if control else "completed"


def unregister_agent_turn(user_id: int, session_id: int, request_id: str) -> None:
    """清理已完成或已断开的轮次。"""
    _ACTIVE_TURNS.pop((user_id, session_id, request_id), None)
