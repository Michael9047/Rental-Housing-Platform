"""租房推荐 Agent —— 会话、推荐、购物车、对比接口"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.agent import (
    AgentElicit,
    AgentHistoryMessage,
    AgentLink,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRecommendation,
    AgentSessionResponse,
    AgentSessionSummary,
    CartItemAddRequest,
    CartItemRead,
    CartRead,
    CompareItem,
    CompareRequest,
    CompareResponse,
    FaqChip,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
)
from app.schemas.property import PropertySearchResult
from app.services.agent_faq import list_faq_chips
from app.services.agent_service import DEFAULT_SESSION_TITLE, AgentService
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
    chat_session = await chat_service.create_session(current_user.id, title=DEFAULT_SESSION_TITLE)
    # 标记为 AI 管家会话（与客服会话共用 chat_sessions 表，靠 kind 区分）
    chat_session.kind = "agent"

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


@router.get("/sessions", response_model=list[AgentSessionSummary])
async def list_agent_sessions(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AgentSessionSummary]:
    """左侧对话列表：该用户的全部 AI 管家会话，最近活跃在前"""
    sessions = await AgentService(session).list_sessions(current_user.id)
    return [AgentSessionSummary.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[AgentHistoryMessage])
async def get_agent_session_messages(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AgentHistoryMessage]:
    """回放历史会话（推荐卡按 property_id 还原成真实房源）"""
    agent_service = AgentService(session)
    chat_session = await agent_service.get_session(session_id, current_user.id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")

    msgs = await agent_service.get_session_messages(session_id)
    return [
        AgentHistoryMessage(
            role=m["role"],
            content=m["content"],
            recommendations=[
                AgentRecommendation(
                    property_id=r["property_id"],
                    match_reason=r.get("match_reason", ""),
                    pros=r.get("pros", []),
                    cons=r.get("cons", []),
                    property=_to_search_result(r["property"]),
                )
                for r in m["recommendations"]
            ],
            elicit=AgentElicit(**m["elicit"]) if m.get("elicit") else None,
            feedback=m.get("feedback"),
            intent=m.get("intent"),
            created_at=m["created_at"],
            id=m["id"],
        )
        for m in msgs
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_session(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await AgentService(session).delete_session(session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")


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
        chat_session, current_user.id, body.message, filters, body.slot_answers
    )

    return AgentMessageResponse(
        message_id=result.get("message_id"),
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
        elicit=AgentElicit(**result["elicit"]) if result.get("elicit") else None,
    )


@router.patch("/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def set_message_feedback(
    message_id: int,
    body: MessageFeedbackRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MessageFeedbackResponse:
    """给某条 AI 回复点赞/点踩；再次提交同值等于取消（前端自行传 null 实现）"""
    ok = await AgentService(session).set_message_feedback(
        current_user.id, message_id, body.feedback
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    return MessageFeedbackResponse(message_id=message_id, feedback=body.feedback)


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
