"""对比 Agent API 路由 —— 深度对比的 REST 接口"""
import asyncio
import json
import logging
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


def _session_to_response(compare_sess) -> CompareSessionResponse:
    """统一序列化独立对比会话，供 REST 与 SSE 最终结果复用。"""
    return CompareSessionResponse(
        id=compare_sess.id,
        user_id=compare_sess.user_id,
        property_ids=compare_sess.unit_type_ids or [],
        priority=compare_sess.priority,
        status=compare_sess.status.value,
        result_cache=compare_sess.result_cache,
        created_at=compare_sess.created_at,
        messages=[_msg_to_read(message) for message in compare_sess.messages],
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
    # 1. 先验证并计算，避免无效 UnitType ID 留下空会话。
    sess_svc = ComparisonSessionService(session)
    comp_svc = ComparisonService(session)
    try:
        result = await comp_svc.analyze(
            property_ids=body.property_ids,
            user_message="请对比分析这些户型",
            priority=body.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    compare_sess = await sess_svc.create_session(
        current_user.id, body.property_ids, body.priority
    )

    # 2. 持久化消息
    await sess_svc.add_message(compare_sess.id, "user", "开始对比分析")
    await sess_svc.add_message(
        compare_sess.id, "assistant", result["reply"],
        tool_calls={"tool_trail": result["tool_trail"]},
    )

    # 3. 缓存结果
    await sess_svc.update_result_cache(compare_sess.id, {
        "scores": result["scores"],
        "property_data": result["property_data"],
        "reply": result["reply"],
    })

    # 重新加载以获取关联的 messages
    compare_sess = await sess_svc.get_session(compare_sess.id, current_user.id)

    return _session_to_response(compare_sess)


@router.post("/sessions/stream")
async def create_compare_session_stream(
    body: CompareSessionCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """创建对比会话，并以 SSE 直通模型生成的简短总结 token。"""
    stream_bind = session.bind
    if stream_bind is None:
        raise HTTPException(status_code=503, detail="数据库连接不可用")
    stream_session_factory = async_sessionmaker(
        bind=stream_bind,
        expire_on_commit=False,
    )
    property_ids = list(body.property_ids)
    priority = body.priority
    user_id = current_user.id

    async def event_stream():
        yield ": connected\n\n"
        yield "data: " + json.dumps({
            "meta": {
                "event": "status",
                "status": "comparing",
                "message": "正在整理对比数据",
            }
        }, ensure_ascii=False) + "\n\n"

        async with stream_session_factory() as stream_session:
            event_queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue(maxsize=32)
            stream_done = object()

            async def emit_token(token: str) -> None:
                await event_queue.put(("token", token))

            async def emit_status(status_name: str, message: str) -> None:
                await event_queue.put(("meta", {
                    "event": "status",
                    "status": status_name,
                    "message": message,
                }))

            async def run_analysis() -> dict:
                try:
                    return await ComparisonService(stream_session).analyze(
                        property_ids=property_ids,
                        user_message="请对比分析这些户型",
                        priority=priority,
                        token_sink=emit_token,
                        status_sink=emit_status,
                    )
                finally:
                    await event_queue.put(("done", stream_done))

            worker = asyncio.create_task(run_analysis())
            try:
                while True:
                    event_type, payload = await event_queue.get()
                    if event_type == "done" and payload is stream_done:
                        break
                    if event_type == "token":
                        yield "data: " + json.dumps(
                            {"token": str(payload)}, ensure_ascii=False
                        ) + "\n\n"
                    elif event_type == "meta":
                        yield "data: " + json.dumps(
                            {"meta": payload}, ensure_ascii=False
                        ) + "\n\n"
                result = await worker

                # 无模型或安全降级没有产生增量 token 时，只发送一个完整正文帧。
                if not result.get("_reply_streamed") and result.get("reply"):
                    yield "data: " + json.dumps(
                        {"token": str(result["reply"])}, ensure_ascii=False
                    ) + "\n\n"

                sess_svc = ComparisonSessionService(stream_session)
                compare_sess = await sess_svc.create_session(
                    user_id, property_ids, priority
                )
                await sess_svc.add_message(compare_sess.id, "user", "开始对比分析")
                await sess_svc.add_message(
                    compare_sess.id,
                    "assistant",
                    result["reply"],
                    tool_calls={"tool_trail": result["tool_trail"]},
                )
                await sess_svc.update_result_cache(compare_sess.id, {
                    "scores": result["scores"],
                    "property_data": result["property_data"],
                    "reply": result["reply"],
                })
                compare_sess = await sess_svc.get_session(compare_sess.id, user_id)
                response = _session_to_response(compare_sess).model_dump(mode="json")
                yield "data: " + json.dumps({
                    "meta": {"event": "result", "session": response}
                }, ensure_ascii=False) + "\n\n"
            except Exception as exc:
                logger.exception("流式创建对比会话失败")
                yield "data: " + json.dumps(
                    {"error": str(exc)}, ensure_ascii=False
                ) + "\n\n"
            finally:
                if not worker.done():
                    worker.cancel()
                    with suppress(asyncio.CancelledError):
                        await worker
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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

    return _session_to_response(compare_sess)


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
    property_ids = compare_sess.unit_type_ids or []

    comp_svc = ComparisonService(session)
    try:
        result = await comp_svc.analyze(
            property_ids=property_ids,
            user_message=body.message,
            priority=priority,
            conversation_history=history,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    effective_priority = result.get("priority", priority)
    if effective_priority != compare_sess.priority:
        await sess_svc.update_priority(session_id, effective_priority)

    return CompareMessageResponse(
        reply=result["reply"],
        scores=result["scores"],
        tool_trail=result["tool_trail"],
        property_data=result["property_data"],
    )
