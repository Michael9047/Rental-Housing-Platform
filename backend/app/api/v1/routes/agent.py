"""租房推荐 Agent —— 会话历史、长期偏好、推荐、候选清单与户型对比接口。"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session
from app.models.chat import AGENT_SESSION_TITLE, ChatMessage, ChatMessageRole, ChatSession
from app.models.unit_type import UnitType
from app.models.user import User
from app.schemas.agent import (
    AgentHistoryMessage,
    AgentHistoryResponse,
    AgentLink,
    AgentMemoryResponse,
    AgentMemoryUpdateRequest,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRecommendation,
    AgentSessionListResponse,
    AgentSessionResponse,
    AgentSessionSummary,
    AgentStateSummary,
    AgentTaskBoundary,
    CartItemAddRequest,
    CartItemRead,
    CartRead,
    CompareItem,
    CompareRequest,
    CompareResponse,
    FaqChip,
    GuidedOption,
    ThinkingStep,
)
from app.schemas.property import PropertySearchResult
from app.schemas.property_image import PropertyImageRead
from app.services.agent_faq import list_faq_chips
from app.services.agent_memory import AgentMemoryService
from app.services.agentic.agents.cart_agent import CartService
from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.chat_service import ChatService


logger = logging.getLogger(__name__)
router = APIRouter()

def _enum_value(value, default: str | None = None):
    return value.value if hasattr(value, "value") else (value if value is not None else default)


def _unit_type_images(unit_type: UnitType) -> list[PropertyImageRead]:
    """把 UnitType.image_urls 适配为旧推荐卡使用的 images 数组。"""
    created_at = unit_type.created_at or datetime.now(timezone.utc)
    return [
        PropertyImageRead(
            id=index,
            property_id=unit_type.id,
            filename=url,
            original_name="",
            mime_type="image/jpeg",
            file_size=0,
            sort_order=index,
            is_primary=index == 0,
            created_at=created_at,
        )
        for index, url in enumerate(unit_type.image_urls or [])
        if url
    ]


def _to_search_result(unit_type: UnitType) -> PropertySearchResult:
    """将 main 的 UnitType + Institute 映射为现有前端推荐卡契约。"""
    institute = unit_type.institute
    property_type = _enum_value(unit_type.property_type)
    images = _unit_type_images(unit_type)
    amenities = list(dict.fromkeys([
        *[str(value) for value in (unit_type.amenities or []) if value],
        *[str(value) for value in ((institute.amenities if institute else None) or []) if value],
    ]))
    return PropertySearchResult(
        id=unit_type.id,
        unit_type_id=unit_type.id,
        name=unit_type.name,
        base_rent=float(unit_type.base_rent),
        institute_address=institute.address if institute else None,
        has_vacancy=unit_type.has_vacancy,
        available_count=unit_type.available_count,
        total_count=unit_type.total_count,
        landlord_id=0,
        title=" · ".join(
            value for value in (
                (institute.name_cn or institute.name) if institute else None,
                unit_type.name,
            )
            if value
        ),
        description=unit_type.description,
        address=institute.address if institute else None,
        country=institute.country if institute else None,
        city=institute.city if institute else None,
        district=institute.district if institute else None,
        price_monthly=unit_type.base_rent,
        area_sqm=unit_type.area_sqm,
        bedrooms=unit_type.bedrooms,
        bathrooms=unit_type.bathrooms,
        property_type=property_type,
        status=_enum_value(unit_type.status, "available"),
        currency=unit_type.currency,
        latitude=float(institute.latitude) if institute and institute.latitude is not None else None,
        longitude=float(institute.longitude) if institute and institute.longitude is not None else None,
        created_at=unit_type.created_at,
        updated_at=unit_type.updated_at,
        images=images,
        image_urls=list(unit_type.image_urls or []),
        institute_id=unit_type.institute_id,
        institute_name=(institute.name_cn or institute.name) if institute else None,
        amenities=amenities or None,
        available_from=unit_type.available_from.isoformat() if unit_type.available_from else None,
        min_stay_months=unit_type.min_stay_months,
        special_offer=unit_type.special_offer,
    )


def _serialize_meta(meta: dict) -> dict:
    """把 SSE/历史元数据中的 UnitType ORM 对象转为 JSON。"""
    # 下划线开头的字段只用于服务端编排，不属于前端响应契约。
    output = {key: value for key, value in meta.items() if not key.startswith("_")}
    for key in ("recommendations", "top_picks"):
        recommendations = output.get(key) or []
        output[key] = [
            {
                **item,
                "property": _to_search_result(item["property"]).model_dump(mode="json"),
            }
            if item.get("property") is not None else item
            for item in recommendations
        ]
    return output


async def _update_history_metadata(
    session: AsyncSession,
    session_id: int,
    assistant_message_id: int,
    serialized_meta: dict,
) -> None:
    """精确补全本轮 assistant 元数据，避免并发消息互相覆盖。"""
    message = await session.scalar(
        select(ChatMessage)
        .where(
            ChatMessage.id == assistant_message_id,
            ChatMessage.session_id == session_id,
            ChatMessage.role == ChatMessageRole.assistant,
        )
    )
    if message is None:
        return
    metadata = dict(message.metadata_ or {})
    for key in (
        "intent", "recommendations", "recommendation_total", "top_picks", "quick_replies", "links",
        "thinking_steps", "guided_options", "state_summary", "filter_patch", "ai_available",
        "cleared_filters", "query_rewrite", "sources",
        "task_boundary", "turn_summary",
    ):
        if key in serialized_meta:
            metadata[key] = serialized_meta[key]
    message.metadata_ = metadata
    await session.commit()


async def _owned_agent_session(
    session: AsyncSession,
    session_id: int,
    user_id: int,
) -> ChatSession | None:
    """按用户和固定 Agent 标题隔离普通客服聊天。"""
    return await session.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.title == AGENT_SESSION_TITLE,
        )
    )


# ── 会话历史 ──────────────────────────────────────────────────────

@router.get("/sessions", response_model=AgentSessionListResponse)
async def list_agent_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentSessionListResponse:
    """列出当前用户的 Agent 会话，不混入 /chat 客服会话。"""
    where = (
        ChatSession.user_id == current_user.id,
        ChatSession.title == AGENT_SESSION_TITLE,
    )
    total = int(await session.scalar(select(func.count(ChatSession.id)).where(*where)) or 0)
    rows = list(await session.scalars(
        select(ChatSession)
        .where(*where)
        .options(selectinload(ChatSession.messages))
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .offset(offset)
        .limit(limit)
    ))
    items: list[AgentSessionSummary] = []
    for chat_session in rows:
        messages = sorted(
            (
                message for message in chat_session.messages
                if message.role in (ChatMessageRole.user, ChatMessageRole.assistant)
            ),
            key=lambda message: message.id,
        )
        last_message = messages[-1] if messages else None
        items.append(AgentSessionSummary(
            session_id=chat_session.id,
            session_uuid=chat_session.session_id,
            title=chat_session.title,
            status=str(_enum_value(chat_session.status, "active")),
            message_count=len(messages),
            last_message=last_message.content[:180] if last_message else None,
            created_at=chat_session.created_at,
            updated_at=last_message.created_at if last_message else chat_session.updated_at,
        ))
    return AgentSessionListResponse(items=items, total=total)


@router.get("/sessions/{session_id}/messages", response_model=AgentHistoryResponse)
async def list_agent_messages(
    session_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentHistoryResponse:
    """按正序恢复 Agent 历史；before_id 支持向前翻页。"""
    if await _owned_agent_session(session, session_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Agent 会话不存在")
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role.in_((ChatMessageRole.user, ChatMessageRole.assistant)),
        )
        .order_by(ChatMessage.id.desc())
        .limit(limit + 1)
    )
    if before_id is not None:
        stmt = stmt.where(ChatMessage.id < before_id)
    rows = list(await session.scalars(stmt))
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    return AgentHistoryResponse(
        items=[
            AgentHistoryMessage(
                id=message.id,
                session_id=message.session_id,
                role=str(_enum_value(message.role)),
                content=message.content,
                metadata=message.metadata_,
                created_at=message.created_at,
            )
            for message in rows
        ],
        has_more=has_more,
    )


@router.post("/sessions", response_model=AgentSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_session(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentSessionResponse:
    chat_session = await ChatService(session).create_session(
        current_user.id,
        title=AGENT_SESSION_TITLE,
    )
    cart = await CartService(session).get_or_create_cart(current_user.id)
    cart.session_id = chat_session.id
    await session.commit()
    return AgentSessionResponse(
        session_id=chat_session.id,
        session_uuid=chat_session.session_id,
        cart_id=cart.id,
        title=chat_session.title,
    )


# ── 长期偏好 ──────────────────────────────────────────────────────

@router.get("/memory", response_model=AgentMemoryResponse, response_model_exclude_none=True)
async def read_agent_memory(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryResponse:
    row = await AgentMemoryService(session).get(current_user.id)
    return AgentMemoryResponse(
        preferences=(row.query_params if row else {}),
        updated_at=row.updated_at if row else None,
    )


@router.put("/memory", response_model=AgentMemoryResponse, response_model_exclude_none=True)
async def update_agent_memory(
    body: AgentMemoryUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryResponse:
    row = await AgentMemoryService(session).save(
        current_user.id,
        body.preferences.model_dump(exclude_unset=True),
        replace=body.replace,
    )
    return AgentMemoryResponse(preferences=row.query_params, updated_at=row.updated_at)


@router.delete("/memory", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await AgentMemoryService(session).clear(current_user.id)


# ── 消息与 SSE ────────────────────────────────────────────────────

def _recommendation(item: dict) -> AgentRecommendation:
    return AgentRecommendation(
        property_id=item["property_id"],
        rank=item.get("rank", 0),
        match_reason=item.get("match_reason", ""),
        pros=item.get("pros", []),
        cons=item.get("cons", []),
        property=_to_search_result(item["property"]),
        source_metadata=item.get("source_metadata", {}),
    )


@router.post("/sessions/{session_id}/messages", response_model=AgentMessageResponse)
async def send_agent_message(
    session_id: int,
    body: AgentMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMessageResponse:
    chat_session = await _owned_agent_session(session, session_id, current_user.id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Agent 会话不存在")
    from app.services.agentic.dispatcher import ASSISTANT_MESSAGE_ID_KEY, dispatch

    filters = body.filters.model_dump(exclude_unset=True) if body.filters else None
    context_filters = body.context_filters.model_dump(exclude_unset=True) if body.context_filters else None
    result = await dispatch(
        session=session,
        chat_session=chat_session,
        user_id=current_user.id,
        message=body.message,
        filters=filters,
        context_filters=context_filters,
        clear_fields=list(body.clear_fields),
        compare_property_ids=body.compare_property_ids,
        mode=body.mode,
        task_mode=body.task_mode,
    )
    assistant_message_id = result.get(ASSISTANT_MESSAGE_ID_KEY)
    serialized = _serialize_meta(result)
    if isinstance(assistant_message_id, int):
        await _update_history_metadata(
            session, chat_session.id, assistant_message_id, serialized
        )
    return AgentMessageResponse(
        reply=result["reply"],
        intent=result["intent"],
        recommendations=[_recommendation(item) for item in result.get("recommendations", []) if item.get("property") is not None],
        recommendation_total=int(result.get("recommendation_total") or 0),
        top_picks=[_recommendation(item) for item in result.get("top_picks", []) if item.get("property") is not None],
        cart_changed=result.get("cart_changed", False),
        ai_available=result.get("ai_available", True),
        quick_replies=result.get("quick_replies", []),
        links=[AgentLink(**item) for item in result.get("links", [])],
        thinking_steps=[ThinkingStep(**item) for item in result.get("thinking_steps", [])],
        guided_options=[GuidedOption(**item) for item in result.get("guided_options", [])],
        state_summary=AgentStateSummary(**result["state_summary"]) if result.get("state_summary") else None,
        turn_summary=AgentStateSummary(**result["turn_summary"]) if result.get("turn_summary") else None,
        filter_patch=result.get("filter_patch", {}),
        cleared_filters=result.get("cleared_filters", []),
        query_rewrite=result.get("query_rewrite"),
        sources=result.get("sources", []),
        task_boundary=(
            AgentTaskBoundary(**result["task_boundary"])
            if result.get("task_boundary") else None
        ),
    )


@router.post("/sessions/{session_id}/messages/stream")
async def send_agent_message_stream(
    session_id: int,
    body: AgentMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """SSE Agent 消息：状态帧、正文 token 帧、完整 result meta、[DONE]。"""
    chat_session = await _owned_agent_session(session, session_id, current_user.id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Agent 会话不存在")
    from app.services.agentic.dispatcher import (
        ASSISTANT_MESSAGE_ID_KEY,
        dispatch_stream,
    )

    filters = body.filters.model_dump(exclude_unset=True) if body.filters else None
    context_filters = body.context_filters.model_dump(exclude_unset=True) if body.context_filters else None
    stream_bind = session.bind
    if stream_bind is None:
        raise HTTPException(status_code=503, detail="数据库连接不可用")
    stream_session_factory = async_sessionmaker(
        bind=stream_bind,
        expire_on_commit=False,
    )
    user_id = current_user.id

    async def event_stream():
        yield ": connected\n\n"
        # FastAPI 0.112 会在 StreamingResponse 真正迭代前释放请求依赖；流内部
        # 使用独立会话，确保筛选状态和候选序号快照能够可靠持久化。
        async with stream_session_factory() as stream_session:
            stream_chat_session = await _owned_agent_session(
                stream_session, session_id, user_id
            )
            if stream_chat_session is None:
                yield f"data: {json.dumps({'error': 'Agent 会话不存在'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            history_meta: dict = {}
            assistant_message_id: int | None = None
            try:
                async for token, meta in dispatch_stream(
                    session=stream_session,
                    chat_session=stream_chat_session,
                    user_id=user_id,
                    message=body.message,
                    filters=filters,
                    context_filters=context_filters,
                    clear_fields=list(body.clear_fields),
                    compare_property_ids=body.compare_property_ids,
                    mode=body.mode,
                    task_mode=body.task_mode,
                ):
                    if token:
                        yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                    if meta:
                        persisted_id = meta.get(ASSISTANT_MESSAGE_ID_KEY)
                        if isinstance(persisted_id, int):
                            assistant_message_id = persisted_id
                        serialized = _serialize_meta(meta)
                        if serialized.get("event") == "result":
                            history_meta = serialized
                        yield f"data: {json.dumps({'meta': serialized}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("Agent SSE 回复失败")
                yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            if history_meta and assistant_message_id is not None:
                await _update_history_metadata(
                    stream_session,
                    stream_chat_session.id,
                    assistant_message_id,
                    history_meta,
                )
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


@router.get("/faqs", response_model=list[FaqChip])
async def get_faq_chips(current_user: User = Depends(get_current_user)) -> list[FaqChip]:
    return [FaqChip(**item) for item in list_faq_chips()]


# ── 候选清单与对比 ────────────────────────────────────────────────

@router.get("/cart", response_model=CartRead)
async def get_cart(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CartRead:
    cart, items = await CartService(session).get_cart_items(current_user.id)
    return CartRead(
        id=cart.id,
        session_id=cart.session_id,
        items=[
            CartItemRead(
                id=item.id,
                property_id=item.unit_type_id,
                reason=item.reason,
                created_at=item.created_at,
                property=_to_search_result(item.unit_type),
            )
            for item in items if item.unit_type is not None
        ],
    )


@router.post("/cart/items", response_model=CartItemRead)
async def add_cart_item(
    body: CartItemAddRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CartItemRead:
    try:
        item = await CartService(session).add_to_cart(
            current_user.id,
            body.property_id,
            body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CartItemRead(
        id=item.id,
        property_id=item.unit_type_id,
        reason=item.reason,
        created_at=item.created_at,
        property=_to_search_result(item.unit_type),
    )


@router.delete("/cart/items/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cart_item(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    if not await CartService(session).remove_from_cart(current_user.id, property_id):
        raise HTTPException(status_code=404, detail="候选清单中没有该户型")


@router.post("/cart/compare", response_model=CompareResponse)
async def compare_cart(
    body: CompareRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    try:
        result = await CompareAgent(session=session).compare(
            current_user.id,
            body.property_ids if body else None,
            body.priority if body else None,
            cart_agent=CartService(session),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CompareResponse(
        summary=result["summary"],
        items=[
            CompareItem(
                property_id=item["property_id"],
                title=item["title"],
                pros=item["pros"],
                cons=item["cons"],
                score=item["score"],
                score_breakdown=item.get("score_breakdown"),
                best_for=item["best_for"],
                commute=item.get("commute"),
                rating=item.get("rating"),
                review_count=item.get("review_count", 0),
                safety_score=item.get("safety_score"),
                property=_to_search_result(item["property"]) if item.get("property") else None,
            )
            for item in result["items"]
        ],
        recommendation=result["recommendation"],
        ai_available=result["ai_available"],
        priority=result.get("priority", "balanced"),
    )
