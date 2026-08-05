"""Agent SSE 与生成式分支的真流式回归测试。"""

import json

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.services.agentic import dispatcher
from app.services.agentic.agents import compare_agent as compare_module
from app.services.agentic.agents import search_agent as search_module
from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.agentic.agents.search_agent import SearchAgent
from app.services.llm_service import LLMService


class _ChunkedLLM:
    """仅提供流式接口；若代码退回非流式补全，测试会直接失败。"""

    is_available = True

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.calls = 0

    async def complete_text_stream(self, *_args, **_kwargs):
        self.calls += 1
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_llm_service_requests_provider_stream_mode() -> None:
    class ProviderChunks:
        def __init__(self) -> None:
            self._chunks = iter(["你", "好"])

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                content = next(self._chunks)
            except StopIteration as exc:
                raise StopAsyncIteration from exc
            return SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
            )

    class Completions:
        def __init__(self) -> None:
            self.kwargs = {}

        async def create(self, **kwargs):
            self.kwargs = kwargs
            return ProviderChunks()

    completions = Completions()
    service = object.__new__(LLMService)
    service._deepseek_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    service._openai_client = None
    service._deepseek_model = "stream-test-model"
    service._openai_model = "unused"

    tokens = [token async for token in service.complete_text_stream(
        [{"role": "user", "content": "你好"}]
    )]

    assert tokens == ["你", "好"]
    assert completions.kwargs["stream"] is True


def _general_context() -> SimpleNamespace:
    state = SimpleNamespace(filters_json={}, stage="general")
    runtime = SimpleNamespace(
        state=state,
        reference_resolution=SimpleNamespace(
            labels=[], unresolved=[],
        ),
    )
    steps = SimpleNamespace(snapshot=lambda *_args: [])
    return SimpleNamespace(
        intent="general",
        classification={"sub_intent": "chitchat"},
        stage="general",
        resolved_ids=[],
        runtime=runtime,
        history=[],
        message="你好",
        steps=steps,
    )


@pytest.mark.asyncio
async def test_general_agent_forwards_upstream_deltas(monkeypatch) -> None:
    llm = _ChunkedLLM(["第一段", "第二段"])
    monkeypatch.setattr(dispatcher, "get_llm_service", lambda: llm)

    events = [event async for event in dispatcher._execute_general_stream(
        _general_context()
    )]

    assert [token for token, _meta in events if token] == ["第一段", "第二段"]
    assert events[-1][1]["reply"] == "第一段第二段"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_search_agent_forwards_upstream_deltas(monkeypatch) -> None:
    chunks = ["第一段真实的流式推荐文本，", "第二段继续从上游模型到达。"]
    llm = _ChunkedLLM(chunks)
    monkeypatch.setattr(search_module, "get_llm_service", lambda: llm)

    agent = SearchAgent(session=SimpleNamespace())
    understanding = SimpleNamespace(rewritten_query="")
    prepared = {
        "unit_results": [SimpleNamespace(id=1)],
        "all_recs": [],
        "top_picks": [],
        "guided_options": [],
        "effective_filters": {},
        "explicit_filters": {},
        "understanding": understanding,
        "score_gap": None,
        "relaxation_level": 0,
        "relaxation_trace": [],
        "candidate_snapshot": [],
        "source_manifest": {},
        "sources": [],
        "source_info": "",
        "latency_ms": 1,
    }

    async def fake_pipeline(*_args, **_kwargs):
        return prepared

    monkeypatch.setattr(agent, "_pipeline", fake_pipeline)
    monkeypatch.setattr(
        agent,
        "_reply_messages",
        lambda _prepared: [{"role": "user", "content": "推荐房源"}],
    )

    events = [event async for event in agent.search_stream("推荐房源")]

    assert [event["text"] for event in events if event["type"] == "token"] == chunks
    assert events[-1]["type"] == "meta"
    assert events[-1]["reply"] == "".join(chunks)
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_compare_agent_forwards_upstream_deltas(monkeypatch) -> None:
    chunks = ["结论先说：", "1 号房更适合预算优先。"]
    llm = _ChunkedLLM(chunks)
    props = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    extras = {
        1: {"commute": "500m", "rating": 4.5},
        2: {"commute": None, "rating": None},
    }
    scores = {
        1: {
            "total": 88,
            "breakdown": {"price": 90, "commute": 80, "space": 85, "rating": 90},
        },
        2: {
            "total": 70,
            "breakdown": {"price": 70, "commute": 50, "space": 80, "rating": 50},
        },
    }
    agent = CompareAgent(session=SimpleNamespace())
    agent._llm_service = llm

    async def resolve(*_args):
        return props

    async def gather(_props):
        return [], extras

    monkeypatch.setattr(agent, "_resolve_compare_properties", resolve)
    monkeypatch.setattr(agent, "_gather_compare_metrics", gather)
    monkeypatch.setattr(compare_module, "compute_scores", lambda *_args: scores)
    monkeypatch.setattr(
        compare_module,
        "property_to_dict",
        lambda prop: {
            "title": f"房源 {prop.id}",
            "price_monthly": 2000 + prop.id,
            "bedrooms": 1,
            "bathrooms": 1,
            "area_sqm": 30,
        },
    )
    monkeypatch.setattr(
        compare_module,
        "format_property_money",
        lambda _prop, value: f"¥{value}",
    )
    monkeypatch.setattr(
        agent,
        "_rule_based_compare",
        lambda *_args: {
            "summary": "规则摘要",
            "dimension_analysis": "规则对比",
            "items": [{"property_id": 1}, {"property_id": 2}],
            "recommendation": "房源 1",
            "ai_available": False,
            "priority": "budget",
        },
    )

    events = [event async for event in agent.compare_stream(
        user_id=1,
        property_ids=[1, 2],
        priority="budget",
    )]

    assert [event["text"] for event in events if event["type"] == "token"] == chunks
    assert events[-1]["type"] == "meta"
    assert events[-1]["reply"] == "".join(chunks)
    assert events[-1]["ai_available"] is True
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_agent_sse_endpoint_disables_proxy_buffering(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    register = await client.post(
        "/api/v1/auth/register", json=landlord_register_payload
    )
    assert register.status_code == 201, register.text
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "hello"},
        headers={**headers, "Accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert "no-transform" in response.headers["cache-control"]
    assert response.text.startswith(": connected\n\n")
    assert '"event": "status"' in response.text
    assert '"event": "result"' in response.text
    assert response.text.endswith("data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_all_primary_chips_are_sent_as_multiple_sse_chunks(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    register = await client.post(
        "/api/v1/auth/register", json=landlord_register_payload
    )
    assert register.status_code == 201, register.text
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = created.json()["session_id"]

    for message in ("我要找房", "预订流程", "合同如何签", "押金怎么退"):
        response = await client.post(
            f"/api/v1/agent/sessions/{session_id}/messages/stream",
            json={"message": message},
            headers={**headers, "Accept": "text/event-stream"},
        )

        token_frames = [
            json.loads(line.removeprefix("data: "))["token"]
            for line in response.text.splitlines()
            if line.startswith("data: {") and '"token"' in line
        ]
        assert response.status_code == 200
        assert len(token_frames) > 2
        assert "".join(token_frames)
