"""Agent 记忆、查询改写、约束消融、重排与上下文打包的纯函数测试。"""
from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.agent_intelligence import AgentUserMemory
from app.services.agentic.context import pack_grounded_candidates
from app.services.agentic.memory import (
    AgentMemoryService,
    merge_dialogue_filters,
    resolve_references,
)
from app.services.agentic.query_understanding import _rule_fallback
from app.services.agentic.retrieval import (
    apply_constraint_ablation,
    candidate_matches_filters,
    rerank_candidates,
)


def _candidate(
    candidate_id: int,
    *,
    price: int,
    district: str = "伦敦",
    area: int | None = 30,
    bedrooms: int = 1,
    description: str = "安静公寓，带阳台",
) -> dict:
    unit_type = SimpleNamespace(
        id=candidate_id,
        name=f"测试户型 {candidate_id}",
        base_rent=Decimal(price),
        area_sqm=Decimal(area) if area is not None else None,
        bedrooms=bedrooms,
        bathrooms=1,
        min_stay_months=3,
        available_from=None,
        amenities=["阳台"],
        image_urls=["https://example.com/room.jpg"],
        description=description,
        currency="GBP",
        special_offer=None,
    )
    institute = SimpleNamespace(
        id=candidate_id,
        name=f"测试公寓 {candidate_id}",
        name_cn=None,
        district=district,
        city=district,
        country="GB",
        address=f"{district} Test Road",
        amenities=["电梯"],
        description="公寓真实描述",
        female_only=False,
    )
    return {
        "unit_type": unit_type,
        "institute": institute,
        "available_rooms": 2,
        "embedding_score": 0.7,
        "_property_id": candidate_id + 1000,
        "_unit_type_id": candidate_id,
        "_commute_minutes": 20,
        "_commute_source": "lookup_table",
        "_poi_distances": {"transit": 400},
        "_poi_score": 80,
        "_source_kind": "unit_type",
    }


class DialogueMemoryTests(unittest.TestCase):
    def test_filter_merge_preserves_state_and_honours_removal(self) -> None:
        merged = merge_dialogue_filters(
            message="不要独卫了，预算提高到1800",
            previous={"district": "伦敦", "price_max": 1500, "amenities": ["独立卫浴", "电梯"]},
            memory_filters={"room_type": "studio"},
            extracted={"price_max": 1800},
            request_filters=None,
            remove_values={"amenities": ["独立卫浴"]},
        )
        self.assertEqual(merged["district"], "伦敦")
        self.assertEqual(merged["room_type"], "studio")
        self.assertEqual(merged["price_max"], 1800)
        self.assertEqual(merged["amenities"], ["电梯"])

    def test_reset_drops_previous_and_long_term_filters(self) -> None:
        merged = merge_dialogue_filters(
            message="重新开始，只看新加坡",
            previous={"district": "伦敦", "price_max": 1500},
            memory_filters={"room_type": "studio"},
            extracted={"district": "新加坡"},
            request_filters=None,
        )
        self.assertEqual(merged, {"district": "新加坡"})

    def test_long_term_evidence_counts_once_per_session(self) -> None:
        chat_session = SimpleNamespace(id=1, accumulated_filters={})
        service = AgentMemoryService(None, chat_session, 7)
        memory = AgentUserMemory(user_id=7, preferences_json={})

        service._update_long_term_memory(memory, {"price_max": 1500}, 1)
        service._update_long_term_memory(memory, {"price_max": 1500}, 1)
        self.assertEqual(memory.preferences_json["price_max"]["evidence_count"], 1)

        service._update_long_term_memory(memory, {"price_max": 1500}, 2)
        service._update_long_term_memory(memory, {"price_max": 1500}, 3)
        self.assertEqual(memory.preferences_json["price_max"]["evidence_count"], 3)
        self.assertGreaterEqual(memory.preferences_json["price_max"]["confidence"], 0.75)

        service._update_long_term_memory(
            memory,
            {},
            4,
            remove_fields=["price_max"],
        )
        self.assertNotIn("price_max", memory.preferences_json)

    def test_reference_resolution_uses_rank_and_semantic_alias(self) -> None:
        refs = {
            "ordinal_refs": {"1": 101, "2": 202},
            "semantic_refs": {"cheapest": 202},
        }
        resolved = resolve_references("第二套和最便宜的哪个好", refs)
        self.assertEqual(resolved.resolved_ids, [202])
        self.assertFalse(resolved.unresolved)


class QueryRewriteTests(unittest.TestCase):
    def test_rule_fallback_extracts_budget_school_and_commute(self) -> None:
        result = _rule_fallback(
            "UCL附近1500镑以内studio，一定要独卫，步行15分钟以内",
            {},
        )
        self.assertEqual(result.extracted_filters["institution"], "UCL")
        self.assertEqual(result.extracted_filters["price_max"], 1500)
        self.assertEqual(result.extracted_filters["currency"], "GBP")
        self.assertEqual(result.extracted_filters["room_type"], "studio")
        self.assertEqual(result.extracted_filters["commute_minutes"], 15)
        self.assertIn("amenities", result.extracted_filters["hard_filters"])
        self.assertIn("当前有效条件", result.rewritten_query)


class SearchAgentBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_agent_requires_dispatcher_understanding(self) -> None:
        """SearchAgent 不应绕过 Dispatcher 自行判断搜索场景。"""
        from app.services.agentic.agents.search_agent import SearchAgent

        agent = SearchAgent(session=None)
        with self.assertRaisesRegex(ValueError, "Dispatcher"):
            await agent._pipeline("帮我找学校附近的房子")

    async def test_handle_does_not_choose_react_by_keywords(self) -> None:
        """通勤、周边等关键词不应再让 SearchAgent 自行切换执行路径。"""
        from app.services.agentic.agents.search_agent import SearchAgent
        from app.services.agentic.orchestration.types import AgentContext
        from app.services.agentic.query_understanding import QueryUnderstanding

        agent = SearchAgent(session=None)
        agent.search = AsyncMock(return_value={"reply": "已执行确定性搜索"})
        agent.search_react = AsyncMock(side_effect=AssertionError("不应调用 ReAct"))
        context = AgentContext(
            user_message="学校附近，通勤方便，周边要有超市",
            filters={"institution": "UCL"},
            extra={
                "query_understanding": QueryUnderstanding(
                    extracted_filters={"institution": "UCL"},
                    rewritten_query="UCL 附近通勤方便且靠近超市的房源",
                ),
                "stage": "narrow",
            },
        )

        result = await agent.handle(context)

        self.assertTrue(result.success)
        agent.search.assert_awaited_once()
        agent.search_react.assert_not_awaited()


class RetrievalTests(unittest.TestCase):
    def test_missing_commute_and_description_only_amenity_do_not_satisfy_hard_filter(self) -> None:
        item = _candidate(1, price=100)
        item["_commute_minutes"] = None
        item["unit_type"].amenities = []
        item["institute"].amenities = []
        item["unit_type"].description = "附近没有泳池"
        self.assertFalse(candidate_matches_filters(item, {"commute_minutes": 20}))
        self.assertFalse(candidate_matches_filters(item, {"amenities": ["泳池"]}))

    def test_zero_result_applies_only_one_soft_relaxation(self) -> None:
        price_miss = _candidate(1, price=120, district="伦敦")
        district_miss = _candidate(2, price=80, district="剑桥")
        selected, effective, traces, level = apply_constraint_ablation(
            [price_miss, district_miss],
            {"district": "伦敦", "price_max": 100, "currency": "GBP"},
            min_results=3,
        )
        self.assertEqual(level, 1)
        self.assertEqual(effective["price_max"], 120)
        self.assertEqual([item["unit_type"].id for item in selected], [1])
        self.assertEqual(sum(1 for trace in traces if trace["applied"]), 1)

    def test_one_strict_result_is_kept_and_relaxation_only_suggested(self) -> None:
        strict = _candidate(1, price=90, district="伦敦")
        miss = _candidate(2, price=115, district="伦敦")
        selected, effective, traces, level = apply_constraint_ablation(
            [strict, miss],
            {"district": "伦敦", "price_max": 100, "currency": "GBP"},
            min_results=3,
        )
        self.assertEqual(level, 0)
        self.assertEqual(effective["price_max"], 100)
        self.assertEqual([item["unit_type"].id for item in selected], [1])
        self.assertTrue(any(trace["after_count"] > trace["before_count"] for trace in traces))

    def test_rerank_is_deterministic_and_exposes_breakdown(self) -> None:
        expensive = _candidate(1, price=1800)
        cheap = _candidate(2, price=1400)
        ranked = rerank_candidates(
            [expensive, cheap],
            query="伦敦 1500镑 阳台",
            filters={"district": "伦敦", "price_max": 1500, "currency": "GBP"},
        )
        self.assertEqual(ranked[0]["unit_type"].id, 2)
        self.assertEqual(ranked[0]["_rank"], 1)
        self.assertEqual(
            set(ranked[0]["_score_breakdown"]),
            {"semantic", "lexical", "price", "commute", "poi", "quality", "constraint"},
        )


class ContextPackingTests(unittest.TestCase):
    def test_candidate_context_uses_property_id_and_respects_limit(self) -> None:
        candidates = rerank_candidates(
            [_candidate(1, price=1400), _candidate(2, price=1500)],
            query="伦敦单间",
            filters={"district": "伦敦", "currency": "GBP"},
        )
        packed = pack_grounded_candidates(
            query="伦敦单间",
            stage="narrow",
            filters={"district": "伦敦"},
            candidates=candidates,
            school="UCL",
            currency="GBP",
            relaxation_trace=[],
            max_candidates=1,
            char_budget=12_000,
        )
        self.assertEqual(len(packed["candidates"]), 1)
        self.assertEqual(
            packed["candidates"][0]["id"],
            candidates[0]["_property_id"],
        )
        self.assertEqual(packed["candidates"][0]["unit_type_id"], candidates[0]["_unit_type_id"])
        self.assertEqual(packed["grounding_policy"]["missing"], "值为 null 或来源为 missing 时必须说暂无数据")


if __name__ == "__main__":
    unittest.main()
