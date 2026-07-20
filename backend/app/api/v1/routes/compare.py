"""对比 Agent API 路由 —— 深度对比的 REST 接口"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.compare import (
    CompareMessageRead,
    CompareMessageRequest,
    CompareMessageResponse,
    CompareSessionCreate,
    CompareSessionResponse,
)
from app.services.comparison_service import ComparisonService
from app.services.comparison_session_service import ComparisonSessionService

logger = logging.getLogger(__name__)

router = APIRouter()


def _msg_to_read(msg) -> CompareMessageRead:
    return CompareMessageRead(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        tool_calls=msg.tool_calls,
        created_at=msg.created_at,
    )


# ── 会话 ──────────────────────────────────────────────────────────

@router.post(
    "/sessions",
    response_model=CompareSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_compare_session(
    body: CompareSessionCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareSessionResponse:
    """创建对比会话并执行首次分析"""
    # 1. 持久化会话
    sess_svc = ComparisonSessionService(session)
    compare_sess = await sess_svc.create_session(
        current_user.id, body.property_ids, body.priority
    )

    # 2. 运行 ReAct 分析
    comp_svc = ComparisonService(session)
    result = await comp_svc.analyze(
        property_ids=body.property_ids,
        user_message="请对比分析这些房源",
        priority=body.priority,
    )

    # 3. 持久化消息
    await sess_svc.add_message(compare_sess.id, "user", "开始对比分析")
    await sess_svc.add_message(
        compare_sess.id, "assistant", result["reply"],
        tool_calls={"tool_trail": result["tool_trail"]},
    )

    # 4. 缓存结果
    await sess_svc.update_result_cache(compare_sess.id, {
        "scores": result["scores"],
        "property_data": result["property_data"],
        "reply": result["reply"],
    })

    # 重新加载以获取关联的 messages
    compare_sess = await sess_svc.get_session(compare_sess.id, current_user.id)

    return CompareSessionResponse(
        id=compare_sess.id,
        user_id=compare_sess.user_id,
        property_ids=compare_sess.property_ids or [],
        priority=compare_sess.priority,
        status=compare_sess.status.value,
        result_cache=compare_sess.result_cache,
        created_at=compare_sess.created_at,
        messages=[_msg_to_read(m) for m in compare_sess.messages],
    )


@router.get("/sessions/{session_id}", response_model=CompareSessionResponse)
async def get_compare_session(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareSessionResponse:
    """获取对比会话（用于回溯历史对比）"""
    sess_svc = ComparisonSessionService(session)
    compare_sess = await sess_svc.get_session(session_id, current_user.id)
    if compare_sess is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对比会话不存在")

    return CompareSessionResponse(
        id=compare_sess.id,
        user_id=compare_sess.user_id,
        property_ids=compare_sess.property_ids or [],
        priority=compare_sess.priority,
        status=compare_sess.status.value,
        result_cache=compare_sess.result_cache,
        created_at=compare_sess.created_at,
        messages=[_msg_to_read(m) for m in compare_sess.messages],
    )


# ── 消息（追问）───────────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages", response_model=CompareMessageResponse)
async def send_compare_message(
    session_id: int,
    body: CompareMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareMessageResponse:
    """在对比会话中发送追问"""
    sess_svc = ComparisonSessionService(session)
    compare_sess = await sess_svc.get_session(session_id, current_user.id)
    if compare_sess is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对比会话不存在")

    # 持久化用户消息
    await sess_svc.add_message(session_id, "user", body.message)

    # 加载对话历史
    history = await sess_svc.get_history(session_id)

    # 运行 ReAct 分析（带历史）
    priority = body.priority or compare_sess.priority
    property_ids = compare_sess.property_ids or []

    comp_svc = ComparisonService(session)
    result = await comp_svc.analyze(
        property_ids=property_ids,
        user_message=body.message,
        priority=priority,
        conversation_history=history,
    )

    # 持久化回复
    await sess_svc.add_message(
        session_id, "assistant", result["reply"],
        tool_calls={"tool_trail": result["tool_trail"]},
    )

    # 更新缓存
    await sess_svc.update_result_cache(session_id, {
        "scores": result["scores"],
        "property_data": result["property_data"],
        "reply": result["reply"],
    })

    return CompareMessageResponse(
        reply=result["reply"],
        scores=result["scores"],
        tool_trail=result["tool_trail"],
        property_data=result["property_data"],
    )
