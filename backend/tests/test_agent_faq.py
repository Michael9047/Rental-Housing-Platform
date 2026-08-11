"""FAQ 工作流测试：规则匹配三档（强/弱/无）+ 接口行为"""
import json

import pytest
from httpx import AsyncClient

from app.services.agent_faq import FAQ_ENTRIES, get_faq, match_faq


# ── 规则匹配单元测试 ──────────────────────────────────────────────

def test_chip_text_is_strong_match() -> None:
    """点 chip（消息即 chip 文案）→ 精确命中对应工作流"""
    for entry in FAQ_ENTRIES:
        strength, hits = match_faq(entry.chip)
        assert strength == "strong"
        assert hits[0].id == entry.id


def test_paraphrase_is_strong_match() -> None:
    """明确问法（同义句/强正则）→ 强命中"""
    cases = {
        "怎么租房子啊": "find_house",
        "押金什么时候能退给我": "deposit",
        "我想了解一下退款流程": "refund",
        "合同条款里要注意什么": "contract",
        "你们平台收哪些费用": "fees",
    }
    for message, expected in cases.items():
        strength, hits = match_faq(message)
        assert strength == "strong", message
        assert hits[0].id == expected, message


def test_bare_topic_word_is_weak_match() -> None:
    """只说主题词（如"押金"）→ 弱命中，交上层反问确认"""
    strength, hits = match_faq("押金")
    assert strength == "weak"
    assert any(e.id == "deposit" for e in hits)


def test_long_recommend_query_not_intercepted() -> None:
    """带主题词的长找房句 → 不被 FAQ 弱匹配误拦（交给意图分类）"""
    strength, _ = match_faq("帮我找个苏州工业园区3000以内的房子，顺便预约看房")
    assert strength == "none"


def test_unrelated_message_no_match() -> None:
    strength, hits = match_faq("我想找近地铁的单间")
    assert strength == "none"
    assert hits == []


# ── 接口测试 ──────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, payload: dict[str, str]) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json=payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": payload["username"], "password": payload["password"]},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_faq_chips_endpoint(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    resp = await client.get("/api/v1/agent/faqs", headers=headers)
    assert resp.status_code == 200
    chips = resp.json()
    assert len(chips) == len(FAQ_ENTRIES)
    assert {"id", "chip"} <= set(chips[0].keys())


@pytest.mark.asyncio
async def test_faq_strong_hit_returns_answer_links_and_chips(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "押金怎么退"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "faq"
    assert "押金" in data["reply"]
    assert data["quick_replies"]  # 后续建议 chips
    assert data["links"] and data["links"][0]["to"].startswith("/")
    assert data["recommendations"] == []


@pytest.mark.asyncio
async def test_faq_weak_hit_asks_confirmation(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "合同"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "faq"
    # 反问确认而非硬答政策
    assert "想了解" in data["reply"]
    assert "合同怎么签" in data["quick_replies"]


@pytest.mark.asyncio
async def test_faq_sse_forwards_grounded_provider_tokens_and_persists_reply(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAQ SSE 原样转发模型 token，且结果元数据与历史正文保持一致。"""
    from app.services.agentic import dispatcher as dispatcher_module

    entry = get_faq("deposit")
    assert entry is not None
    raw_tokens = [entry.answer[:19], entry.answer[19:71], entry.answer[71:]]

    class StreamingLlm:
        is_available = True

        def __init__(self) -> None:
            self.complete_text_calls = 0
            self.stream_messages: list[dict[str, str]] = []
            self.stream_kwargs: dict = {}

        async def complete_text(self, *_args, **_kwargs):
            self.complete_text_calls += 1
            raise AssertionError("FAQ SSE 不得调用非流式 complete_text")

        async def complete_text_stream(self, messages, **kwargs):
            self.stream_messages = messages
            self.stream_kwargs = kwargs
            for token in raw_tokens:
                yield token

    async def classify_as_general(
        _message: str,
        _history: list[dict] | None = None,
    ) -> dict:
        return {"intent": "general", "stage": "general", "refs": []}

    fake_llm = StreamingLlm()
    monkeypatch.setattr(dispatcher_module, "classify_message", classify_as_general)
    monkeypatch.setattr(dispatcher_module, "get_llm_service", lambda: fake_llm)

    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "押金怎么退"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    tokens = [event["token"] for event in events if "token" in event]
    statuses = [
        event["meta"]["status"]
        for event in events
        if "meta" in event and event["meta"].get("event") == "status"
    ]
    result = next(
        event["meta"]
        for event in events
        if "meta" in event and event["meta"].get("event") == "result"
    )

    assert response.status_code == 200
    assert tokens == raw_tokens
    assert statuses == ["understanding", "generating"]
    assert fake_llm.complete_text_calls == 0
    assert fake_llm.stream_kwargs["temperature"] == 0
    assert entry.answer in fake_llm.stream_messages[0]["content"]
    assert fake_llm.stream_messages[1] == {"role": "user", "content": "押金怎么退"}
    assert result["reply"] == "".join(raw_tokens)
    assert result["intent"] == "faq"
    assert result["quick_replies"] == entry.next_chips
    assert result["links"] == [
        {"label": link.label, "to": link.to} for link in entry.links
    ]

    history = await client.get(
        f"/api/v1/agent/sessions/{session_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()["items"][-1]["content"] == "".join(raw_tokens)


@pytest.mark.asyncio
async def test_faq_sse_offline_falls_back_to_one_official_answer_frame(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型不可用时 FAQ 保持确定性，只发送一次官方答案。"""
    from app.services.agentic import dispatcher as dispatcher_module

    entry = get_faq("deposit")
    assert entry is not None

    class OfflineLlm:
        is_available = False

        async def complete_text_stream(self, *_args, **_kwargs):
            raise AssertionError("离线模式不得调用模型流")
            yield ""  # pragma: no cover

    async def classify_as_general(
        _message: str,
        _history: list[dict] | None = None,
    ) -> dict:
        return {"intent": "general", "stage": "general", "refs": []}

    monkeypatch.setattr(dispatcher_module, "classify_message", classify_as_general)
    monkeypatch.setattr(dispatcher_module, "get_llm_service", lambda: OfflineLlm())

    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "押金怎么退"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    tokens = [event["token"] for event in events if "token" in event]
    result = next(
        event["meta"]
        for event in events
        if "meta" in event and event["meta"].get("event") == "result"
    )

    assert response.status_code == 200
    assert tokens == [entry.answer]
    assert result["reply"] == entry.answer
    assert result["intent"] == "faq"
    assert result["quick_replies"] == entry.next_chips
    assert result["links"] == [
        {"label": link.label, "to": link.to} for link in entry.links
    ]
