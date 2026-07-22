"""Filter 到 Search 数据流与重复 LLM 防回归测试。"""
from unittest.mock import AsyncMock

import pytest

from app.services.agent_service import AgentService
from app.services.agentic.orchestration.supervisor import Supervisor
from app.services.agentic.orchestration.execution_dag import ExecutionDAG
from app.services.agentic.orchestration.types import AgentContext, AgentResult


def test_supervisor_applies_filter_context_updates() -> None:
    context = AgentContext(user_message="预算3000", filters=None)
    result = AgentResult(
        content="",
        data={"price_max": 3000},
        context_updates={
            "filters": {"price_max": 3000},
            "preference_state": {"version": 1},
        },
    )
    Supervisor._apply_context_updates(context, result)
    assert context.filters == {"price_max": 3000}
    assert context.extra["preference_state"] == {"version": 1}


def test_search_and_compare_dag_do_not_repeat_synthesis() -> None:
    search_agents = [node.agent_name for node in ExecutionDAG.from_intent("search").nodes]
    compare_agents = [node.agent_name for node in ExecutionDAG.from_intent("compare").nodes]
    assert search_agents == ["filter_agent", "search_agent"]
    assert compare_agents == ["compare_agent"]


@pytest.mark.asyncio
async def test_search_agent_receives_filter_agent_output(monkeypatch) -> None:
    captured = {}

    async def fake_recommend(_self, **kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "recommendations": []}

    monkeypatch.setattr(AgentService, "recommend_properties", fake_recommend)
    supervisor = Supervisor(session=object())
    context = AgentContext(
        user_message="预算3000",
        filters={"price_max": 3000},
        extra={"explicit_filters": {"district": "SIP"}},
    )
    result = await supervisor._run_search_agent(context)

    assert result.success
    assert captured["filters"] == {"district": "SIP"}
    assert captured["extracted_filters"] == {"price_max": 3000}


@pytest.mark.asyncio
async def test_recommend_skips_filter_llm_when_extracted_filters_supplied(monkeypatch) -> None:
    llm = SimpleLLM()
    monkeypatch.setattr("app.services.agent_service.get_llm_service", lambda: llm)

    service = AgentService(session=object())
    service.property_service.search = AsyncMock(return_value=[])
    await service.recommend_properties(
        "预算3000",
        extracted_filters={"price_max": 3000, "hard_filters": ["price_max"]},
    )
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_classify_prioritises_faq_rules_over_llm(monkeypatch) -> None:
    """FAQ 必须走确定性规则，不能被 LLM 分类结果盖掉。

    历史退化：Supervisor 接管入口后，FAQ 规则优先逻辑留在了没人调用的
    AgentService.handle_message 里，导致 LLM 不可用时"押金怎么退"被分到 general。
    """
    async def fake_classify(_self, *_args, **_kwargs):
        return {"intent": "search", "sub_intent": "browse", "stage": "explore",
                "complexity": 0.5, "confidence": 0.9, "routing": "agent", "refs": []}

    monkeypatch.setattr(AgentService, "classify_message", fake_classify)
    supervisor = Supervisor(session=object())

    result = await supervisor._classify("押金怎么退", [])
    assert result["intent"] == "faq"
    assert result["faq_topic"] == "deposit"
    assert result["used_llm"] is False

    # 非 FAQ 消息仍然交给 LLM 分类器
    passthrough = await supervisor._classify("找个园区3000以内的一居室", [])
    assert passthrough["intent"] == "search"


@pytest.mark.asyncio
async def test_hard_commute_constraint_without_institution_keeps_candidates(monkeypatch) -> None:
    """没识别到学校时算不出通勤，硬约束应跳过而不是把候选清空。

    FilterAgent 的 prompt 把"不超过/以内"判为 hard，用户又常常不提学校，
    所以"预算3000，通勤30分钟以内"是常见输入而非边角情况。
    """
    from types import SimpleNamespace

    from app.services import agent_service as agent_service_module
    from app.services.property_fact_service import (
        DataCompleteness,
        POISummary,
        PropertyFactBundle,
    )

    prop = SimpleNamespace(
        id=7, title="测试房源", country="CN", district="SIP",
        address="88 University Road", description="近地铁",
        price_monthly=2800, area_sqm=45, bedrooms=1, bathrooms=1,
        property_type="apartment", images=[], amenities=[],
    )

    async def fake_relaxed_search(_self, **_kwargs):
        return {"rows": [(prop, 0.9)], "relaxation_level": 0, "relaxed_fields": []}

    async def fake_build_bundles(_self, properties, **_kwargs):
        # 无起点坐标 → commute 全是 None，正是触发本 bug 的形态
        return {
            p.id: PropertyFactBundle(
                property_id=p.id,
                poi=POISummary(),
                commute=None,
                data_completeness=DataCompleteness(poi_cache_available=False),
            )
            for p in properties
        }

    monkeypatch.setattr(AgentService, "_search_with_relaxation", fake_relaxed_search)
    monkeypatch.setattr(
        agent_service_module.PropertyFactService, "build_bundles", fake_build_bundles
    )

    service = AgentService(session=object())
    result = await service.recommend_properties(
        "预算3000，通勤30分钟以内",
        extracted_filters={
            "price_max": 3000,
            "commute_minutes": 30,
            "hard_filters": ["price_max", "commute_minutes"],
        },
    )

    assert result["recommendations"], "无起点时不应把候选全部过滤掉"
    assert result["recommendations"][0]["property_id"] == 7


class SimpleLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("已有 FilterAgent 输出时不应再次调用条件提取 LLM")
