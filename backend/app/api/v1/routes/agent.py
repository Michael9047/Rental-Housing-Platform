"""租房推荐 Agent —— 会话、推荐、购物车、对比接口

轻量架构：Router 分类 → Dispatcher 分发 → Agent/Service/Tool 直接执行。
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.user import User
from app.schemas.agent import (
    AgentLink,
    AgentHistoryMessage,
    AgentHistoryResponse,
    AgentMemoryResponse,
    AgentMemoryUpdateRequest,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRecommendation,
    AgentSource,
    AgentStateSummary,
    AgentSessionListResponse,
    AgentSessionResponse,
    AgentSessionSummary,
    CartItemAddRequest,
    CartItemRead,
    CartRead,
    CompareItem,
    CompareRequest,
    CompareResponse,
    FaqChip,
    GuidedOption,
    QueryRewriteInfo,
    ReferenceResolutionInfo,
    ThinkingStep,
)
from app.schemas.property import PropertySearchResult
from app.services.agent_faq import list_faq_chips
from app.services.agentic.agents.cart_agent import CartService
from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.agentic.memory import (
    clear_user_memory,
    get_user_memory,
    memory_to_filters,
    save_user_memory,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_search_result(prop, property_id_override: int | None = None) -> PropertySearchResult:
    """兼容 UnitType 和 Property/Room 两种模型。"""
    # UnitType 对象 → 转为 PropertySearchResult 兼容 dict
    if hasattr(prop, 'institute_id') and not hasattr(prop, 'landlord_id'):
        # 这是 UnitType — 映射到 PropertySearchResult 的字段
        inst = getattr(prop, 'institute', None)
        name_lower = str(getattr(prop, "name", "")).lower()
        bedrooms = int(getattr(prop, "bedrooms", 0) or 0)
        if bedrooms == 0 or "studio" in name_lower or "单间" in name_lower:
            property_type = "studio"
        elif "shared" in name_lower or "合租" in name_lower or "床位" in name_lower:
            property_type = "shared"
        elif bedrooms == 1:
            property_type = "1-bed"
        elif bedrooms >= 2:
            property_type = "2-bed"
        else:
            property_type = "studio"
        amenities = list(dict.fromkeys([
            *[str(value) for value in (getattr(prop, "amenities", None) or []) if value],
            *[str(value) for value in (getattr(inst, "amenities", None) or []) if value],
        ]))
        return PropertySearchResult(
            id=property_id_override or prop.id,
            landlord_id=0,  # UnitType 没有 landlord，填 0
            title=prop.name,
            description=getattr(prop, 'description', None),
            address=getattr(inst, 'address', None) if inst else None,
            district=getattr(inst, 'district', None) if inst else None,
            country=getattr(inst, 'country', None) if inst else None,
            price_monthly=prop.base_rent,
            area_sqm=prop.area_sqm,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            property_type=property_type,
            status=getattr(prop, 'status', 'available'),
            currency=getattr(prop, 'currency', None),
            latitude=getattr(inst, 'latitude', None) if inst else None,
            longitude=getattr(inst, 'longitude', None) if inst else None,
            created_at=getattr(prop, 'created_at', None),
            updated_at=getattr(prop, 'updated_at', None),
            images=_unit_type_images(prop, property_id_override),
            institute_id=prop.institute_id,
            institute_name=getattr(inst, 'name', None) if inst else None,
            amenities=amenities or None,
            min_stay_months=getattr(prop, 'min_stay_months', None),
            special_offer=getattr(prop, 'special_offer', None),
        )
    result = PropertySearchResult.model_validate(prop)
    # 旧版独立房源把设施存成扁平文本；仅透传真实值，不再由前端按价格/户型猜测。
    if not result.amenities:
        raw_amenities = getattr(prop, "institute_amenities", None)
        if isinstance(raw_amenities, str) and raw_amenities.strip():
            try:
                parsed = json.loads(raw_amenities)
                if isinstance(parsed, list):
                    result.amenities = [str(value) for value in parsed if value]
            except (TypeError, ValueError, json.JSONDecodeError):
                result.amenities = [
                    value.strip()
                    for value in raw_amenities.replace("，", ",").split(",")
                    if value.strip()
                ]
    if not result.special_offer:
        result.special_offer = getattr(prop, "special_discount", None)
    return result


def _unit_type_images(prop, property_id_override: int | None = None) -> list:
    """UnitType.image_urls（URL 字符串数组）→ PropertyImageRead 列表。

    前端 getImageUrl 对 http 开头的 filename 直接原样用，否则拼 /api/v1/uploads/，
    两种存储形式都兼容。
    """
    from datetime import datetime, timezone

    from app.schemas.property_image import PropertyImageRead

    now = datetime.now(timezone.utc)
    return [
        PropertyImageRead(
            id=idx, property_id=property_id_override or prop.id, filename=url,
            original_name="", mime_type="", file_size=0,
            sort_order=idx, is_primary=(idx == 0),
            created_at=getattr(prop, "created_at", None) or now,
        )
        for idx, url in enumerate(getattr(prop, "image_urls", None) or [])
        if url
    ]


def _serialize_meta(meta: dict) -> dict:
    """流式 meta 里的 property 是 UnitType 对象，json.dumps 前统一序列化。"""
    out = dict(meta)
    for key in ("recommendations", "top_picks"):
        recs = out.get(key)
        if not recs:
            continue
        out[key] = [
            {
                **r,
                "property": _to_search_result(
                    r["property"], r.get("property_id")
                ).model_dump(mode="json"),
            }
            if r.get("property") is not None else r
            for r in recs
        ]
    return out


async def _update_latest_history_metadata(
    session: AsyncSession,
    session_id: int,
    serialized_meta: dict,
) -> None:
    """把已序列化的推荐卡、FAQ 链接等补入最新历史回复。"""
    assistant_message = await session.scalar(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == ChatMessageRole.assistant,
        )
        .order_by(ChatMessage.id.desc())
        .limit(1)
    )
    if assistant_message is None:
        return
    metadata = dict(assistant_message.metadata_ or {})
    for key in ("recommendations", "top_picks", "links", "ai_available"):
        if key in serialized_meta:
            metadata[key] = serialized_meta[key]
    assistant_message.metadata_ = metadata
    await session.commit()


# ── 会话 ──────────────────────────────────────────────────────────

@router.get("/sessions", response_model=AgentSessionListResponse)
async def list_agent_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentSessionListResponse:
    """列出当前用户的 Agent 对话记录，供侧栏恢复会话。"""
    total = int(await session.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == current_user.id)
        .where(ChatSession.session_kind == "agent")
    ) or 0)
    rows = list(await session.scalars(
        select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.session_kind == "agent",
        )
        .options(selectinload(ChatSession.messages))
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .offset(offset)
        .limit(limit)
    ))
    items: list[AgentSessionSummary] = []
    for chat_session in rows:
        messages = sorted(
            (
                message for message in (chat_session.messages or [])
                if message.role in (ChatMessageRole.user, ChatMessageRole.assistant)
            ),
            key=lambda message: (message.created_at, message.id),
        )
        last_message = messages[-1] if messages else None
        items.append(AgentSessionSummary(
            session_id=chat_session.id,
            session_uuid=chat_session.session_id,
            title=chat_session.title,
            status=(
                chat_session.status.value
                if hasattr(chat_session.status, "value") else str(chat_session.status)
            ),
            message_count=len(messages),
            last_message=(last_message.content[:180] if last_message else None),
            created_at=chat_session.created_at,
            updated_at=(last_message.created_at if last_message else chat_session.updated_at),
        ))
    return AgentSessionListResponse(items=items, total=total)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=AgentHistoryResponse,
)
async def list_agent_messages(
    session_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentHistoryResponse:
    """按时间正序回放会话消息；before_id 用于向前翻页。"""
    chat_service = ChatService(session)
    if await chat_service.get_session(
        session_id, current_user.id, session_kind="agent"
    ) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")
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
                role=message.role.value,
                content=message.content,
                metadata=message.metadata_,
                created_at=message.created_at,
            )
            for message in rows
        ],
        has_more=has_more,
    )


@router.get(
    "/memory",
    response_model=AgentMemoryResponse,
    response_model_exclude_none=True,
)
async def read_agent_memory(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryResponse:
    memory = await get_user_memory(session, current_user.id)
    if memory is None:
        return AgentMemoryResponse(preferences={})
    return AgentMemoryResponse(
        preferences=memory_to_filters(memory.preferences_json),
        updated_at=memory.updated_at,
    )


@router.put(
    "/memory",
    response_model=AgentMemoryResponse,
    response_model_exclude_none=True,
)
async def update_agent_memory(
    body: AgentMemoryUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryResponse:
    memory = await save_user_memory(
        session,
        current_user.id,
        body.preferences.model_dump(exclude_unset=True),
        replace=body.replace,
    )
    return AgentMemoryResponse(
        preferences=memory_to_filters(memory.preferences_json),
        updated_at=memory.updated_at,
    )


@router.delete("/memory", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await clear_user_memory(session, current_user.id)

@router.post("/sessions", response_model=AgentSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_session(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentSessionResponse:
    chat_service = ChatService(session)
    chat_session = await chat_service.create_session(
        current_user.id,
        title="租房推荐 Agent",
        session_kind="agent",
    )

    cart_agent = CartService(session=session)
    cart = await cart_agent.get_or_create_cart(current_user.id)
    # 购物车关联到最新会话
    cart.session_id = chat_session.id
    await session.commit()

    return AgentSessionResponse(
        session_id=chat_session.id,
        session_uuid=chat_session.session_id,
        cart_id=cart.id,
        title=chat_session.title,
    )


@router.post("/sessions/{session_id}/messages", response_model=AgentMessageResponse)
async def send_agent_message(
    session_id: int,
    body: AgentMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentMessageResponse:
    chat_service = ChatService(session)
    chat_session = await chat_service.get_session(
        session_id, current_user.id, session_kind="agent"
    )
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")

    from app.services.agentic.dispatcher import dispatch
    filters = body.filters.model_dump(exclude_none=True) if body.filters else None
    context_filters = (
        body.context_filters.model_dump(exclude_none=True)
        if body.context_filters else None
    )
    result = await dispatch(session=session, chat_session=chat_session, user_id=current_user.id,
                            message=body.message, filters=filters,
                            context_filters=context_filters,
                            compare_property_ids=body.compare_property_ids,
                            mode=body.mode)
    await _update_latest_history_metadata(
        session,
        chat_session.id,
        _serialize_meta(result),
    )

    return AgentMessageResponse(
        reply=result["reply"],
        intent=result["intent"],
        recommendations=[
            AgentRecommendation(
                property_id=r["property_id"],
                rank=r.get("rank", 0),
                final_score=r.get("final_score", 0.0),
                score_breakdown=r.get("score_breakdown", {}),
                match_reason=r.get("match_reason", ""),
                pros=r.get("pros", []),
                cons=r.get("cons", []),
                property=_to_search_result(r["property"], r["property_id"]),
                poi_distances=r.get("poi_distances"),
                source_metadata=r.get("source_metadata", {}),
            )
            for r in result.get("recommendations", [])
        ],
        top_picks=[
            AgentRecommendation(
                property_id=tp["property_id"],
                rank=tp.get("rank", 0),
                final_score=tp.get("final_score", 0.0),
                score_breakdown=tp.get("score_breakdown", {}),
                match_reason=tp.get("match_reason", ""),
                pros=tp.get("pros", []),
                cons=tp.get("cons", []),
                property=_to_search_result(tp["property"], tp["property_id"]),
                poi_distances=tp.get("poi_distances"),
                source_metadata=tp.get("source_metadata", {}),
            )
            for tp in result.get("top_picks", [])
        ],
        cart_changed=result.get("cart_changed", False),
        ai_available=result.get("ai_available", True),
        quick_replies=result.get("quick_replies", []),
        links=[AgentLink(**link) for link in result.get("links", [])],
        thinking_steps=[
            ThinkingStep(**step) for step in result.get("thinking_steps", [])
        ],
        guided_options=[
            GuidedOption(**opt) for opt in result.get("guided_options", [])
        ],
        raw_intent=result.get("raw_intent", "general"),
        stage=result.get("stage", "explore"),
        sources=[AgentSource(**source) for source in result.get("sources", [])],
        relaxation_trace=result.get("relaxation_trace", []),
        query_rewrite=(
            QueryRewriteInfo(**result["query_rewrite"])
            if result.get("query_rewrite") else None
        ),
        reference_resolution=(
            ReferenceResolutionInfo(**result["reference_resolution"])
            if result.get("reference_resolution") else None
        ),
        state_summary=(
            AgentStateSummary(**result["state_summary"])
            if result.get("state_summary") else None
        ),
        filter_patch=result.get("filter_patch", {}),
    )


@router.post("/sessions/{session_id}/messages/stream")
async def send_agent_message_stream(
    session_id: int,
    body: AgentMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """流式 Agent 消息 —— SSE 逐 token 返回 AI 回复。"""
    from fastapi.responses import StreamingResponse
    from app.services.agentic.dispatcher import dispatch_stream

    chat_service = ChatService(session)
    chat_session = await chat_service.get_session(
        session_id, current_user.id, session_kind="agent"
    )
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")

    filters = body.filters.model_dump(exclude_none=True) if body.filters else None
    context_filters = (
        body.context_filters.model_dump(exclude_none=True)
        if body.context_filters else None
    )

    async def event_stream():
        history_meta: dict = {}
        # 先发 SSE 注释帧，让浏览器和反向代理立即建立流，
        # 避免意图识别/检索期间一直等到首个正文 token 才收到响应头。
        yield ": connected\n\n"
        try:
            async for token, meta in dispatch_stream(
                session=session, chat_session=chat_session, user_id=current_user.id,
                message=body.message, filters=filters,
                context_filters=context_filters,
                compare_property_ids=body.compare_property_ids,
                mode=body.mode,
            ):
                if token:
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                if meta:
                    serialized_meta = _serialize_meta(meta)
                    if serialized_meta.get("event") == "result":
                        history_meta.update(serialized_meta)
                    yield f"data: {json.dumps({'meta': serialized_meta}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("Agent SSE 流式回复失败")
            yield (
                "data: "
                f"{json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            )
        if history_meta:
            await _update_latest_history_metadata(
                session,
                chat_session.id,
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
async def get_faq_chips(
    current_user: User = Depends(get_current_user),
) -> list[FaqChip]:
    """FAQ 快捷入口 chips（前端渲染在输入框上方/气泡里）"""
    return [FaqChip(**c) for c in list_faq_chips()]


# ── 购物车 ────────────────────────────────────────────────────────

@router.get("/cart", response_model=CartRead)
async def get_cart(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CartRead:
    cart_agent = CartService(session=session)
    cart, items = await cart_agent.get_cart_items(current_user.id)
    return CartRead(
        id=cart.id,
        session_id=cart.session_id,
        items=[
            CartItemRead(
                id=item.id,
                property_id=item.property_id,
                reason=item.reason,
                created_at=item.created_at,
                property=_to_search_result(item.property),
            )
            for item in items
            if item.property is not None
        ],
    )


@router.post("/cart/items", response_model=CartItemRead)
async def add_cart_item(
    body: CartItemAddRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CartItemRead:
    cart_agent = CartService(session=session)
    try:
        item = await cart_agent.add_to_cart(current_user.id, body.property_id, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return CartItemRead(
        id=item.id,
        property_id=item.property_id,
        reason=item.reason,
        created_at=item.created_at,
        property=_to_search_result(item.property),
    )


@router.delete("/cart/items/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cart_item(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    cart_agent = CartService(session=session)
    removed = await cart_agent.remove_from_cart(current_user.id, property_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车中没有该房源")


@router.post("/cart/compare", response_model=CompareResponse)
async def compare_cart(
    body: CompareRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    compare_agent = CompareAgent(session=session)
    cart_agent = CartService(session=session)
    property_ids = body.property_ids if body else None
    priority = body.priority if body else None
    try:
        result = await compare_agent.compare(current_user.id, property_ids, priority, cart_agent=cart_agent)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return CompareResponse(
        summary=result["summary"],
        items=[
            CompareItem(
                property_id=it["property_id"],
                title=it["title"],
                pros=it["pros"],
                cons=it["cons"],
                score=it["score"],
                score_breakdown=it.get("score_breakdown"),
                best_for=it["best_for"],
                commute=it.get("commute"),
                rating=it.get("rating"),
                review_count=it.get("review_count", 0),
                property=_to_search_result(it["property"]) if it.get("property") is not None else None,
            )
            for it in result["items"]
        ],
        recommendation=result["recommendation"],
        ai_available=result["ai_available"],
        priority=result.get("priority", "balanced"),
    )
