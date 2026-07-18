"""FAQ Agent —— FAQ 规则匹配（无 LLM，直接委托现有 agent_faq）。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class FAQAgent(BaseAgent):
    name = "faq_agent"
    description = "FAQ 规则匹配（押金/合同/预订流程等政策问题）"

    async def handle(self, context: AgentContext) -> AgentResult:
        from app.services.agent_faq import match_faq, get_faq

        message = context.user_message
        strength, hits = match_faq(message)

        if strength == "strong" and hits:
            entry = hits[0]
            chips = list(entry.next_chips) if entry.next_chips else []
            links = [{"label": l.label, "to": l.to} for l in (entry.links or [])]
            return AgentResult(
                content=entry.answer,
                success=True,
                data={"faq_id": entry.id, "strength": "strong", "chips": chips, "links": links},
            )

        if strength == "weak" and hits:
            chips = [e.chip for e in hits[:5]]
            names = "、".join(f"「{c}」" for c in chips)
            return AgentResult(
                content=f"你想了解的是 {names} 中的哪个？点下面的按钮选择。",
                success=True,
                data={"strength": "weak", "chips": chips},
            )

        entry = get_faq(message)
        if entry:
            return AgentResult(content=entry.answer, success=True, data={"faq_id": entry.id})

        return AgentResult(
            content="这是平台使用问题，建议查看帮助中心或联系客服。",
            success=True,
        )
