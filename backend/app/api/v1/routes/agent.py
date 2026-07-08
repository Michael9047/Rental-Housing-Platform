"""租房推荐 Agent —— 会话、推荐、购物车、对比接口"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.agent import (
    AgentLink,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRecommendation,
    AgentSessionResponse,
    CartItemAddRequest,
    CartItemRead,
    CartRead,
    CompareItem,
    CompareRequest,
    CompareResponse,
    FaqChip,
)
from app.schemas.property import PropertySearchResult
from app.services.agent_faq import list_faq_chips
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_search_result(prop) -> PropertySearchResult:
    return PropertySearchResult.model_validate(prop)


# ── 会话 ──────────────────────────────────────────────────────────

@router.post("/sessions", response_model=AgentSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_session(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentSessionResponse:
    chat_service = ChatService(session)
    chat_session = await chat_service.create_session(current_user.id, title="租房推荐 Agent")

    agent_service = AgentService(session)
    cart = await agent_service.get_or_create_cart(current_user.id)
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
    chat_session = await chat_service.get_session(session_id, current_user.id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")

    agent_service = AgentService(session)
    filters = body.filters.model_dump(exclude_none=True) if body.filters else None
    result = await agent_service.handle_message(
        chat_session, current_user.id, body.message, filters
    )

    return AgentMessageResponse(
        reply=result["reply"],
        intent=result["intent"],
        recommendations=[
            AgentRecommendation(
                property_id=r["property_id"],
                match_reason=r.get("match_reason", ""),
                pros=r.get("pros", []),
                cons=r.get("cons", []),
                property=_to_search_result(r["property"]),
            )
            for r in result["recommendations"]
        ],
        cart_changed=result["cart_changed"],
        ai_available=result["ai_available"],
        quick_replies=result.get("quick_replies", []),
        links=[AgentLink(**link) for link in result.get("links", [])],
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
    agent_service = AgentService(session)
    cart, items = await agent_service.get_cart_items(current_user.id)
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
    agent_service = AgentService(session)
    try:
        item = await agent_service.add_to_cart(current_user.id, body.property_id, body.reason)
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
    agent_service = AgentService(session)
    removed = await agent_service.remove_from_cart(current_user.id, property_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车中没有该房源")


@router.post("/cart/compare", response_model=CompareResponse)
async def compare_cart(
    body: CompareRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    agent_service = AgentService(session)
    property_ids = body.property_ids if body else None
    priority = body.priority if body else None
    try:
        result = await agent_service.compare_cart(current_user.id, property_ids, priority)
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
