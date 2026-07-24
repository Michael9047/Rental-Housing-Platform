"""Agent 消息分发器 —— 轻量路由：分类 → 直接调 Agent/Service/Tool。

替代 Supervisor + DAG + AgentRegistry 的复杂编排链路。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.services.agentic.router import classify_message
from app.services.agentic.agents.search_agent import SearchAgent
from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.agentic.agents.cart_agent import CartService
from app.services.agent_faq import match_faq, get_faq
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


async def dispatch(
    session: AsyncSession,
    chat_session: ChatSession,
    user_id: int,
    message: str,
    filters: dict[str, Any] | None = None,
    compare_property_ids: list[int] | None = None,
) -> dict[str, Any]:
    """主入口：分类意图 → 分发执行 → 返回结果。

    链路：
      classify → search/compare/cart/faq/general → 持久化消息 → 返回
    """
    history = await _load_history(session, chat_session.id)
    classification = await classify_message(message, history)

    intent = classification.get("intent", "general")
    if compare_property_ids and len(compare_property_ids) >= 2:
        intent = "compare"

    # ── 分发执行 ──
    reply = ""
    recommendations: list[dict] = []
    top_picks: list[dict] = []
    cart_changed = False
    quick_replies: list[str] = []
    links: list[dict] = []
    extracted_filters = None
    source_info = ""
    score_gap = None
    relaxation_level = 0
    candidate_snapshot: list[int] = []

    if intent == "search":
        agent = SearchAgent(session=session)
        result = await agent.search(message=message, filters=filters)
        reply = result.get("reply", "")
        recommendations = result.get("recommendations", [])
        top_picks = result.get("top_picks", [])
        extracted_filters = result.get("extracted_filters")
        source_info = result.get("source_info", "")
        score_gap = result.get("score_gap")
        relaxation_level = result.get("relaxation_level", 0)
        candidate_snapshot = result.get("candidate_snapshot", [])

    elif intent == "compare":
        agent = CompareAgent(session=session)
        cart_svc = CartService(session=session)
        try:
            result = await agent.compare(
                user_id=user_id,
                property_ids=compare_property_ids,
                cart_agent=cart_svc,
            )
            reply = result.get("dimension_analysis", "") or result.get("summary", "")
            recommendations = result.get("items", [])
        except ValueError as e:
            reply = str(e)

    elif intent == "manage_cart":
        sub = classification.get("sub_intent", "view")
        cart_svc = CartService(session=session)
        if sub == "add":
            ids = _extract_ids(message, classification.get("refs", []))
            if ids:
                for pid in ids:
                    try:
                        await cart_svc.add_to_cart(user_id, pid)
                    except ValueError:
                        pass
                reply = "已加入候选清单。"
                cart_changed = True
            else:
                reply = "请告诉我要加入哪套房源。"
        elif sub == "remove":
            ids = _extract_ids(message, classification.get("refs", []))
            if ids:
                for pid in ids:
                    await cart_svc.remove_from_cart(user_id, pid)
                reply = "已移除。"
                cart_changed = True
            else:
                reply = "请指定要移除的房源。"
        else:
            _cart, items = await cart_svc.get_cart_items(user_id)
            reply = f"候选清单共 {len(items)} 套。" if items else "候选清单为空。"

    elif intent == "faq":
        strength, hits = match_faq(message)
        if strength == "strong" and hits:
            reply = hits[0].answer
            quick_replies = list(hits[0].next_chips) if hits[0].next_chips else []
        elif strength == "weak" and hits:
            reply = f"你想了解的是 {' / '.join(e.chip for e in hits[:5])} 中的哪个？"
            quick_replies = [e.chip for e in hits[:5]]
        else:
            entry = get_faq(message)
            reply = entry.answer if entry else "这是平台使用问题，建议查看帮助中心。"

    else:  # general
        llm = get_llm_service()
        if llm.is_available:
            msgs = [{"role": "system", "content": "你是留学生租房顾问，用口语化中文简洁回答。1-2句话。不编造房源。"}]
            msgs.extend(history)
            msgs.append({"role": "user", "content": message})
            reply = await llm.complete_text(msgs)
        else:
            reply = "我是租房推荐助手，告诉我你的预算和需求，我帮你筛房源。"

    # ── 持久化消息 ──
    user_msg = ChatMessage(session_id=chat_session.id, role=ChatMessageRole.user, content=message,
                           metadata_={"filters": filters or {}})
    assistant_msg = ChatMessage(session_id=chat_session.id, role=ChatMessageRole.assistant, content=reply,
                                metadata_={"intent": intent, "recommendations": [
                                    {"property_id": r.get("property_id", r.get("id", 0)),
                                     "match_reason": r.get("match_reason", "")}
                                    for r in recommendations
                                ]})
    session.add_all([user_msg, assistant_msg])
    await session.commit()

    return {
        "reply": reply, "intent": intent, "recommendations": recommendations,
        "cart_changed": cart_changed, "ai_available": get_llm_service().is_available,
        "quick_replies": quick_replies, "links": links,
        "extracted_filters": extracted_filters, "top_picks": top_picks,
        "score_gap": score_gap, "relaxation_level": relaxation_level,
        "candidate_snapshot": candidate_snapshot, "source_info": source_info,
    }


async def dispatch_stream(
    session: AsyncSession,
    chat_session: ChatSession,
    user_id: int,
    message: str,
    filters: dict[str, Any] | None = None,
    compare_property_ids: list[int] | None = None,
):
    """流式分发 —— yield (token, meta)，用于 SSE 端点。"""
    history = await _load_history(session, chat_session.id)
    classification = await classify_message(message, history)
    intent = classification.get("intent", "general")

    llm = get_llm_service()
    full_reply = ""
    recommendations = []
    meta = {"intent": intent}

    if intent == "search":
        agent = SearchAgent(session=session)
        result = await agent.search(message=message, filters=filters)
        recommendations = result.get("recommendations", [])
        meta["recommendations"] = [
            {"property_id": r["property_id"], "match_reason": r.get("match_reason", "")}
            for r in recommendations
        ]
        # 搜索的 AI 回复已在 search() 中生成，这里逐字 yield
        full_reply = result.get("reply", "")
        # 模拟流式：每 3 个字 yield 一次
        import asyncio
        for i in range(0, len(full_reply), 3):
            chunk = full_reply[i:i+3]
            yield chunk, None
            await asyncio.sleep(0.01)
        yield None, meta

    elif intent == "general":
        msgs = [{"role": "system", "content": "你是留学生租房顾问，口语化中文回答，1-2句话。"}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": message})
        async for token in llm.complete_text_stream(msgs, max_tokens=500):
            full_reply += token
            yield token, None
        yield None, meta

    elif intent == "faq":
        strength, hits = match_faq(message)
        if strength == "strong" and hits:
            full_reply = hits[0].answer
        elif strength == "weak" and hits:
            full_reply = f"你想了解的是 {' / '.join(e.chip for e in hits[:5])} 中的哪个？"
        else:
            entry = get_faq(message)
            full_reply = entry.answer if entry else "建议查看帮助中心。"
        yield full_reply, None
        yield None, meta

    else:  # manage_cart / compare — 暂不流式
        result = await dispatch(session, chat_session, user_id, message, filters, compare_property_ids)
        full_reply = result.get("reply", "")
        yield full_reply, meta

    # 持久化
    user_msg = ChatMessage(session_id=chat_session.id, role=ChatMessageRole.user,
                           content=message, metadata_={"filters": filters or {}})
    assistant_msg = ChatMessage(session_id=chat_session.id, role=ChatMessageRole.assistant,
                                content=full_reply, metadata_={"intent": intent, "recommendations": [
                                    {"property_id": r.get("property_id", r.get("id", 0)),
                                     "match_reason": r.get("match_reason", "")}
                                    for r in recommendations
                                ]})
    session.add_all([user_msg, assistant_msg])
    await session.commit()


# ── helpers ──────────────────────────────────────────────────────

async def _load_history(session: AsyncSession, session_id: int, limit: int = 10) -> list[dict]:
    from sqlalchemy import select
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(
        ChatMessage.created_at.desc()).limit(limit)
    msgs = list(await session.scalars(stmt))
    return [{"role": m.role.value, "content": m.content}
            for m in reversed(msgs)
            if m.role in (ChatMessageRole.user, ChatMessageRole.assistant)]


def _extract_ids(message: str, refs: list[int] | None = None) -> list[int]:
    import re
    ids = [int(m.group(1)) for m in re.finditer(r"房源\s*(\d+)", message)]
    return list(dict.fromkeys(ids)) if ids else (refs or [])
